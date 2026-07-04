from django.contrib import admin
from .models import Patient, Visit


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0
    fields = ['visit_type', 'scheduled_date', 'actual_date', 'status']
    readonly_fields = []


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = [
        'patient_code', 'initials', 'protocol', 'is_active', 'enrolled_date',
        'viatic_cap', 'total_viaticos', 'created_at',
    ]
    list_filter = ['protocol', 'is_active']
    search_fields = ['patient_code', 'initials', 'protocol__code']
    readonly_fields = ['created_at', 'created_by']
    list_select_related = ['protocol']
    autocomplete_fields = ['protocol']
    inlines = [VisitInline]

    @admin.display(description='Viáticos ejecutados (USD)')
    def total_viaticos(self, obj):
        return obj.get_total_viaticos()
    fieldsets = (
        ('Identificación', {
            'fields': ('protocol', 'patient_code', 'initials', 'is_active', 'enrolled_date'),
            'description': 'NUNCA ingresar el nombre completo del paciente aquí.'
        }),
        ('Integración externa', {
            'fields': ('external_patient_id',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['patient', 'visit_type', 'scheduled_date', 'actual_date', 'status']
    list_filter = ['status', 'patient__protocol', 'visit_type']
    search_fields = ['patient__patient_code', 'visit_type__name']
    date_hierarchy = 'scheduled_date'
    list_select_related = ['patient__protocol', 'visit_type']
    autocomplete_fields = ['patient']
    readonly_fields = ['created_at', 'created_by']
    fieldsets = (
        ('Visita', {
            'fields': ('patient', 'visit_type', 'scheduled_date', 'actual_date', 'status', 'notes')
        }),
        ('Integración externa', {
            'fields': ('external_visit_id',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
