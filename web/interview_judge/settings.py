"""
Django settings for interview-judge.

Patch #4 (Plan iter-2): redis URLs read from env vars with NO DEFAULTS.
Missing values must crash at startup — this prevents the silent
misconfiguration class of bugs where redis-channels and redis-judge0 get
collapsed by accident.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root


def _required(name: str) -> str:
    """Read env var or raise — used for credentials we refuse to default."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Required env var {name!r} is not set. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


# --- core ---
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-do-not-use-in-prod")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

ROOT_URLCONF = "web.interview_judge.urls"
ASGI_APPLICATION = "web.interview_judge.asgi.application"

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "django_q",
    # local apps
    "web.apps.core",
    "web.apps.judging",  # Step 3
    "web.apps.interviewer",  # Step 4
    "web.apps.candidate",  # Step 5
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # i18n: must sit after SessionMiddleware so language can be persisted
    # in the session, and before CommonMiddleware so URL prefixes resolve.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "interview_judge"),
        "USER": os.environ.get("POSTGRES_USER", "interview_judge"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# --- redis (Patch #4: NO DEFAULTS) ---
CHANNELS_REDIS_URL = _required("CHANNELS_REDIS_URL")
JUDGE0_REDIS_URL = _required("JUDGE0_REDIS_URL")

# Compile-time guard: explicit identity check — sharing channels-redis with
# Judge0 is forbidden by Plan §3.5. Identical URLs are a misconfiguration.
if CHANNELS_REDIS_URL == JUDGE0_REDIS_URL:
    raise RuntimeError(
        "CHANNELS_REDIS_URL and JUDGE0_REDIS_URL must be different. "
        "Sharing them couples our real-time SLO to Judge0's queue depth "
        "(see docs/architecture.md and Plan §3.5)."
    )

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CHANNELS_REDIS_URL]},
    },
}

# --- django-q2 (scheduler runs OUT-OF-PROCESS — Plan REV-1) ---
Q_CLUSTER = {
    "name": "interview_judge",
    "workers": 2,
    "recycle": 500,
    "timeout": 60,
    "retry": 90,
    "compress": True,
    "save_limit": 1000,
    "queue_limit": 500,
    "cpu_affinity": 1,
    "label": "Django Q2",
    "orm": "default",  # Postgres jobstore — Plan REV-1
}

# --- judge0 ---
JUDGE0_BASE_URL = os.environ.get("JUDGE0_BASE_URL", "http://judge0-server:2358")
JUDGE0_CALLBACK_BASE_URL = os.environ.get("JUDGE0_CALLBACK_BASE_URL", "http://web:8000")
JUDGE0_CALLBACK_HMAC_SECRET = os.environ.get("JUDGE0_CALLBACK_HMAC_SECRET", "")

# --- session cookie (Patch: token vs cookie separation, Plan REV-4) ---
INTERVIEW_SESSION_COOKIE_NAME = os.environ.get(
    "INTERVIEW_SESSION_COOKIE_NAME", "interview_session"
)
INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS = int(
    os.environ.get("INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS", "18000")
)

# --- i18n / static / etc. ---
# Default language; LocaleMiddleware overrides per-request based on user
# preference (session > cookie > Accept-Language header).
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("zh-hant", "繁體中文"),
]
LOCALE_PATHS = [BASE_DIR / "web" / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "web" / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth — interviewers reuse Django admin login (already wired at /admin/login/).
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
