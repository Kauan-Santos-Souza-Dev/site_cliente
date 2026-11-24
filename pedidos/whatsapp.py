"""Formatação de dinheiro (R$) e o link do WhatsApp para falar sobre um pedido."""

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


def build_message(order):
    """Texto que a cliente envia à loja pelo WhatsApp para falar de um pedido.

    Na v2 o pedido fica no site (Meus pedidos), então a mensagem leva só o
    número: menos dado pessoal (nome, endereço) circulando numa URL.
    """
    return f'Olá! Quero falar sobre o meu pedido nº {order.pk} no site.'


def build_whatsapp_url(order):
    """Link wa.me com a mensagem pronta.

    quote() codifica o texto para caber numa URL: espaço vira %20,
    quebra de linha vira %0A, "ç" vira %C3%A7 etc. Sem isso, o link
    quebraria no primeiro espaço ou caractere especial.
    """
    return f'https://wa.me/{settings.WHATSAPP_NUMBER}?text={quote(build_message(order))}'
