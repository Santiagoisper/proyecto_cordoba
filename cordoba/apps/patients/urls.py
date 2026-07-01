from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('crear/', views.patient_create, name='patient_create'),
    path('<int:pk>/', views.patient_detail, name='patient_detail'),
    path('<int:pk>/editar/', views.patient_edit, name='patient_edit'),
    path('<int:patient_pk>/visita/crear/', views.visit_create, name='visit_create'),
    path('visita/<int:pk>/editar/', views.visit_edit, name='visit_edit'),
]
