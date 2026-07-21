"""
Production settings for Proyecto Córdoba.
Deploy objetivo: Railway (o cualquier PaaS detrás de proxy TLS).
"""
import environ
from .base import *

env = environ.Env()

DEBUG = False

SECRET_KEY = env('SECRET_KEY')

DATABASES = {
    'default': env.db('DATABASE_URL')
}
# Conexiones persistentes: menos overhead por request contra Postgres gestionado.
DATABASES['default']['CONN_MAX_AGE'] = env.int('CONN_MAX_AGE', default=60)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

# ─── TLS / cookies ────────────────────────────────────────────────────────────
# Detrás del proxy de Railway la request llega por HTTP interno:
# confiar en el header estándar para saber que el cliente vino por HTTPS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_REFERRER_POLICY = 'same-origin'

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# Jornada laboral: la sesión expira a las 12 horas sin importar actividad.
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE', default=12 * 60 * 60)

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# ─── Celery: en producción SIEMPRE con worker real ────────────────────────────
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=False)

# ─── allauth: rate limit de login ─────────────────────────────────────────────
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/5m/ip,10/1h/key',
}
