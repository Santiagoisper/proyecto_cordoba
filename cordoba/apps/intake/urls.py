from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]
