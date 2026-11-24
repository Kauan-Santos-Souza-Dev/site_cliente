"""Reserva de estoque com prazo: expira pedidos não pagos (decisão 88).

Como funciona a reserva?
O checkout já desconta o estoque quando o pedido nasce (decisão 42): as
peças ficam "presas" para aquele pedido. O campo Order.expires_at diz até
quando. Passado o prazo sem pagamento, o pedido vira "expirado" e o
Order.save() devolve as peças ao estoque.

Quem chama a expiração?
1. O comando `python manage.py expirar_pedidos`, para um agendador rodar
   de tempos em tempos (cron, Agendador de Tarefas do Windows, scheduler da
   hospedagem, que ainda não foi escolhida).
2. A expiração "preguiçosa": algumas páginas (produto, adicionar ao
   carrinho, checkout, Meus pedidos) chamam expire_overdue_orders() antes
   de mostrar algo. É uma rede de segurança: mesmo sem agendador, a peça
   volta quando alguém tenta comprá-la.

E se os dois rodarem ao mesmo tempo? Veja expire_order().
"""

from django.db import transaction
from django.utils import timezone

from .models import Order


def overdue_orders(now):
    """Pedidos aguardando pagamento com o prazo vencido.

    Usa o índice (status, expires_at), então é uma consulta rápida mesmo com
    muitos pedidos. Pedido sem prazo (expires_at vazio, os da v1) nunca entra.
    """
    return Order.objects.filter(
        status=Order.Status.AWAITING_PAYMENT, expires_at__lt=now
    )


def expire_order(order_id, now):
    """Expira UM pedido, se ele ainda estiver vencido. Devolve True se expirou.

    Concorrência (duas requisições ao mesmo tempo):
    select_for_update() trava a linha do pedido até o fim da transação. Se o
    comando e uma página tentarem expirar o MESMO pedido juntos, o segundo
    espera o primeiro terminar e, ao reler, o pedido já está "expirado":
    o filtro não o encontra e nada acontece. O mesmo vale se o pagamento
    for confirmado nesse meio-tempo (Etapa 7): o status já não é
    "aguardando". Resultado: o estoque nunca volta em dobro (idempotência).
    """
    with transaction.atomic():
        order = (
            overdue_orders(now)
            .select_for_update()
            .filter(pk=order_id)
            .first()
        )
        if order is None:
            return False  # outro processo já resolveu este pedido
        order.status = Order.Status.EXPIRED
        order.save()  # o save() devolve o estoque (STOCK_RETURNING_TRANSITIONS)
        return True


def expire_overdue_orders(now=None, user=None):
    """Expira todos os pedidos vencidos (ou só os da conta `user`). Devolve quantos.

    Cada pedido é expirado na SUA transação: um problema num pedido não
    desfaz os outros, e as travas duram o mínimo possível.
    """
    now = now or timezone.now()
    orders = overdue_orders(now)
    if user is not None:
        orders = orders.filter(user=user)
    # list(): lê os ids de uma vez, antes de começar a alterar os pedidos.
    order_ids = list(orders.order_by('pk').values_list('pk', flat=True))
    return sum(1 for order_id in order_ids if expire_order(order_id, now))
