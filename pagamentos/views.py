"""Views do Pix: gerar a cobrança, mostrar o QR Code, informar a situação (decisão 104)
e receber o webhook do Mercado Pago (v2 Etapa 7b, decisões 106 e 107).

Segurança comum às views da cliente:
- @login_required e busca SEMPRE por request.user.orders: pedido de outra
  conta, sem dona (v1) ou inexistente dá 404 (contra IDOR, decisão 91).
- Nenhuma delas marca o pedido como pago. Quem confirma pagamento é o
  webhook do Mercado Pago, depois de reconsultar a API (v2 Etapa 7b).
"""

import logging

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from pedidos.models import Order
from pedidos.reservations import expire_overdue_orders

from . import gateway
from .models import Payment
from .pix import PixNotAllowed, start_pix_payment
from .webhook import process_order_notification

logger = logging.getLogger('pagamentos')

# Tipos de aviso que tratamos. A documentação usa "order" numa página e
# "orders" em outra; aceitamos os dois.
ORDER_NOTIFICATION_TYPES = {'order', 'orders'}


def make_qr_svg(text):
    """Desenha o QR Code do "copia e cola" como SVG (texto), com a biblioteca qrcode.

    É seguro pôr este SVG na página com |safe: ele é gerado pela biblioteca
    e só contém um <path> com coordenadas. O conteúdo do Pix vira desenho,
    não texto, então não há como injetar HTML por ele.
    """
    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    return image.to_string(encoding='unicode')


@login_required
@require_POST
def start_pix(request, pk):
    """Botão "Pagar com Pix": gera a cobrança (ou reaproveita) e abre a página do QR.

    Só POST (com o token CSRF do Django): gerar cobrança muda dados, então
    um link ou um robô não pode disparar isso.
    """
    expire_overdue_orders(user=request.user)
    order = get_object_or_404(request.user.orders, pk=pk)
    if not gateway.is_configured():
        messages.error(request, 'O pagamento online está indisponível no momento. Fale com a loja pelo WhatsApp.')
        return redirect('order_detail', pk=order.pk)
    try:
        start_pix_payment(order)
    except PixNotAllowed:
        messages.error(request, f'O pedido nº {order.pk} não aguarda mais pagamento.')
        return redirect('order_detail', pk=order.pk)
    except gateway.GatewayError:
        # Mensagem genérica: o detalhe técnico não vai para a tela.
        messages.error(request, 'Não foi possível gerar o Pix agora. Tente de novo em instantes.')
        return redirect('order_detail', pk=order.pk)
    return redirect('pix_page', pk=order.pk)


@login_required
def pix_page(request, pk):
    """Página do Pix: QR Code, "copia e cola", valor e prazo.

    Se o Pix ainda não foi gerado, volta ao detalhe do pedido (onde está o
    botão). Depois de pago ou expirado, mostra só a situação, sem o QR.
    """
    expire_overdue_orders(user=request.user)
    order = get_object_or_404(request.user.orders.prefetch_related('items'), pk=pk)
    payment = order.payments.filter(method=Payment.Method.PIX).exclude(pix_code='').first()
    if payment is None:
        return redirect('order_detail', pk=order.pk)
    context = {
        'order': order,
        'payment': payment,
        # O QR retornado pelo gateway é persistido; SVG atende cobranças antigas.
        'qr_data_uri': f'data:image/png;base64,{payment.qr_code_base64}' if payment.qr_code_base64 else '',
        # O QR só aparece enquanto o pedido aguarda pagamento.
        'qr_svg': make_qr_svg(payment.pix_code) if order.is_awaiting_payment else '',
        'late_paid': is_late_paid(order, payment),
    }
    return render(request, 'pagamentos/pix.html', context)


def is_late_paid(order, payment):
    """True se o Pix foi pago DEPOIS de o pedido expirar ou ser cancelado (decisão 108).

    A conta fica aqui, e não no template, porque o {% if %} do Django não
    aceita parênteses e a condição ficaria confusa de ler. A página só
    LÊ a situação gravada pelo webhook: nada é confirmado por ela.
    """
    return (
        payment.status == Payment.Status.LATE_PAID
        and order.status in (Order.Status.EXPIRED, Order.Status.CANCELLED)
    )


@login_required
@require_GET
@never_cache
def pix_status(request, pk):
    """Situação do pedido em JSON, para a página do Pix se atualizar sozinha.

    Lê SÓ o nosso banco: não fala com o Mercado Pago e não confirma nada.
    O navegador serve apenas para ATUALIZAR A TELA; quem muda o status para
    "pago" é o webhook. A única escrita possível aqui é a expiração
    "preguiçosa" (decisão 88), a mesma de "Meus pedidos".

    @never_cache: o navegador não pode guardar uma resposta velha
    ("aguardando") e mostrá-la de novo depois que o pedido foi pago.
    """
    expire_overdue_orders(user=request.user)
    order = get_object_or_404(request.user.orders, pk=pk)
    return JsonResponse({'status': order.status})


@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    """Recebe o aviso do Mercado Pago de que uma order (Pix) mudou.

    O que é um webhook? Em vez de a loja perguntar ao Mercado Pago "já
    pagaram?" a cada minuto, o Mercado Pago CHAMA esta URL quando algo muda.

    Por que @csrf_exempt (a ÚNICA rota POST do site sem CSRF)? O token CSRF
    prova que o formulário saiu de uma página nossa, aberta no navegador da
    cliente. Quem chama aqui é o servidor do Mercado Pago, que não tem esse
    token. A proteção no lugar dele é a ASSINATURA (HMAC com a chave secreta)
    e, depois, a reconsulta à API: mesmo um aviso verdadeiro só serve de
    "campainha".

    Sem login: o Mercado Pago não tem conta no site. Nenhum dado sai daqui:
    a resposta é sempre vazia.

    Códigos de resposta:
    - 401: assinatura inválida/ausente. Nada é processado.
    - 200: aviso aceito (inclusive order desconhecida ou tipo que não nos
      interessa: responder erro faria o Mercado Pago reenviar à toa).
    - 503: problema NOSSO (chave não configurada ou Mercado Pago fora do ar na
      reconsulta). O Mercado Pago tenta de novo depois (a cada 15 minutos).
    - 500: erro inesperado (o Django responde sozinho); também gera reenvio.

    O corpo do aviso NÃO é lido: tudo o que importa vem da reconsulta.
    """
    if not settings.MERCADOPAGO_WEBHOOK_SECRET or not gateway.is_configured():
        logger.error('Webhook recebido, mas o Mercado Pago não está configurado no .env.')
        return HttpResponse(status=503)

    # data.id e type chegam na QUERY STRING (?data.id=ORD...&type=order).
    data_id = request.GET.get('data.id', '').strip()
    notification_type = request.GET.get('type', '').strip()
    signature_ok = data_id and gateway.is_webhook_signature_valid(
        request.headers.get('x-signature'), request.headers.get('x-request-id'), data_id,
    )
    if not signature_ok:
        return HttpResponse(status=401)

    if notification_type and notification_type not in ORDER_NOTIFICATION_TYPES:
        return HttpResponse(status=200)  # outro tipo de aviso: não é conosco

    try:
        process_order_notification(data_id)
    except gateway.GatewayError:
        # Não conseguimos confirmar agora: 503 faz o Mercado Pago reenviar.
        return HttpResponse(status=503)
    return HttpResponse(status=200)
