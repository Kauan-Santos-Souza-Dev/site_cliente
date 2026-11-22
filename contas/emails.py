"""Envio dos e-mails de segurança da conta (decisões 72 e 73).

Todos passam por `can_send_email`: no máximo um e-mail a cada 2 minutos por
conta. Sem esse limite, qualquer pessoa poderia encher a caixa de entrada de
outra (mail bombing) repetindo o cadastro ou o "esqueci a senha" com o
e-mail dela. A resposta do site é sempre a mesma, então quem tenta não
descobre se o e-mail foi enviado ou não.

Os e-mails não vão para nenhum log: em desenvolvimento aparecem só no
terminal (backend de console).
"""

from datetime import timedelta

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .tokens import make_verification_token

# Intervalo mínimo entre dois e-mails de segurança para a mesma conta.
EMAIL_COOLDOWN = timedelta(minutes=2)


def can_send_email(user):
    """Diz se já passou o intervalo mínimo desde o último e-mail desta conta."""
    if user.last_email_sent_at is None:
        return True
    return timezone.now() - user.last_email_sent_at >= EMAIL_COOLDOWN


def mark_email_sent(user):
    """Anota a hora do envio (só este campo é gravado)."""
    user.last_email_sent_at = timezone.now()
    user.save(update_fields=['last_email_sent_at'])


def send_template_email(to_email, name, context):
    """Monta o e-mail a partir de templates/contas/email/<name>_assunto.txt e <name>.txt."""
    subject = render_to_string(f'contas/email/{name}_assunto.txt', context).strip()
    body = render_to_string(f'contas/email/{name}.txt', context)
    # from_email=None usa o DEFAULT_FROM_EMAIL do settings.
    send_mail(subject, body, None, [to_email])


def send_verification_email(request, user):
    """Envia o link de verificação (válido por 24 h). Devolve True se enviou.

    build_absolute_uri monta o link completo (https://dominio/...) a partir do
    endereço da requisição. O ALLOWED_HOSTS impede que um atacante troque o
    domínio do link mandando um cabeçalho "Host" falso.
    """
    if not can_send_email(user):
        return False
    token = make_verification_token(user)
    link = request.build_absolute_uri(reverse('verify_email', args=[token]))
    send_template_email(user.email, 'verificacao', {'user': user, 'link': link})
    mark_email_sent(user)
    return True


def send_account_exists_email(request, user):
    """Avisa a dona de uma conta VERIFICADA que alguém tentou cadastrar o e-mail dela.

    O site responde ao cadastro com a mesma mensagem de sempre (não revela
    que o e-mail existe). Só a dona do e-mail, na caixa de entrada dela,
    fica sabendo, com links para entrar ou redefinir a senha.
    """
    if not can_send_email(user):
        return False
    context = {
        'user': user,
        'login_link': request.build_absolute_uri(reverse('login')),
        'reset_link': request.build_absolute_uri(reverse('password_reset')),
    }
    send_template_email(user.email, 'conta_existente', context)
    mark_email_sent(user)
    return True
