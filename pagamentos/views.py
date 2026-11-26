"""Views do Pix: gerar a cobrança, mostrar o QR Code e informar a situação (decisão 104).

Segurança comum a todas:
- @login_required e busca SEMPRE por request.user.orders: pedido de outra
  conta, sem dona (v1) ou inexistente dá 404 (contra IDOR, decisão 91).
- Nenhuma delas marca o pedido como pago. Quem confirma pagamento é o
  webhook do Mercado Pago, depois de reconsultar a API (v2 Etapa 7b).
"""

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from pedidos.reservations import expire_overdue_orders

from . import gateway
from .models import Payment
from .pix import PixNotAllowed, start_pix_payment


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
    }
    return render(request, 'pagamentos/pix.html', context)


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
