from django.apps import AppConfig


class CarrinhoConfig(AppConfig):
    """App do carrinho de compras (guardado na sessão, sem models próprios)."""

    name = 'carrinho'
