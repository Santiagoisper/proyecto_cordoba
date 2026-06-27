from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('export/visitas/', views.export_visits_csv, name='export_visits_csv'),
]
