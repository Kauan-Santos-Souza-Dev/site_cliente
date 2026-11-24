"""
Configurações do projeto Elegância Cristã.

Regra de ouro: nada secreto fica neste arquivo. Senhas e chaves vêm de
variáveis de ambiente, que em desenvolvimento são lidas do arquivo ".env"
(que NÃO vai para o Git). Veja ".env.example" para a lista de variáveis.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Pasta raiz do projeto (a que contém manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent

# Lê o arquivo .env (se existir) e joga os valores em os.environ.
# Em produção as variáveis podem vir direto do servidor, sem arquivo .env.
load_dotenv(BASE_DIR / '.env')


def get_env_bool(name, default=False):
    """Lê uma variável de ambiente como True/False (ex.: DEBUG=True).

    Variável ausente ou vazia (ex.: "SECURE_HTTPS=") usa o valor padrão.
    """
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'sim')


# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------

# A SECRET_KEY assina sessões e tokens CSRF. Se vazar, é preciso trocá-la.
# Por isso não há valor padrão: se faltar, o Django avisa com erro claro.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'Defina a variável SECRET_KEY no arquivo .env (veja o README).'
    )

# DEBUG mostra páginas de erro detalhadas: use True só em desenvolvimento.
# O padrão é False (o mais seguro) caso a variável não exista.
DEBUG = get_env_bool('DEBUG', default=False)

# Domínios que podem servir o site. Separados por vírgula no .env.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', '').split(',')
    if host.strip()
]

# HTTPS (produção). Por padrão, liga sozinho quando DEBUG=False, para não
# depender de alguém lembrar. Para testar localmente com DEBUG=False (ex.:
# ver a página 404), use SECURE_HTTPS=False no .env, pois o runserver não
# tem HTTPS.
SECURE_HTTPS = get_env_bool('SECURE_HTTPS', default=not DEBUG)
if SECURE_HTTPS:
    # Cookies de sessão (carrinho) e de CSRF só trafegam por HTTPS: quem
    # "escuta" a rede (ex.: Wi-Fi público) não consegue copiá-los.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Quem acessar por http:// é redirecionado para https://.
    SECURE_SSL_REDIRECT = True
    # HSTS: o navegador passa a recusar http:// para este domínio pelo tempo
    # indicado. Começamos com 1 hora de propósito: se o HTTPS do servidor
    # quebrar, o site fica fora do ar só por esse tempo. Depois de validar
    # o HTTPS, aumente (ex.: 31536000 = 1 ano). Veja o checklist no README.
    SECURE_HSTS_SECONDS = 60 * 60


# ---------------------------------------------------------------------------
# Aplicativos e middlewares
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Contas de clientes (v2): vem primeiro porque define o modelo de usuário.
    'contas',
    'loja',
    'carrinho',
    'pedidos',
    # Pagamentos pelo Mercado Pago (v2 Etapa 7: Pix).
    'pagamentos',
    # O admin do Django com 2FA obrigatório (contas/admin_config.py). Substitui
    # 'django.contrib.admin': é o mesmo admin, mas com outro "site" padrão.
    'contas.admin_config.LojaAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Django REST Framework: a API de leitura de produtos (etapa 5).
    'rest_framework',
    # Bloqueio de tentativas repetidas de login (v2 Etapa 3, decisão 71).
    'axes',
    # Autenticação em dois fatores (2FA) do admin (decisão 75):
    # - django_otp: o núcleo (dispositivos, verificação na sessão);
    # - otp_totp: códigos de 6 dígitos de um app autenticador no celular;
    # - otp_static: códigos de backup, cada um usado uma única vez.
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Proteção CSRF: exige o token em todo formulário POST.
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Depois da autenticação: diz se a usuária já passou pelo 2FA nesta
    # sessão (request.user.is_verified()). O admin exige isso.
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Por último, como pede a documentação do axes: transforma uma conta
    # bloqueada na página "Muitas tentativas" (templates/contas/bloqueado.html).
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Pasta de templates globais (base.html etc.), na raiz do projeto.
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Dados de contato da loja em todos os templates.
                'loja.context_processors.store_info',
                # Número de peças do carrinho (contador no menu).
                'carrinho.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ---------------------------------------------------------------------------
# Banco de dados (MySQL, acessado só pelo ORM do Django)
# ---------------------------------------------------------------------------

# O driver é o PyMySQL, ativado em config/__init__.py.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'elegancia_crista'),
        'USER': os.environ.get('DB_USER', 'elegancia'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        # utf8mb4 guarda acentos e emojis corretamente.
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}


# ---------------------------------------------------------------------------
# Contas: modelo de usuário, senhas e login (v2 Etapa 2)
# ---------------------------------------------------------------------------

# Diz ao Django para usar o NOSSO modelo de usuário (contas/models.py, login
# por e-mail) no lugar do User padrão. Tudo que fala de "usuário" (login,
# admin, permissões) passa a usar este modelo. Decisão 64.
AUTH_USER_MODEL = 'contas.User'

# Como as senhas viram hash (decisão 63). O PRIMEIRO da lista é usado para
# senhas novas: Argon2, que exige muita memória por tentativa e encarece
# ataques com placa de vídeo. Os outros ficam só para conseguir CONFERIR
# hashes antigos; no próximo login, o Django regrava a senha em Argon2.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

# Regras de senha (cadastro do site, admin e createsuperuser):
AUTH_PASSWORD_VALIDATORS = [
    # Recusa senha parecida com o e-mail ou o nome.
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    # Mínimo de 10 caracteres (o padrão é 8). Tamanho é o que mais dificulta
    # adivinhar uma senha (decisão 68).
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    # Recusa senhas de uma lista com milhares das mais usadas ("12345678"...).
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    # Recusa senha só de números.
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Para onde mandar quem precisa entrar (ex.: @login_required) e para onde ir
# depois de entrar ou sair. Aceitam o "name" de uma rota.
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# Quem confere e-mail e senha no login. A ordem importa: o axes vem primeiro
# e recusa a tentativa se o par e-mail + IP estiver bloqueado, ANTES de o
# ModelBackend (o padrão do Django) conferir a senha.
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Link de "esqueci a senha" vale 1 hora (o padrão do Django é 3 dias).
# Quanto menos tempo, menor a chance de um e-mail antigo ser mal usado.
PASSWORD_RESET_TIMEOUT = 60 * 60


# ---------------------------------------------------------------------------
# Bloqueio de tentativas de login: django-axes (decisão 71)
# ---------------------------------------------------------------------------
# Contra força bruta (testar milhares de senhas): 5 erros seguidos bloqueiam
# o par e-mail + IP por 15 minutos. O axes guarda as tentativas no BANCO,
# então o bloqueio vale para todos os processos do servidor.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Lista dentro de lista = combinação: bloqueia "este e-mail vindo deste IP".
# Assim um atacante não consegue travar a conta de alguém de outro lugar.
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
# Login certo zera o contador de erros daquele e-mail + IP.
AXES_RESET_ON_SUCCESS = True
# Padroniza o e-mail (minúsculas) antes de contar: sem isso, "A@x.com" e
# "a@x.com" teriam contadores separados e o limite seria burlado.
AXES_USERNAME_CALLABLE = 'contas.axes.get_axes_username'
# Página do bloqueio, em português e SEM citar o e-mail (não revela se ele
# existe: o bloqueio acontece igual para e-mail cadastrado ou não).
# O axes responde com status 429 ("muitas requisições").
AXES_LOCKOUT_TEMPLATE = 'contas/bloqueado.html'
# Privacidade (decisão 83):
# - NÃO guardar o histórico de logins BEM-SUCEDIDOS (tabela AccessLog, com
#   e-mail, IP e navegador). O bloqueio não depende dele, e dado que não é
#   necessário não deve ser guardado (LGPD art. 6º III, minimização).
AXES_DISABLE_ACCESS_LOG = True
# - Nas mensagens de aviso que o axes escreve no terminal/log, o e-mail e o
#   IP aparecem como "********". Este já é o padrão do axes; fica escrito
#   aqui para ninguém remover sem perceber. (A senha o axes nunca registra.)
AXES_SENSITIVE_PARAMETERS = ['username', 'ip_address']
# IP real atrás de proxy (Nginx, Cloudflare): veja o checklist do README.


# ---------------------------------------------------------------------------
# 2FA do admin: django-otp (decisão 75)
# ---------------------------------------------------------------------------
# Nome que aparece no app autenticador do celular, ao lado do código.
OTP_TOTP_ISSUER = 'Elegância Cristã'


# ---------------------------------------------------------------------------
# E-mail (verificação de conta, aviso de cadastro e redefinição de senha)
# ---------------------------------------------------------------------------
# Em desenvolvimento, o e-mail é só IMPRESSO no terminal do runserver (backend
# de console): nada sai para a internet. O envio de verdade (Brevo, por SMTP)
# será configurado quando houver credenciais (decisão 62).
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'Elegância Cristã <nao-responder@localhost>'
)


# ---------------------------------------------------------------------------
# Idioma e fuso horário
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
# O Django guarda datas em UTC no banco e converte para o fuso ao exibir.
USE_TZ = True


# ---------------------------------------------------------------------------
# Arquivos estáticos (CSS, JS, logo) e de mídia (fotos enviadas pelo admin)
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# Pasta para onde "python manage.py collectstatic" copia TODOS os estáticos
# (os nossos + os do admin e do DRF). Em produção, o servidor web serve
# essa pasta. Ela é gerada, por isso fica fora do Git.
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sessão (usada pelo carrinho): mantemos o padrão do Django.
# - Os dados ficam no banco (tabela django_session); o navegador guarda só
#   um código aleatório no cookie "sessionid".
# - O cookie é HttpOnly: JavaScript não consegue lê-lo.
# - Validade: 2 semanas (SESSION_COOKIE_AGE, em segundos).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14


# ---------------------------------------------------------------------------
# API (Django REST Framework)
# ---------------------------------------------------------------------------

# Renderizadores: JSON sempre. A "API navegável" (página HTML para testar a
# API no navegador) só em desenvolvimento, para não expor uma interface a mais.
API_RENDERERS = ['rest_framework.renderers.JSONRenderer']
if DEBUG:
    API_RENDERERS.append('rest_framework.renderers.BrowsableAPIRenderer')

REST_FRAMEWORK = {
    # "Fechado por padrão": uma view da API sem permissão declarada só é
    # acessível a administradores. As views públicas (loja/api_views.py)
    # declaram AllowAny de propósito, e são somente leitura.
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAdminUser'],
    # Listas divididas em páginas de 12 itens (?page=2).
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    # Limite de requisições por IP para visitantes anônimos: dificulta robôs
    # copiando o catálogo em massa. Passou do limite, recebe erro 429.
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '60/minute'},
    'DEFAULT_RENDERER_CLASSES': API_RENDERERS,
}


# ---------------------------------------------------------------------------
# Dados da loja (ficam aqui para não se espalharem pelos templates)
# ---------------------------------------------------------------------------

# Número só com dígitos, com DDI e DDD: usado no link https://wa.me/<número>
WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '5511985335054')
# E-mail de contato confirmado pela dona da loja (v2 Etapa 4).
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'elegancia.crist@gmail.com')
INSTAGRAM_HANDLE = 'elegancia.crista.oficial'
STORE_MOTTO = 'Operando Deus quem impedirá'

# Identificação do fornecedor exigida no comércio eletrônico (Decreto
# 7.962/2013, art. 2º I e II; decisão 85). A loja ainda não tem CNPJ: por
# isso ficam VAZIOS e a Política, os Termos e o rodapé mostram
# "[A DEFINIR PELA DONA]". Quando o CNPJ existir, basta preencher no .env,
# sem mexer em código. Só existe campo de CNPJ (não de CPF) e o endereço é
# o COMERCIAL: nunca coloque aqui CPF nem endereço residencial.
STORE_LEGAL_NAME = os.environ.get('STORE_LEGAL_NAME', '').strip()
STORE_CNPJ = os.environ.get('STORE_CNPJ', '').strip()
STORE_ADDRESS = os.environ.get('STORE_ADDRESS', '').strip()


# ---------------------------------------------------------------------------
# Pagamento online: Mercado Pago (v2 Etapa 7, decisões 100 a 105)
# ---------------------------------------------------------------------------
# Chaves SÓ no .env (nunca no código, nunca no Git, nunca em log).
# Comece SEMPRE com as credenciais de TESTE (sandbox). Sem Access Token, o
# botão "Pagar com Pix" some e o site avisa que o pagamento está indisponível.
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '').strip()
# Assinatura secreta do webhook, gerada no painel do Mercado Pago (v2 Etapa 7b).
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get('MERCADOPAGO_WEBHOOK_SECRET', '').strip()
# SÓ NO SANDBOX: com "APRO", o Mercado Pago aprova o Pix de teste sozinho.
# Em produção fica VAZIO (aí o site não manda nome nenhum ao gateway).
MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME = os.environ.get('MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME', '').strip()


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
# O logger "pagamentos" escreve no terminal (console). Regra do projeto:
# logs SEM dados pessoais e SEM dados de pagamento. As mensagens levam só
# números de pedido/pagamento e status do gateway; nunca e-mail, valor,
# "copia e cola", token ou corpo de resposta do Mercado Pago.
LOGGING = {
    'version': 1,
    # False: não desliga os logs que o Django já configura sozinho.
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'pagamentos': {'handlers': ['console'], 'level': 'INFO'},
    },
}
