"""Transforma o carrinho em pedido (Order + OrderItem), desconta o estoque e calcula o frete."""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from carrinho.cart import Cart
from loja.models import ProductVariant, StoreSettings

from .models import Order, OrderItem
from .shipping import calculate_shipping


class OutOfStockError(Exception):
    """Algum item do carrinho não tem mais estoque suficiente."""


def create_order(cart, form, user):
    """Cria o pedido da conta `user` a partir do carrinho e do formulário válido.

    Devolve o Order criado, ou lança OutOfStockError / ShippingUnavailableError
    (e nada é salvo).

    O pedido nasce "aguardando pagamento", com as peças RESERVADAS (estoque já
    descontado) até expires_at (decisão 88).

    transaction.atomic(): tudo aqui dentro é uma única transação no banco.
    Ou TUDO é gravado (pedido, itens e estoque descontado), ou NADA é.
    Se lançarmos um erro no meio, o Django desfaz o que já tinha feito
    (rollback): não sobra pedido sem itens, nem estoque descontado à toa.
    """
    with transaction.atomic():
        # select_for_update(): TRAVA as linhas destas variações até o fim da
        # transação. Se outra cliente estiver finalizando um pedido com a mesma
        # peça, ela espera esta transação terminar e então lê o estoque já
        # atualizado. Sem a trava, as duas poderiam comprar a última peça.
        # order_by('pk'): trava sempre na mesma ordem (evita deadlock, ver
        # Order.restore_stock).
        variants = (
            ProductVariant.objects.select_for_update()
            .select_related('product')
            .filter(id__in=cart.data.keys())
            .order_by('pk')
        )
        variants_by_id = {str(variant.id): variant for variant in variants}

        # 1) Confere o estoque de TODOS os itens antes de gravar qualquer coisa.
        for variant_id, quantity in cart.data.items():
            variant = variants_by_id.get(variant_id)
            if variant is None:
                raise OutOfStockError('Um item do seu carrinho não está mais disponível.')
            error = Cart.check_stock(variant, quantity)
            if error:
                raise OutOfStockError(f'{variant.product.name}: {error}')

        # 2) Frete calculado com os preços ATUAIS (os das linhas travadas).
        #    UF sem frete lança ShippingUnavailableError e desfaz tudo.
        items_total = sum(
            (variants_by_id[vid].product.price * qty for vid, qty in cart.data.items()),
            Decimal('0'),
        )
        shipping_cost = calculate_shipping(form.cleaned_data['state'], items_total)

        # 3) Grava o pedido. commit=False: o form monta o Order, mas ainda não
        #    salva; completamos dona, frete e prazo e só então salvamos.
        order = form.save(commit=False)
        order.user = user
        order.status = Order.Status.AWAITING_PAYMENT
        order.shipping_cost = shipping_cost
        minutes = StoreSettings.load().reservation_minutes
        order.expires_at = timezone.now() + timedelta(minutes=minutes)
        order.save()

        # 4) Cria os itens, copiando nome, tamanho e PREÇO ATUAL, e desconta o estoque.
        for variant_id, quantity in cart.data.items():
            variant = variants_by_id[variant_id]
            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                size=variant.size,
                unit_price=variant.product.price,
                quantity=quantity,
            )
            # Seguro mesmo sem F(): a linha está travada pelo select_for_update.
            variant.stock -= quantity
            variant.save(update_fields=['stock'])

    return order
