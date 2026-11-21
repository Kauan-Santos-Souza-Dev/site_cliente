"""Configuração do app de contas de clientes."""

from django.apps import AppConfig


class ContasConfig(AppConfig):
    """App `contas`: usuário próprio (login por e-mail), cadastro, login e logout."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contas'
    verbose_name = 'Contas'
