"""
URL configuration for Proyecto Córdoba.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('expenses/', include('apps.expenses.urls')),
    path('patients/', include('apps.patients.urls')),
    path('protocols/', include('apps.protocols.urls')),
    path('reports/', include('apps.reports.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'Proyecto Córdoba — Administración'
admin.site.site_title = 'Proyecto Córdoba'
admin.site.index_title = 'Panel de administración'
