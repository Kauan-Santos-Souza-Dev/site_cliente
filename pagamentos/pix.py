"""Cobrança Pix de um pedido: cria no Mercado Pago e alinha os prazos (decisão 103).

Quem manda no prazo?
O prazo da cobrança Pix e a reserva do pedido usam o mesmo instante de
expiração. O horário local é contado a partir do início da requisição ao
gateway, para nunca ultrapassar os N minutos de validade do Pix.

Por que a reserva é renovada?
O Pix é gerado DEPOIS do checkout (a cliente pode demorar a clicar em
"Pagar com Pix"). Sem renovar, ela poderia receber um Pix de 30 minutos
para um pedido que expira em 5. Como existe um Pix só por pedido, a
renovação acontece uma única vez.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from loja.models import StoreSettings
from pedidos.models import Order

from . import gateway
from .models import Payment

logger = logging.getLogger('pagamentos')

# O Mercado Pago não aceita Pix com prazo menor que 30 minutos.
PIX_MINIMUM_MINUTES = 30
class PixNotAllowed(Exception):
    """O pedido não aguarda mais pagamento (pago, expirado, cancelado...)."""


def pix_minutes():
    """Prazo do Pix, em minutos: o da reserva da loja, nunca menos que 30."""
    return max(StoreSettings.load().reservation_minutes, PIX_MINIMUM_MINUTES)


def _lock_order_awaiting_payment(order_id, now):
    """Trava o pedido e confere que ele ainda aguarda pagamento, dentro do prazo.

    select_for_update(): trava a linha até o fim da transação. Expirar,
    cancelar e gerar o Pix ao mesmo tempo nunca se atropelam: quem chega
    depois espera e relê o status novo. Só funciona dentro de transaction.atomic().
    """
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.AWAITING_PAYMENT:
        raise PixNotAllowed
    if order.expires_at is not None and order.expires_at <= now:
        raise PixNotAllowed
    return order


def start_pix_payment(order):
    """Gera (ou reaproveita) a cobrança Pix do pedido e devolve o Payment.

    A view já conferiu que o pedido é da conta logada (contra IDOR).

    Três passos, para NÃO segurar a trava do banco durante a chamada de rede:
    1. Com trava: confere o pedido e cria o Payment "criando", com a chave
       de idempotência já gravada. Se o Pix já existe, devolve o mesmo.
    2. Sem trava: chama o Mercado Pago (pode levar alguns segundos).
    3. Com trava: grava IDs, "copia e cola" e prazos.

    Se o passo 2 falhar (GatewayError), o Payment fica "criando" com a MESMA
    chave: a próxima tentativa não cria cobrança duplicada no Mercado Pago.
    Se duas requisições chegarem juntas (clique duplo), as duas mandam a
    mesma chave, o Mercado Pago devolve a mesma cobrança e só a primeira
    grava no passo 3.
    """
    # Passo 1
    with transaction.atomic():
        locked_order = _lock_order_awaiting_payment(order.pk, timezone.now())
        payment, _created = Payment.objects.get_or_create(
            order=locked_order, method=Payment.Method.PIX,
            defaults={'amount': locked_order.total},
        )
        if payment.status != Payment.Status.CREATING:
            return payment  # o Pix já foi gerado: reaproveita

    # Passo 2
    minutes = pix_minutes()
    requested_at = timezone.now()
    charge = gateway.create_pix_order(
        reference=payment.external_reference,
        amount=payment.amount,
        payer_email=order.user.email,
        expiration_minutes=minutes,
        idempotency_key=payment.idempotency_key,
    )

    # Passo 3
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != Payment.Status.CREATING:
            return payment  # outra requisição já gravou (clique duplo)
        now = timezone.now()
        payment.status = Payment.Status.PENDING
        payment.gateway_order_id = charge.id
        payment.gateway_payment_id = charge.payment_id
        payment.gateway_status = charge.status
        payment.gateway_status_detail = charge.status_detail
        payment.pix_code = charge.pix_code
        payment.expires_at = requested_at + timedelta(minutes=minutes)
        payment.qr_code_base64 = charge.qr_code_base64
        payment.save()
        # Renova a reserva (uma vez só) se o pedido ainda aguarda. Se ele foi
        # cancelado nesse meio-tempo, não mexe: um pagamento que chegue mesmo
        # assim vira estorno (v2 Etapa 7b).
        if locked_order.status == Order.Status.AWAITING_PAYMENT:
            locked_order.expires_at = payment.expires_at
            locked_order.save(update_fields=['expires_at', 'updated_at'])

    # Log só com números e status: nada de e-mail, valor ou "copia e cola".
    logger.info(
        'Pix criado: pedido %s, pagamento %s, status no Mercado Pago "%s".',
        order.pk, payment.pk, charge.status,
    )
    return payment
