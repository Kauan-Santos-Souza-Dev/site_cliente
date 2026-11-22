"""Ajuste do django-axes ao login por e-mail (decisão 71)."""

from django.contrib.auth import get_user_model


def get_axes_username(request, credentials):
    """Devolve o e-mail digitado, padronizado, para o axes contar as tentativas.

    O axes chama esta função (AXES_USERNAME_CALLABLE no settings) em DOIS
    momentos, e ela precisa devolver o mesmo valor nos dois:
    1. ANTES de conferir a senha, para saber se o par e-mail + IP está
       bloqueado. Aqui as credenciais chegam com a chave do USERNAME_FIELD
       do nosso modelo: "email".
    2. DEPOIS de uma senha errada, para registrar a falha. Aqui a chave é
       "username" (o nome que o Django usa no sinal de login falho).

    Cuidado (bug real, pego pelos testes): a primeira versão lia só
    "username". No momento 1 ela devolvia texto vazio, o axes não achava as
    falhas e deixava a senha certa entrar mesmo com o par bloqueado.

    A padronização (minúsculas) impede que "Maria@X.com" e "maria@x.com"
    tenham contadores separados.
    """
    User = get_user_model()
    email = ''
    if credentials:
        email = credentials.get('username') or credentials.get(User.USERNAME_FIELD) or ''
    if not email:
        # Sem credenciais (ex.: a verificação feita pelo middleware): lê o formulário.
        email = request.POST.get('username', '')
    return User.objects.normalize_email(email)
