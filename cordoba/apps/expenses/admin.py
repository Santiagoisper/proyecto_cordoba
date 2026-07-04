from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Expense,
    ExpensePeriod,
    ProtocolBudgetItem,
    TicketFile,
    ReceptionTicket,
    AuditLog,
)


def _all_model_fields(model):
    return [field.name for field in model._meta.fields]


def _file_preview(file_field, mime_type=''):
    """Miniatura clickeable del comprobante (o link si es PDF)."""
    if not file_field:
        return '—'
    if 'pdf' in (mime_type or ''):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">📄 Ver PDF</a>', file_field.url
        )
    return format_html(
        '<a href="{0}" target="_blank" rel="noopener">'
        '<img src="{0}" style="max-height:80px;max-width:120px;'
        'border:1px solid #cbd5e1;border-radius:4px;" /></a>',
        file_field.url,
    )


class TicketFileInline(admin.TabularInline):
    model = TicketFile
    extra = 0
    readonly_fields = ['preview', 'uploaded_at', 'uploaded_by', 'ocr_status', 'file_size', 'mime_type']
    fields = ['preview', 'file', 'original_filename', 'ocr_status', 'uploaded_by', 'uploaded_at']

    @admin.display(description='Vista previa')
    def preview(self, obj):
        return _file_preview(obj.file, obj.mime_type)


@admin.register(ExpensePeriod)
class ExpensePeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'protocol', 'date_from', 'date_to', 'status', 'closed_by', 'closed_at']
    list_filter = ['status', 'protocol']
    search_fields = ['name', 'protocol__code']
    readonly_fields = ['created_at', 'created_by', 'closed_by', 'closed_at']
    fieldsets = (
        ('Período', {
            'fields': ('protocol', 'name', 'date_from', 'date_to', 'status')
        }),
        ('Cierre', {
            'fields': ('closed_by', 'closed_at'),
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

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status != 'open':
            readonly.extend(_all_model_fields(self.model))
        return sorted(set(readonly))


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'protocol_code', 'patient_code', 'visit_name', 'category',
        'amount', 'currency', 'amount_usd', 'expense_date', 'status', 'submitted_by',
    ]
    list_filter = ['status', 'category', 'currency', 'visit__patient__protocol']
    search_fields = [
        'visit__patient__patient_code',
        'visit__patient__protocol__code',
        'vendor', 'description'
    ]
    date_hierarchy = 'expense_date'
    list_per_page = 50
    list_select_related = ['visit__patient__protocol', 'visit__visit_type', 'submitted_by']
    autocomplete_fields = ['visit', 'period']

    @admin.display(description='Protocolo', ordering='visit__patient__protocol__code')
    def protocol_code(self, obj):
        return obj.visit.patient.protocol.code

    @admin.display(description='Paciente', ordering='visit__patient__patient_code')
    def patient_code(self, obj):
        return obj.visit.patient.patient_code

    @admin.display(description='Visita', ordering='visit__visit_type__order')
    def visit_name(self, obj):
        return obj.visit.visit_type.name
    readonly_fields = [
        'created_at', 'updated_at', 'submitted_by',
        'reviewed_by', 'reviewed_at', 'ocr_raw_data', 'ocr_confidence', 'ocr_processed_at'
    ]
    inlines = [TicketFileInline]
    fieldsets = (
        ('Gasto', {
            'fields': (
                'visit', 'period', 'category', 'amount', 'currency',
                'exchange_rate_to_usd', 'amount_usd',
                'expense_date', 'vendor', 'description',
            )
        }),
        ('Estado y revisión', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('OCR', {
            'fields': ('ocr_raw_data', 'ocr_confidence', 'ocr_processed_at'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('submitted_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.submitted_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and (
            obj.status in {'settled', 'exported'}
            or (obj.period_id and obj.period.status != 'open')
        ):
            readonly.extend(_all_model_fields(self.model))
        return sorted(set(readonly))


@admin.register(ProtocolBudgetItem)
class ProtocolBudgetItemAdmin(admin.ModelAdmin):
    list_display = ['protocol', 'visit_type', 'category', 'amount_usd', 'created_by', 'created_at']
    list_filter = ['protocol', 'category']
    search_fields = ['protocol__code', 'protocol__name', 'visit_type__name']
    readonly_fields = ['created_by', 'created_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TicketFile)
class TicketFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'expense', 'original_filename', 'ocr_status', 'uploaded_by', 'uploaded_at']
    list_filter = ['ocr_status', 'mime_type']
    search_fields = [
        'expense__visit__patient__patient_code',
        'expense__visit__patient__protocol__code',
        'original_filename',
    ]
    readonly_fields = [
        'preview', 'uploaded_at', 'uploaded_by', 'file_size', 'mime_type',
        'ocr_task_id', 'ocr_status',
    ]
    fieldsets = (
        ('Archivo', {
            'fields': ('preview', 'expense', 'file', 'original_filename', 'file_size', 'mime_type')
        }),
        ('OCR', {
            'fields': ('ocr_status', 'ocr_task_id'),
        }),
        ('Auditoría', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Vista previa')
    def preview(self, obj):
        return _file_preview(obj.file, obj.mime_type)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReceptionTicket)
class ReceptionTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'site', 'original_filename', 'uploaded_by', 'uploaded_at', 'assigned_expense']
    list_filter = ['status', 'site', 'mime_type']
    search_fields = ['original_filename', 'notes', 'assigned_expense__visit__patient__patient_code']
    date_hierarchy = 'uploaded_at'
    readonly_fields = [
        'preview', 'uploaded_at', 'uploaded_by', 'file_size', 'mime_type',
        'assigned_expense', 'assigned_by', 'assigned_at',
    ]

    @admin.display(description='Vista previa')
    def preview(self, obj):
        return _file_preview(obj.file, obj.mime_type)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'content_type', 'object_id', 'ip_address']
    list_filter = ['action', 'content_type']
    search_fields = ['user__username', 'object_repr', 'action']
    readonly_fields = [
        'user', 'action', 'timestamp', 'content_type',
        'object_id', 'object_repr', 'details', 'ip_address'
    ]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
