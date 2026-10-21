"""Configuração do projeto. Valores sensíveis vêm de variáveis de ambiente (ver .env.example)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("DET_DEBUG", True)
SECRET_KEY = env("DET_SECRET_KEY", "dev-insecure-troque-em-producao")
if not DEBUG and SECRET_KEY.startswith("dev-insecure"):
    raise RuntimeError("Defina DET_SECRET_KEY quando DET_DEBUG=False.")
ALLOWED_HOSTS = [h for h in env("DET_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DET_CSRF_TRUSTED_ORIGINS", "").split(",") if o]
# Render informa o domínio público do serviço; libera host e origem do CSRF automaticamente.
_host_render = env("RENDER_EXTERNAL_HOSTNAME")
if _host_render:
    ALLOWED_HOSTS.append(_host_render)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_host_render}")

# Carga de dados demo fora do modo debug (ex.: link de teste online). Desligada por padrão.
PERMITIR_DEMO = env_bool("DET_PERMITIR_DEMO", False)
DEMO_SENHA = env("DET_DEMO_SENHA", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite por padrão; para PostgreSQL defina DET_DB_ENGINE=postgresql e as demais DET_DB_*.
if env("DET_DB_ENGINE", "sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DET_DB_NAME", "det"),
            "USER": env("DET_DB_USER", "det"),
            "PASSWORD": env("DET_DB_PASSWORD", ""),
            "HOST": env("DET_DB_HOST", "localhost"),
            "PORT": env("DET_DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DET_SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_USER_MODEL = "core.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Anexos podem ter dados pessoais: ficam fora de qualquer pasta pública e só saem por view autenticada.
MEDIA_ROOT = Path(env("DET_MEDIA_ROOT", str(BASE_DIR / "anexos_privados")))
ANEXO_MAX_MB = int(env("DET_ANEXO_MAX_MB", "10"))
ANEXO_EXTENSOES = (".pdf", ".png", ".jpg", ".jpeg")
DATA_UPLOAD_MAX_MEMORY_SIZE = ANEXO_MAX_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = ANEXO_MAX_MB * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Itens por página nas listas (paginação no servidor).
PAGE_SIZE = int(env("DET_PAGE_SIZE", "20"))

# E-mail: console em desenvolvimento, SMTP quando DET_EMAIL_HOST estiver definido.
if env("DET_EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("DET_EMAIL_HOST")
    EMAIL_PORT = int(env("DET_EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("DET_EMAIL_USER", "")
    EMAIL_HOST_PASSWORD = env("DET_EMAIL_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("DET_EMAIL_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DET_EMAIL_FROM", "det-controle@instituto.local")

# Regras dos alertas (usadas por `manage.py enviar_alertas`).
ALERTA_DIA_LEMBRETE_MENSAL = int(env("DET_ALERTA_DIA_MES", "5"))
ALERTA_DIAS_ANTES_PRAZO = [int(x) for x in env("DET_ALERTA_DIAS_PRAZO", "5,2").split(",") if x]

if not DEBUG:
    # Atrás de proxy HTTPS (Render, nginx, IIS): confia no cabeçalho para evitar loop de redirecionamento.
    if env_bool("DET_PROXY_SSL", True):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DET_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 3600
