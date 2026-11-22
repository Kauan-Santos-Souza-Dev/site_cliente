"""Site do admin com 2FA obrigatório (decisão 75).

O `OTPAdminSite` do django-otp é o admin normal do Django com duas
diferenças: a tela de login pede também o código de 6 dígitos do app
autenticador (ou um código de backup), e só entra quem passou por esse
segundo passo nesta sessão. Uma senha vazada, sozinha, não abre o painel.
"""

from django_otp.admin import OTPAdminSite


class LojaAdminSite(OTPAdminSite):
    """Admin da loja: o OTPAdminSite com os textos da loja."""

    site_header = 'Elegância Cristã — painel da loja'
    site_title = 'Elegância Cristã'
    index_title = 'Administração'

    def __init__(self, name='admin'):
        """Usa o nome "admin" (o OTPAdminSite usa "otpadmin").

        Assim os endereços continuam sendo reverse('admin:...'), como antes.
        """
        super().__init__(name)
