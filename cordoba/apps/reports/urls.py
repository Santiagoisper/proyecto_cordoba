from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),

    # Descargas — POST obligatorio (mutación de estado + CSRF)
    path('patient-pdf/', views.patient_pdf, name='patient_pdf'),
    path('site-pdf/', views.site_pdf, name='site_pdf'),
    path('site-excel/', views.site_excel, name='site_excel'),
    path('visit-pdf/', views.visit_pdf, name='visit_pdf'),

    # HTMX chained selects (GET, solo lectura, sin mutación)
    path('htmx/periods/', views.htmx_periods_for_protocol, name='htmx_periods'),
    path('htmx/patients/', views.htmx_patients_for_protocol, name='htmx_patients'),
    path('htmx/patient-periods/', views.htmx_periods_for_patient, name='htmx_patient_periods'),
    path('htmx/visit-types/', views.htmx_visit_types_for_protocol, name='htmx_visit_types'),
]
