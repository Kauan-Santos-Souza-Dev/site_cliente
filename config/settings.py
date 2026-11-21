"""
Configurações do projeto Elegância Cristã.

Regra de ouro: nada secreto fica neste arquivo. Senhas e chaves vêm de
variáveis de ambiente, que em desenvolvimento são lidas do arquivo ".env"
(que NÃO vai para o Git). Veja ".env.example" para a lista de variáveis.
"""

import os
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
    'loja',
    'carrinho',
    'pedidos',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Django REST Framework: a API de leitura de produtos (etapa 5).
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Proteção CSRF: exige o token em todo formulário POST.
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
# Validação de senhas (usada pelo admin)
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


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
# Confirmar com a loja antes de publicar.
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'elegancia.crist@gmail.com')
INSTAGRAM_HANDLE = 'elegancia.crista.oficial'
STORE_MOTTO = 'Operando Deus quem impedirá'
