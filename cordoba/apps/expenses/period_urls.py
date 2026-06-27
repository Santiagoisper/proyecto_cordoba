from django.urls import path
from . import views

app_name = 'periods'

urlpatterns = [
    path('', views.period_list, name='list'),
    path('<int:pk>/close/', views.close_period_view, name='close'),
]
