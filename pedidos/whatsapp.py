"""Monta a mensagem do pedido e o link do WhatsApp da loja."""

from urllib.parse import quote

from django.conf import settings


def format_brl(value):
    """Formata um Decimal como dinheiro brasileiro: 1234.5 -> "R$ 1.234,50".

    O Python formata no padrão americano ("1,234.50"); trocamos os
    separadores usando um caractere temporário ("_").
    """
    american = f'{value:,.2f}'  # "1,234.50"
    brazilian = american.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {brazilian}'


def format_cep(cep):
    """"01234567" -> "01234-567"."""
    return f'{cep[:5]}-{cep[5:]}'


def format_phone(phone):
    """"11912345678" -> "(11) 91234-5678"; "1132345678" -> "(11) 3234-5678"."""
    return f'({phone[:2]}) {phone[2:-4]}-{phone[-4:]}'


def build_message(order):
    """Texto do pedido que a cliente envia à loja pelo WhatsApp."""
    lines = [
        f'Olá! Acabei de fazer o pedido nº {order.pk} no site.',
        '',
        '*Itens:*',
    ]
    for item in order.items.all():
        lines.append(
            f'- {item.product_name} (tam. {item.size}) x{item.quantity}: '
            f'{format_brl(item.subtotal)}'
        )

    complement = f', {order.complement}' if order.complement else ''
    lines += [
        '',
        f'*Total:* {format_brl(order.items_total)}',
        'Frete: a combinar',
        '',
        f'*Nome:* {order.customer_name}',
        f'*Telefone:* {format_phone(order.phone)}',
        f'*Entrega:* {order.street}, {order.number}{complement} - '
        f'{order.neighborhood}, {order.city}/{order.state} - CEP {format_cep(order.cep)}',
    ]
    return '\n'.join(lines)


def build_whatsapp_url(order):
    """Link wa.me com a mensagem pronta.

    quote() codifica o texto para caber numa URL: espaço vira %20,
    quebra de linha vira %0A, "ç" vira %C3%A7 etc. Sem isso, o link
    quebraria no primeiro espaço ou caractere especial.
    """
    return f'https://wa.me/{settings.WHATSAPP_NUMBER}?text={quote(build_message(order))}'
