"""
Production settings for Proyecto Córdoba.
"""
import environ
from .base import *

env = environ.Env()

DEBUG = False

SECRET_KEY = env('SECRET_KEY')

DATABASES = {
    'default': env.db('DATABASE_URL')
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
