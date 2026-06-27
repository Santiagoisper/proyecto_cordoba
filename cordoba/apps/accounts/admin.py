from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Información del site', {
            'fields': ('site_name', 'phone', 'external_id'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Información del site', {
            'fields': ('site_name', 'phone'),
        }),
    )
    list_display = ['username', 'email', 'get_full_name', 'site_name', 'role_display', 'is_active']
    list_filter = ['groups', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'site_name']

    def role_display(self, obj):
        return obj.role_display
    role_display.short_description = 'Rol'
