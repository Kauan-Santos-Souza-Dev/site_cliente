"""Transforma o carrinho em pedido (Order + OrderItem) e desconta o estoque."""

from django.db import transaction

from carrinho.cart import Cart
from loja.models import ProductVariant

from .models import OrderItem


class OutOfStockError(Exception):
    """Algum item do carrinho não tem mais estoque suficiente."""


def create_order(cart, form):
    """Cria o pedido a partir do carrinho e do formulário de checkout válido.

    Devolve o Order criado, ou lança OutOfStockError (e nada é salvo).

    transaction.atomic(): tudo aqui dentro é uma única transação no banco.
    Ou TUDO é gravado (pedido, itens e estoque descontado), ou NADA é.
    Se lançarmos um erro no meio, o Django desfaz o que já tinha feito
    (rollback) — não sobra pedido sem itens, nem estoque descontado à toa.
    """
    with transaction.atomic():
        # select_for_update(): TRAVA as linhas destas variações até o fim da
        # transação. Se outra cliente estiver finalizando um pedido com a mesma
        # peça, ela espera esta transação terminar e então lê o estoque já
        # atualizado. Sem a trava, as duas poderiam comprar a última peça.
        variants = (
            ProductVariant.objects.select_for_update()
            .select_related('product')
            .filter(id__in=cart.data.keys())
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

        # 2) Grava o pedido com os dados do formulário.
        order = form.save()

        # 3) Cria os itens, copiando nome, tamanho e PREÇO ATUAL, e desconta o estoque.
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
