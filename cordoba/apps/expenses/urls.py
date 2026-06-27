from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list, name='list'),
    path('new/', views.expense_create, name='create'),
    path('<int:pk>/review/', views.expense_review, name='review'),

    # HTMX endpoints
    path('htmx/patients/', views.htmx_patients_for_protocol, name='htmx_patients'),
    path('htmx/visits/', views.htmx_visits_for_patient, name='htmx_visits'),
]
