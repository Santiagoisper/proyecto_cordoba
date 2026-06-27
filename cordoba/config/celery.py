"""
Configuración de Celery para Proyecto Córdoba.
En desarrollo (DEBUG=True) las tareas se ejecutan de forma síncrona (TASK_ALWAYS_EAGER).
En producción se requiere un worker Celery y un broker Redis real.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('proyecto_cordoba')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
