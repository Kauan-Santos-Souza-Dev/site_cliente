"""Cálculo das parcelas do cartão (v2 Etapa 6, decisões 98 e 99).

Aqui fica a ÚNICA função que calcula parcelas: o checkout, a página do
produto e (na Etapa 8) o envio do limite ao Mercado Pago usam esta mesma
conta. Assim o site nunca mostra uma coisa e cobra outra.

Importante: o site só MOSTRA as opções e informa o LIMITE. Quem divide e cobra
é o Mercado Pago. Os valores daqui são ESTIMATIVAS.

Todo dinheiro é Decimal (float erra centavos, ex.: 0.1 + 0.2).
"""

from decimal import ROUND_DOWN, Decimal
from typing import NamedTuple, Optional

from loja.models import StoreSettings

CENTS = Decimal('0.01')


class InstallmentOption(NamedTuple):
    """Uma opção de parcelamento: `number` parcelas.

    `amounts` tem o valor de CADA parcela (a soma é exatamente o total).
    Vem None quando a política é "a cliente paga os juros": o site não sabe a
    taxa do gateway, então não inventa valores. `total` também vira None.
    """

    number: int
    amounts: Optional[tuple]
    total: Optional[Decimal]

    @property
    def amount(self):
        """Valor da parcela "comum" (a última). A primeira pode ter centavos a mais."""
        return self.amounts[-1] if self.amounts else None


def split_in_cents(total, number):
    """Divide `total` em `number` parcelas, somando EXATAMENTE o total.

    Truncamos cada parcela para centavos (ROUND_DOWN) e a sobra vai para a
    PRIMEIRA parcela. Ex.: R$ 100,00 em 3x -> 33,34 + 33,33 + 33,33 = 100,00.
    Se arredondássemos cada parcela, a soma poderia dar R$ 99,99 ou R$ 100,01.
    """
    base = (total / number).quantize(CENTS, rounding=ROUND_DOWN)
    first = total - base * (number - 1)
    return (first,) + (base,) * (number - 1)


def get_installment_limit(products):
    """Limite de parcelas para um conjunto de produtos (o do carrinho).

    Cada produto tem o limite próprio, ou o da regra geral se o campo estiver
    vazio. Num carrinho com vários produtos vale o MENOR limite entre eles.
    (A parcela mínima é aplicada depois, em calculate_installments.)
    """
    default = StoreSettings.load().max_installments
    limits = [
        product.max_installments if product.max_installments is not None else default
        for product in products
    ]
    return min(limits) if limits else default


def calculate_installments(total, max_installments=None):
    """Devolve a lista de opções de parcelamento (1x até o limite) para `total`.

    - `max_installments`: limite do carrinho (veja get_installment_limit).
      Vazio = regra geral da loja.
    - O número de parcelas também respeita a parcela mínima: o maior N com
      total / N >= valor mínimo. Ex.: R$ 120 com mínimo R$ 50 -> até 2x.
    - Sempre existe a opção 1x (à vista no cartão), mesmo abaixo do mínimo.
    - Política "cliente paga": só os números de parcelas, sem valores.
    """
    if not isinstance(total, Decimal):
        raise TypeError('O total precisa ser Decimal (nunca float).')
    if total <= 0:
        raise ValueError('O total precisa ser maior que zero.')

    config = StoreSettings.load()
    limit = max_installments if max_installments is not None else config.max_installments
    # "//" entre Decimals é divisão inteira: quantas parcelas mínimas cabem no total.
    by_minimum = int(total // config.min_installment_value)
    biggest = max(1, min(limit, by_minimum))

    customer_pays = config.interest_policy == StoreSettings.InterestPolicy.CUSTOMER_PAYS
    options = []
    for number in range(1, biggest + 1):
        if customer_pays and number > 1:
            options.append(InstallmentOption(number, None, None))
        else:
            options.append(InstallmentOption(number, split_in_cents(total, number), total))
    return options
