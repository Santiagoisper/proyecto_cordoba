from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('export/visitas/', views.export_visits_csv, name='export_visits_csv'),
    path('auditor/viaticos/', views.auditor_viaticos_dashboard, name='auditor_viaticos'),
    path('auditor/patient/<int:patient_id>/update-cap/', views.update_patient_viatic_cap, name='update_viatic_cap'),
]
