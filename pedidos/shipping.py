"""Cálculo do frete: tabela por UF + frete grátis acima de um valor (decisão 90).

Nenhum valor fica no código: a tabela (ShippingRate) e o limite do frete
grátis (StoreSettings) são editados pela dona no admin.
"""

from decimal import Decimal

from loja.models import StoreSettings

from .models import ShippingRate


class ShippingUnavailableError(Exception):
    """A loja ainda não entrega na UF informada."""


def calculate_shipping(state, items_total):
    """Devolve o frete (Decimal) para a UF e o total dos produtos.

    - total dos produtos >= limite do frete grátis -> Decimal('0');
    - senão, o preço da UF na tabela;
    - UF sem linha na tabela -> ShippingUnavailableError.
    """
    threshold = StoreSettings.load().free_shipping_threshold
    rate = ShippingRate.objects.filter(state=state).first()
    if rate is None:
        raise ShippingUnavailableError(
            'Ainda não entregamos neste estado. Fale com a gente pelo WhatsApp.'
        )
    if threshold is not None and items_total >= threshold:
        return Decimal('0')
    return rate.price


def shipping_table():
    """Tabela para a tela do checkout: {"SP": "19.90", ...} + limite do frete grátis.

    Os valores vão como TEXTO (e não número) para o JavaScript não errar os
    centavos (decisão 33). É só para MOSTRAR: o valor cobrado é sempre o
    calculado de novo pelo servidor em calculate_shipping().
    """
    threshold = StoreSettings.load().free_shipping_threshold
    return {
        'rates': {rate.state: str(rate.price) for rate in ShippingRate.objects.all()},
        'free_from': str(threshold) if threshold is not None else None,
    }
