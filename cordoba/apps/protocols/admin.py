from django.contrib import admin
from .models import Protocol, Site, VisitType


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'country', 'is_active', 'contact_name']
    list_filter = ['is_active', 'country', 'city']
    search_fields = ['code', 'name', 'contact_name', 'contact_email']
    fieldsets = (
        ('Identificación', {
            'fields': ('code', 'name', 'is_active')
        }),
        ('Dirección', {
            'fields': ('address', 'city', 'country'),
        }),
        ('Contacto', {
            'fields': ('contact_name', 'contact_email', 'contact_phone'),
        }),
    )


class VisitTypeInline(admin.TabularInline):
    model = VisitType
    extra = 1
    fields = ['name', 'code', 'order', 'window_before_days', 'window_after_days']


@admin.register(Protocol)
class ProtocolAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'sponsor', 'phase', 'currency', 'is_active', 'created_at']
    list_filter = ['is_active', 'currency', 'phase']
    search_fields = ['code', 'name', 'sponsor']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    inlines = [VisitTypeInline]
    fieldsets = (
        ('Identificación', {
            'fields': ('code', 'name', 'sponsor', 'phase', 'is_active', 'site')
        }),
        ('Topes de gastos', {
            'fields': ('currency', 'max_daily_meals', 'max_daily_transport', 'max_daily_accommodation')
        }),
        ('Integración externa', {
            'fields': ('external_protocol_id',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(VisitType)
class VisitTypeAdmin(admin.ModelAdmin):
    list_display = ['protocol', 'name', 'code', 'order', 'window_before_days', 'window_after_days']
    list_filter = ['protocol']
    search_fields = ['name', 'code', 'protocol__code']
    ordering = ['protocol', 'order']
