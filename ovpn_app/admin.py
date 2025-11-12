"""
Django admin configuration for OpenVPN management
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import (
    OpenVPNServer, CertificateAuthority, ClientCertificate, 
    VPNConnection, ServerTask
)


@admin.register(OpenVPNServer)
class OpenVPNServerAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'host', 'status', 'openvpn_port', 'openvpn_protocol',
        'client_count', 'last_check', 'created_at'
    ]
    list_filter = ['status', 'openvpn_protocol', 'created_at']
    search_fields = ['name', 'host', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_check']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'status', 'created_by')
        }),
        ('Подключение к серверу', {
            'fields': ('host', 'ssh_port', 'ssh_username', 'ssh_password', 'ssh_key_path')
        }),
        ('OpenVPN настройки', {
            'fields': ('openvpn_port', 'openvpn_protocol', 'server_subnet', 'server_netmask', 'dns_servers')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at', 'last_check'),
            'classes': ('collapse',)
        }),
    )
    
    def client_count(self, obj):
        count = obj.clients.count()
        if count > 0:
            url = reverse('admin:ovpn_app_clientcertificate_changelist')
            return format_html(
                '<a href="{}?server__id__exact={}">{} клиентов</a>',
                url, obj.id, count
            )
        return '0 клиентов'
    client_count.short_description = 'Клиенты'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CertificateAuthority)
class CertificateAuthorityAdmin(admin.ModelAdmin):
    list_display = ['server', 'organization', 'country', 'created_at', 'expires_at', 'is_valid_status']
    list_filter = ['country', 'created_at']
    search_fields = ['server__name', 'organization', 'email']
    readonly_fields = ['created_at', 'expires_at']
    
    def is_valid_status(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Действителен</span>')
        else:
            return format_html('<span style="color: red;">✗ Истёк</span>')
    is_valid_status.short_description = 'Статус'


@admin.register(ClientCertificate)
class ClientCertificateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'server', 'status', 'email', 'created_at', 
        'expires_at', 'is_valid_status', 'created_by'
    ]
    list_filter = ['status', 'server', 'created_at']
    search_fields = ['name', 'email', 'server__name']
    readonly_fields = ['created_at', 'expires_at', 'revoked_at']
    
    fieldsets = (
        ('Информация о клиенте', {
            'fields': ('name', 'email', 'description', 'server')
        }),
        ('Статус сертификата', {
            'fields': ('status', 'created_at', 'expires_at', 'revoked_at')
        }),
        ('Сертификат и ключ', {
            'fields': ('client_cert', 'client_key'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_by',),
        }),
    )
    
    def is_valid_status(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Действителен</span>')
        else:
            return format_html('<span style="color: red;">✗ Недействителен</span>')
    is_valid_status.short_description = 'Статус'
    
    actions = ['revoke_certificates']
    
    def revoke_certificates(self, request, queryset):
        count = 0
        for cert in queryset.filter(status='active'):
            cert.revoke()
            count += 1
        
        self.message_user(request, f'Отозвано {count} сертификатов.')
    revoke_certificates.short_description = 'Отозвать выбранные сертификаты'


@admin.register(VPNConnection)
class VPNConnectionAdmin(admin.ModelAdmin):
    list_display = [
        'client', 'client_ip', 'virtual_ip', 'connected_at', 
        'duration_display', 'bytes_received_display', 'bytes_sent_display'
    ]
    list_filter = ['connected_at', 'client__server']
    search_fields = ['client__name', 'client_ip', 'virtual_ip']
    readonly_fields = ['connected_at', 'last_seen']
    
    def duration_display(self, obj):
        duration = obj.duration()
        hours = duration.total_seconds() // 3600
        minutes = (duration.total_seconds() % 3600) // 60
        return f"{int(hours)}ч {int(minutes)}м"
    duration_display.short_description = 'Время подключения'
    
    def bytes_received_display(self, obj):
        return obj.format_bytes(obj.bytes_received)
    bytes_received_display.short_description = 'Получено'
    
    def bytes_sent_display(self, obj):
        return obj.format_bytes(obj.bytes_sent)
    bytes_sent_display.short_description = 'Отправлено'


@admin.register(ServerTask)
class ServerTaskAdmin(admin.ModelAdmin):
    list_display = [
        'task_type', 'server', 'status', 'progress', 'created_at', 
        'started_at', 'completed_at', 'created_by'
    ]
    list_filter = ['task_type', 'status', 'created_at']
    search_fields = ['server__name', 'task_id']
    readonly_fields = ['task_id', 'created_at', 'started_at', 'completed_at']
    
    fieldsets = (
        ('Информация о задаче', {
            'fields': ('task_type', 'server', 'status', 'progress', 'task_id')
        }),
        ('Параметры и результат', {
            'fields': ('parameters', 'result', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'started_at', 'completed_at', 'created_by')
        }),
    )


# Customize admin site headers
admin.site.site_header = "OpenVPN Management System"
admin.site.site_title = "OpenVPN Admin"
admin.site.index_title = "Добро пожаловать в систему управления OpenVPN"
