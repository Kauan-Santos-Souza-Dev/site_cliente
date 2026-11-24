from django.apps import AppConfig


class PagamentosConfig(AppConfig):
    """App de pagamentos: integração com o Mercado Pago (Pix na v2 Etapa 7)."""

    name = 'pagamentos'
    verbose_name = 'pagamentos'
