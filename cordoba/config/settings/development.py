"""
Development settings for Proyecto Córdoba.
"""
import environ
from .base import *

env = environ.Env()

DEBUG = True

ALLOWED_HOSTS = ['*']

environ.Env.read_env(BASE_DIR / '.env', overwrite=True)

SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-key-change-in-production-xyz123')

DATABASES = {
    'default': env.db('DATABASE_URL')
}

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['https://*.replit.dev', 'https://*.repl.co', 'https://*.replit.app']
)
