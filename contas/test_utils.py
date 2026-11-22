"""Funções de apoio para os testes de todos os apps (não é usado pelo site)."""

from django.contrib.auth import get_user_model
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

# Senha que passa em todos os validadores (10+ caracteres, não comum, não só números).
GOOD_PASSWORD = 'Lirio-do-campo-42'


def make_customer(email='cliente@example.com', verified=True, **extra):
    """Cria uma conta de cliente (por padrão, com e-mail já verificado)."""
    return get_user_model().objects.create_user(
        email=email, password=GOOD_PASSWORD, email_verified=verified, **extra,
    )


def login_admin(client, user):
    """Entra no admin como se a conta tivesse passado pelo 2FA.

    force_login pula a senha; depois gravamos na sessão o dispositivo 2FA
    "usado", que é exatamente o que o django-otp faz quando o código de
    6 dígitos confere. Só para testes: no site, o código é obrigatório.
    """
    device = TOTPDevice.objects.create(user=user, name='Teste', confirmed=True)
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device
