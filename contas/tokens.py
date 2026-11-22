"""Tokens dos links enviados por e-mail: verificação (decisão 72) e troca de e-mail (decisão 81).

Como funciona, sem guardar nada no banco:
`signing.dumps` transforma um pequeno dicionário em texto e "assina" esse
texto com a SECRET_KEY. A assinatura é como um lacre: se alguém mudar uma
letra do token (para tentar verificar a conta de outra pessoa), o lacre
não confere e `signing.loads` recusa. O token também leva a hora em que
foi criado, e `max_age` recusa tokens mais velhos que 24 horas.

O token NÃO é secreto quanto ao conteúdo (dá para ler o id e o e-mail);
ele só não pode ser FALSIFICADO. Por isso não colocamos nada sensível nele.
"""

from django.contrib.auth import get_user_model
from django.core import signing

# "Sal" separa este uso de outros usos da SECRET_KEY: um token assinado para
# outra finalidade não serve aqui.
VERIFICATION_SALT = 'contas.verificacao-email'
# Validade do link: 24 horas, em segundos.
VERIFICATION_MAX_AGE = 60 * 60 * 24


def make_verification_token(user):
    """Cria o token do link de verificação para esta conta."""
    payload = {'uid': user.pk, 'email': user.email}
    return signing.dumps(payload, salt=VERIFICATION_SALT)


def get_user_from_verification_token(token):
    """Devolve a conta do token, ou None se ele for inválido, adulterado ou vencido.

    O e-mail dentro do token precisa ser o e-mail ATUAL da conta: se ele
    mudou depois que o link foi enviado, o link antigo não vale mais.
    """
    try:
        # SignatureExpired (vencido) é um tipo de BadSignature, então os dois
        # casos caem no mesmo except.
        payload = signing.loads(token, salt=VERIFICATION_SALT, max_age=VERIFICATION_MAX_AGE)
    except signing.BadSignature:
        return None
    User = get_user_model()
    return User.objects.filter(pk=payload.get('uid'), email=payload.get('email')).first()


# ---------------------------------------------------------------------------
# Troca de e-mail em "Minha conta" (decisão 81)
# ---------------------------------------------------------------------------
# Mesmo mecanismo do link de verificação, com OUTRO sal: um token de
# verificação não serve para trocar e-mail, e vice-versa.
EMAIL_CHANGE_SALT = 'contas.troca-email'
EMAIL_CHANGE_MAX_AGE = 60 * 60 * 24


def make_email_change_token(user, new_email):
    """Cria o token do link enviado ao NOVO e-mail.

    Leva o e-mail ATUAL também: se a conta trocar de e-mail por outro
    caminho antes do clique, este link deixa de valer.
    """
    payload = {'uid': user.pk, 'old': user.email, 'new': new_email}
    return signing.dumps(payload, salt=EMAIL_CHANGE_SALT)


def read_email_change_token(token):
    """Devolve (conta, novo_email), ou (None, None) se o token não vale.

    Não vale quando: foi adulterado, passou de 24 horas, ou o e-mail atual
    da conta já não é o que estava no token (link antigo ou já usado).
    """
    try:
        payload = signing.loads(token, salt=EMAIL_CHANGE_SALT, max_age=EMAIL_CHANGE_MAX_AGE)
    except signing.BadSignature:
        return None, None
    User = get_user_model()
    user = User.objects.filter(
        pk=payload.get('uid'), email=payload.get('old'), is_active=True
    ).first()
    if user is None:
        return None, None
    return user, payload.get('new')
