"""
URL configuration for Proyecto Córdoba.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('expenses/', include('apps.expenses.urls')),
    path('patients/', include('apps.patients.urls')),
    path('protocols/', include('apps.protocols.urls')),
    path('reports/', include('apps.reports.urls')),
    path('periods/', include('apps.expenses.period_urls')),
    path('intake/', include('apps.intake.urls')),
    # PWA: el service worker se sirve desde la raíz para tener scope global.
    path('sw.js', TemplateView.as_view(
        template_name='pwa/sw.js',
        content_type='application/javascript',
    ), name='sw'),
    path('offline/', TemplateView.as_view(template_name='pwa/offline.html'), name='offline'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'Proyecto Córdoba — Administración'
admin.site.site_title = 'Proyecto Córdoba'
admin.site.index_title = 'Panel de administración'
