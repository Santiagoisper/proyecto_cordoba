from django.contrib import admin
from .models import Expense, ExpensePeriod, TicketFile, AuditLog


class TicketFileInline(admin.TabularInline):
    model = TicketFile
    extra = 0
    readonly_fields = ['uploaded_at', 'uploaded_by', 'ocr_status', 'file_size', 'mime_type']
    fields = ['file', 'original_filename', 'ocr_status', 'uploaded_by', 'uploaded_at']


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


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'visit', 'category', 'amount', 'currency',
        'expense_date', 'status', 'submitted_by', 'created_at'
    ]
    list_filter = ['status', 'category', 'currency', 'visit__patient__protocol']
    search_fields = [
        'visit__patient__patient_code',
        'visit__patient__protocol__code',
        'vendor', 'description'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'submitted_by',
        'reviewed_by', 'reviewed_at', 'ocr_raw_data', 'ocr_confidence', 'ocr_processed_at'
    ]
    inlines = [TicketFileInline]
    fieldsets = (
        ('Gasto', {
            'fields': ('visit', 'period', 'category', 'amount', 'currency', 'expense_date', 'vendor', 'description')
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
        'uploaded_at', 'uploaded_by', 'file_size', 'mime_type',
        'ocr_task_id', 'ocr_status',
    ]
    fieldsets = (
        ('Archivo', {
            'fields': ('expense', 'file', 'original_filename', 'file_size', 'mime_type')
        }),
        ('OCR', {
            'fields': ('ocr_status', 'ocr_task_id'),
        }),
        ('Auditoría', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )

    def has_change_permission(self, request, obj=None):
        return False


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
