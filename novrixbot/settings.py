"""Configurações do robô de WhatsApp da Novrix Tech.

Tudo o que é segredo ou muda entre ambientes vem de variáveis de ambiente
(no Render: serviço novrix-bot → Environment). Nada de senha no código.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome, padrao=""):
    return os.environ.get(nome, padrao)


SECRET_KEY = env("SECRET_KEY", "dev-apenas-local-troque-em-producao")
DEBUG = env("DEBUG", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "bot",
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

ROOT_URLCONF = "novrixbot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "novrixbot.wsgi.application"

# PostgreSQL no Render (DATABASE_URL); SQLite no computador.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ---------- WhatsApp (API oficial da Meta) ----------
WHATSAPP = {
    # Token de acesso (no começo, o temporário de 24 h; depois, o de usuário do sistema).
    "TOKEN": env("WHATSAPP_TOKEN"),
    # "ID do número de telefone" da tela WhatsApp → Configuração da API.
    "PHONE_NUMBER_ID": env("WHATSAPP_PHONE_NUMBER_ID"),
    # Palavra que você inventa e repete no cadastro do webhook na Meta.
    "VERIFY_TOKEN": env("WHATSAPP_VERIFY_TOKEN"),
    # "Chave secreta do app" (Configurações do app → Básico). Confere que a mensagem veio da Meta.
    "APP_SECRET": env("WHATSAPP_APP_SECRET"),
    "GRAPH_VERSION": env("WHATSAPP_GRAPH_VERSION", "v23.0"),
}

# Por quanto tempo o robô fica quieto numa conversa depois que uma pessoa assume.
PAUSA_HUMANO_HORAS = int(env("PAUSA_HUMANO_HORAS", "24"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
