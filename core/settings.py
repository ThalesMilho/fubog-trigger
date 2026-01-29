from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url 

# Carrega variáveis do .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURANÇA: Nunca deixe a chave vazia em produção
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-chave-padrao-apenas-para-dev')

# QA: DEBUG deve ser False em prod, mas True para seu colega testar o QR Code localmente
DEBUG = 'RENDER' not in os.environ

# SECURITY: Permite qualquer host se DEBUG=True, ou define domínios específicos
ALLOWED_HOSTS = ['*'] 

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'trigger',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Recomendado para estáticos em prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <--- AQUI
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# DATABASE CONFIGURATION
# ------------------------------------------------------------------------------
# Se existir a variável DATABASE_URL (na nuvem), usa ela. 
# Se não, usa o banco local (sqlite ou postgres local) para desenvolvimento.

DATABASES = {
    'default': dj_database_url.config(
        default='postgres://postgres:lya100104@localhost:5432/sistemabicho',
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalização ajustada para Brasil
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# STATIC FILES CONFIGURATION
# ------------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') # Onde o Render vai juntar os arquivos

# Ativa a compressão e cache eficiente de estáticos (Whitenoise)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Expira a sessão do usuário após 1200 segundos (20 minutos) de inatividade.
SESSION_COOKIE_AGE = 20 * 60 

# Faz com que a sessão expire quando o navegador for fechado
SESSION_EXPIRE_AT_BROWSER_CLOSE = True