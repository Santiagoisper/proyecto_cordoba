from django.contrib import admin

from .models import ChannelContact, InboundMessage


@admin.register(ChannelContact)
class ChannelContactAdmin(admin.ModelAdmin):
    list_display = ['phone', 'display_name', 'site', 'channel', 'is_active', 'created_at']
    list_filter = ['channel', 'is_active', 'site']
    search_fields = ['phone', 'display_name']
    readonly_fields = ['created_at']


@admin.register(InboundMessage)
class InboundMessageAdmin(admin.ModelAdmin):
    list_display = ['external_id', 'channel', 'sender', 'message_type', 'status', 'received_at']
    list_filter = ['channel', 'status', 'message_type']
    search_fields = ['external_id', 'sender']
    readonly_fields = [
        'channel', 'external_id', 'sender', 'message_type', 'payload',
        'status', 'error', 'reception_ticket', 'received_at', 'processed_at',
    ]
    date_hierarchy = 'received_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
