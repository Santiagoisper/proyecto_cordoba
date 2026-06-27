from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # Asistente — carga y revisión
    path('', views.expense_list, name='list'),
    path('new/', views.expense_create, name='create'),
    path('<int:pk>/review/', views.expense_review, name='review'),
    path('<int:pk>/detail/', views.expense_detail, name='detail'),
    path('<int:pk>/correct/', views.expense_correct, name='correct'),

    # Coordinador — acciones HTMX
    path('<int:pk>/approve/', views.approve_expense, name='approve'),
    path('<int:pk>/reject/', views.reject_expense, name='reject'),
    path('<int:pk>/observe/', views.observe_expense, name='observe'),
    path('<int:pk>/modal/<str:action>/', views.action_modal, name='action_modal'),

    # HTMX chained selects
    path('htmx/patients/', views.htmx_patients_for_protocol, name='htmx_patients'),
    path('htmx/visits/', views.htmx_visits_for_patient, name='htmx_visits'),
    path('htmx/protocol-info/', views.htmx_protocol_info, name='htmx_protocol_info'),
]
