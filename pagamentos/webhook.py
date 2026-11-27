"""Regra do webhook do Pix: o que fazer quando o Mercado Pago avisa que uma order mudou.

A view (views.mercadopago_webhook) já validou a ASSINATURA do aviso. Aqui
vem o resto, e a regra de ouro é: NUNCA confiar no corpo do aviso.
O aviso serve só de "campainha"; o estado verdadeiro da cobrança vem da
reconsulta ao Mercado Pago (gateway.get_order), feita com o nosso token.

O que é idempotência aqui?
O Mercado Pago pode mandar o MESMO aviso várias vezes (reenvia se não
recebeu resposta a tempo, e às vezes manda repetido mesmo assim).
Processar de novo não pode ter efeito novo: o pedido vira "pago" uma vez
só e o approved_at não muda. A trava (select_for_update) garante isso
mesmo com dois avisos chegando no mesmo instante.
"""

import logging

from django.db import transaction
from django.utils import timezone

from pedidos.models import Order

from . import gateway
from .models import Payment

logger = logging.getLogger('pagamentos')

# Resultados de process_order_notification (aparecem no log e nos testes).
UNKNOWN = 'desconhecida'
PAID = 'pago'
REPEATED = 'repetido'
DIVERGENT = 'divergente'
LATE = 'tardio'
NOT_PAID = 'pendente'

# Situações do Payment que encerram o assunto: um aviso novo não muda mais nada.
FINAL_PAYMENT_STATUSES = {
    Payment.Status.APPROVED,
    Payment.Status.LATE_PAID,
    Payment.Status.DIVERGENT,
}

# Status da order no Mercado Pago que significam "não vai mais ser paga".
# O status_detail não é comparado: a documentação mostra mais de um valor
# ("canceled", "canceled_transaction", "expired").
GATEWAY_CLOSED_STATUSES = {
    'canceled': Payment.Status.CANCELLED,
    'failed': Payment.Status.EXPIRED,
}


def process_order_notification(gateway_order_id):
    """Processa um aviso (já com assinatura válida) da order `gateway_order_id`.

    Devolve um dos resultados acima. Lança gateway.GatewayError se o Mercado
    Pago não responder: a view devolve 503 e ele tenta de novo mais tarde.

    Três passos, como em pix.start_pix_payment (sem segurar a trava do
    banco durante a chamada de rede):
    1. Sem trava: acha o Payment pelo ID da order. Não achou = não é nosso.
    2. Sem trava: pergunta ao Mercado Pago como está a order.
    3. Com trava: aplica o resultado (apply_gateway_order).
    """
    payment = Payment.objects.filter(gateway_order_id=gateway_order_id).first()
    if payment is None:
        logger.info('Webhook: order desconhecida, ignorada.')
        return UNKNOWN

    charge = gateway.get_order(gateway_order_id)
    result = apply_gateway_order(payment.pk, charge)
    # Log só com números e resultado: nada de e-mail, valor ou ID do gateway.
    logger.info('Webhook: pedido %s, pagamento %s, resultado "%s".', payment.order_id, payment.pk, result)
    return result


def apply_gateway_order(payment_id, charge):
    """Aplica ao nosso banco o que o Mercado Pago respondeu sobre a order.

    transaction.atomic() + select_for_update(): trava o PEDIDO e depois o
    PAGAMENTO (sempre nessa ordem, igual a pix.py, para não haver deadlock).
    Se dois avisos chegarem juntos, o segundo espera aqui, relê o Payment
    já "aprovado" e sai como "repetido".
    """
    with transaction.atomic():
        order_id = Payment.objects.values_list('order_id', flat=True).get(pk=payment_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status in FINAL_PAYMENT_STATUSES:
            return REPEATED

        payment.gateway_status = charge.status[:40]
        payment.gateway_status_detail = charge.status_detail[:60]

        # 1º: está pago? Se não, só atualiza o espelho. Uma cobrança não paga
        # NUNCA vira "divergente": não há dinheiro a conferir.
        if not gateway.is_paid(charge):
            closed_status = GATEWAY_CLOSED_STATUSES.get(charge.status)
            if closed_status and payment.status == Payment.Status.PENDING:
                payment.status = closed_status
            payment.save()
            return NOT_PAID

        # 2º: pago, mas é MESMO a nossa cobrança, com o valor certo?
        if not _matches_our_payment(charge, payment, order):
            payment.status = Payment.Status.DIVERGENT
            payment.save()
            logger.warning(
                'Webhook: pagamento %s do pedido %s com valor ou referência divergente. Conferir no painel.',
                payment.pk, order.pk,
            )
            return DIVERGENT

        # 3º: confirmado. O que fazer depende do pedido.
        payment.approved_at = timezone.now()
        if order.status == Order.Status.AWAITING_PAYMENT:
            return _confirm(order, payment)
        if order.status in (Order.Status.EXPIRED, Order.Status.CANCELLED):
            return _mark_late(order, payment)
        # Pedido já pago/enviado por outro caminho: só registra a cobrança.
        payment.status = Payment.Status.APPROVED
        payment.save()
        logger.warning('Webhook: pagamento %s aprovado para pedido %s já em "%s".', payment.pk, order.pk, order.status)
        return PAID


def _matches_our_payment(charge, payment, order):
    """Confere vínculo e valor (sempre Decimal, nunca float).

    - A order consultada é a que gravamos no Payment, e a external_reference
      é a que NÓS mandamos ("pagamento-<id>").
    - O valor da order e o valor pago batem com o valor congelado no Payment
      E com o total atual do pedido (itens + frete).
    total_paid_amount vazio (None) também é divergência: sem saber quanto
    foi pago, não dá para confirmar.
    """
    expected = payment.amount
    return (
        charge.id == payment.gateway_order_id
        and charge.external_reference == payment.external_reference
        and charge.total_amount == expected
        and charge.total_paid_amount == expected
        and order.total == expected
    )


def _confirm(order, payment):
    """Pedido aguardando -> pago. A reserva de estoque vira definitiva.

    order.save() aplica a tabela de transições (aguardando -> pago é
    permitido). Não devolve estoque: essa transição não está em
    STOCK_RETURNING_TRANSITIONS. E, como o status deixa de ser "aguardando",
    o expirar_pedidos nunca mais encontra este pedido.

    Vale mesmo se o prazo (expires_at) já passou sem o comando ter rodado:
    o Mercado Pago só aceita o Pix dentro da validade, que é igual à da
    reserva (decisão 103), e as peças ainda estão presas para este pedido.
    """
    order.status = Order.Status.PAID
    order.save()
    payment.status = Payment.Status.APPROVED
    payment.save()
    return PAID


def _mark_late(order, payment):
    """Pago depois de o pedido expirar ou ser cancelado (opção B, decisão 108).

    O pedido NÃO volta: as peças já foram devolvidas e podem ter sido
    vendidas. A cobrança fica "Pago após expirar (decidir)" e a dona decide
    se entrega ou estorna.
    """
    payment.status = Payment.Status.LATE_PAID
    payment.save()
    logger.warning(
        'Webhook: pagamento %s chegou com o pedido %s "%s". A dona precisa decidir.',
        payment.pk, order.pk, order.status,
    )
    return LATE
