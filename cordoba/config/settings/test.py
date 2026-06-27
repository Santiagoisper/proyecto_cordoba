"""
Test settings for Proyecto Cordoba.
Uses SQLite by default so the local test suite does not require PostgreSQL.
"""
from .base import *

DEBUG = False
SECRET_KEY = 'django-insecure-test-key'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

CELERY_TASK_ALWAYS_EAGER = True
