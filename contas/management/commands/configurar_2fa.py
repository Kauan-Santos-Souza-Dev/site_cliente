"""Configura (ou refaz) o 2FA de uma conta do admin. Roda NO SERVIDOR (decisão 75).

Como usar:
    python manage.py configurar_2fa dona@exemplo.com
    python manage.py configurar_2fa dona@exemplo.com --redefinir

Por que um comando, e não uma tela?
O login do admin já pede o código do 2FA. Uma conta nova (ou quem perdeu o
celular) não teria como entrar para cadastrar o celular: o "ovo e a
galinha". Quem tem acesso ao servidor resolve por aqui. Isso também é o
PLANO DE RECUPERAÇÃO: perdeu o celular e os códigos de backup? Alguém com
acesso ao servidor roda o comando com --redefinir.

O que o comando faz:
1. Cria o "dispositivo" TOTP: uma chave secreta compartilhada entre o
   servidor e o app autenticador (Google Authenticator, Microsoft
   Authenticator, Aegis...). A cada 30 segundos, os dois calculam o mesmo
   código de 6 dígitos a partir da chave e do relógio.
2. Mostra essa chave como QR Code no terminal, para o celular ler.
3. Gera 10 códigos de backup, cada um usado UMA vez, para quando o
   celular não estiver à mão. Eles aparecem só agora: guarde em lugar seguro.

ATENÇÃO: o QR Code e a URL "otpauth://" contêm a chave secreta. Não tire
foto da tela, não cole em conversas e não rode o comando gravando a saída
em arquivo de log.
"""

import qrcode
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

# Quantos códigos de backup gerar.
BACKUP_CODES_COUNT = 10


class Command(BaseCommand):
    """Cria o app autenticador e os códigos de backup de uma conta do admin."""

    help = 'Configura o 2FA (app autenticador + códigos de backup) de uma conta do admin.'

    def add_arguments(self, parser):
        """Argumentos: o e-mail da conta e a opção --redefinir."""
        parser.add_argument('email', help='E-mail da conta do admin.')
        parser.add_argument(
            '--redefinir',
            action='store_true',
            help='Apaga o 2FA atual (celular e códigos de backup) e cria um novo.',
        )

    def handle(self, *args, **options):
        """Valida a conta, cria os dispositivos e mostra QR Code e códigos."""
        user = self.get_admin_user(options['email'])
        has_devices = (
            TOTPDevice.objects.filter(user=user).exists()
            or StaticDevice.objects.filter(user=user).exists()
        )
        if has_devices and not options['redefinir']:
            raise CommandError(
                'Esta conta já tem 2FA. Para trocar (ex.: celular perdido), '
                'rode de novo com --redefinir.'
            )

        # Tudo ou nada: se algo falhar no meio, a conta não fica sem 2FA válido.
        with transaction.atomic():
            TOTPDevice.objects.filter(user=user).delete()
            StaticDevice.objects.filter(user=user).delete()
            totp = TOTPDevice.objects.create(user=user, name='Celular', confirmed=True)
            codes = self.create_backup_codes(user)

        self.show_qr_code(totp.config_url)
        self.stdout.write('')
        self.stdout.write('Códigos de backup (cada um vale UMA vez; guarde em lugar seguro):')
        for code in codes:
            self.stdout.write(f'  {code}')
        self.stdout.write(self.style.SUCCESS(f'2FA configurado para {user.email}.'))

    def get_admin_user(self, email):
        """Busca a conta pelo e-mail e confere que ela é do admin (is_staff)."""
        User = get_user_model()
        try:
            user = User.objects.get_by_natural_key(email)
        except User.DoesNotExist:
            raise CommandError('Não existe conta com este e-mail.')
        if not user.is_staff:
            # Clientes não usam 2FA (decisão 61): só quem entra no admin.
            raise CommandError('Esta conta não tem acesso ao admin (is_staff=False).')
        return user

    def create_backup_codes(self, user):
        """Cria o dispositivo de códigos de backup e devolve os códigos gerados."""
        device = StaticDevice.objects.create(user=user, name='Códigos de backup', confirmed=True)
        codes = [StaticToken.random_token() for _ in range(BACKUP_CODES_COUNT)]
        StaticToken.objects.bulk_create(StaticToken(device=device, token=code) for code in codes)
        return codes

    def show_qr_code(self, config_url):
        """Desenha o QR Code no terminal e mostra a URL (para digitar à mão, se preciso).

        O desenho usa só "#" e espaços (ASCII). Os caracteres de bloco
        (█ ▀ ▄) que o qrcode usa por padrão quebram no terminal do Windows
        quando a saída não é UTF-8 (bug real, visto ao testar o comando).

        Cada "módulo" (quadradinho) do QR vira 2 caracteres, porque a letra
        do terminal é mais alta do que larga. Os módulos CLAROS viram "##":
        num terminal de fundo escuro, o "#" claro faz o papel do branco do
        QR, e o fundo escuro faz o papel do preto.
        """
        qr = qrcode.QRCode(border=2)
        qr.add_data(config_url)
        lines = [
            ''.join('  ' if is_dark else '##' for is_dark in row)
            for row in qr.get_matrix()
        ]
        self.stdout.write('Leia este QR Code com o app autenticador do celular')
        self.stdout.write('(se o celular não ler, diminua o zoom do terminal):')
        self.stdout.write('\n'.join(lines))
        self.stdout.write('Se não der para ler, cadastre manualmente esta URL no app:')
        self.stdout.write(f'  {config_url}')
