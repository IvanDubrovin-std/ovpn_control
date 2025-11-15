"""
Django admin configuration for OpenVPN management
"""

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    CertificateAuthority,
    ClientCertificate,
    OpenVPNServer,
    ServerTask,
    VPNConnection,
)


class OpenVPNServerAdminForm(forms.ModelForm):
    """Custom form for OpenVPN Server with secure private key handling"""

    # Optional field for uploading new SSH key (not bound to model field)
    new_ssh_private_key = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "cols": 80,
                "placeholder": "Вставьте новый SSH приватный ключ здесь...",
            }
        ),
        required=False,
        label="Новый SSH приватный ключ",
        help_text="Вставьте содержимое приватного SSH ключа (будет заменен существующий). Оставьте пустым, чтобы сохранить текущий ключ.",
    )

    class Meta:
        model = OpenVPNServer
        exclude = ["ssh_private_key"]  # Exclude to prevent displaying
        widgets = {
            "ssh_password": forms.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure new_ssh_private_key is always empty (never populate with existing key)
        self.initial["new_ssh_private_key"] = ""
        # Store original private key to preserve it if not updating
        if self.instance and self.instance.pk:
            self._original_ssh_private_key = self.instance.ssh_private_key
        else:
            self._original_ssh_private_key = None

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Update SSH private key if new one provided
        new_key = self.cleaned_data.get("new_ssh_private_key")
        if new_key and new_key.strip():
            # User provided new key - update it
            instance.ssh_private_key = new_key.strip()
        else:
            # No new key provided - preserve original
            if hasattr(self, "_original_ssh_private_key"):
                instance.ssh_private_key = self._original_ssh_private_key

        if commit:
            instance.save()
        return instance


@admin.register(OpenVPNServer)
class OpenVPNServerAdmin(admin.ModelAdmin):
    form = OpenVPNServerAdminForm

    list_display = [
        "name",
        "host",
        "status",
        "openvpn_port",
        "openvpn_protocol",
        "use_stunnel_display",
        "client_count",
        "last_check",
        "created_at",
    ]
    list_filter = ["status", "openvpn_protocol", "use_stunnel", "created_at"]
    search_fields = ["name", "host", "description"]
    readonly_fields = ["created_at", "updated_at", "last_check", "ssh_key_display"]

    fieldsets = (
        ("Основная информация", {"fields": ("name", "description", "status", "created_by")}),
        (
            "Подключение к серверу",
            {
                "fields": (
                    "host",
                    "ssh_port",
                    "ssh_username",
                    "ssh_password",
                    "ssh_key_path",
                    "ssh_key_display",
                    "new_ssh_private_key",
                )
            },
        ),
        (
            "OpenVPN настройки",
            {
                "fields": (
                    "openvpn_port",
                    "openvpn_protocol",
                    "server_subnet",
                    "server_netmask",
                    "dns_servers",
                )
            },
        ),
        (
            "Stunnel настройки",
            {
                "fields": ("use_stunnel", "stunnel_port", "stunnel_enabled"),
                "classes": ("collapse",),
            },
        ),
        (
            "Метаданные",
            {"fields": ("created_at", "updated_at", "last_check"), "classes": ("collapse",)},
        ),
    )

    def use_stunnel_display(self, obj):
        if obj.use_stunnel:
            status_text = "✓ Включен"
            if obj.stunnel_enabled:
                return format_html(
                    '<span style="color: green;">{}</span> (порт: {})',
                    status_text,
                    obj.stunnel_port,
                )
            else:
                return format_html(
                    '<span style="color: orange;">{}</span> (не запущен)', status_text
                )
        return format_html('<span style="color: gray;">✗ Отключен</span>')

    use_stunnel_display.short_description = "Stunnel"  # type: ignore[attr-defined]

    def ssh_key_display(self, obj):
        """Display SSH key status without showing the actual key"""
        if obj.ssh_private_key:
            key_length = len(obj.ssh_private_key)
            return format_html(
                '<span style="color: green;">✓ SSH ключ загружен</span> ({} символов)',
                key_length,
            )
        return format_html('<span style="color: gray;">✗ SSH ключ не загружен</span>')

    ssh_key_display.short_description = "SSH приватный ключ"  # type: ignore[attr-defined]

    def client_count(self, obj):
        count = obj.clients.count()
        if count > 0:
            url = reverse("admin:ovpn_app_clientcertificate_changelist")
            return format_html(
                '<a href="{}?server__id__exact={}">{} клиентов</a>', url, obj.id, count
            )
        return "0 клиентов"

    client_count.short_description = "Клиенты"  # type: ignore[attr-defined]

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CertificateAuthority)
class CertificateAuthorityAdmin(admin.ModelAdmin):
    list_display = [
        "server",
        "organization",
        "country",
        "created_at",
        "expires_at",
        "is_valid_status",
    ]
    list_filter = ["country", "created_at"]
    search_fields = ["server__name", "organization", "email"]
    readonly_fields = ["created_at", "expires_at"]

    def is_valid_status(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Действителен</span>')
        else:
            return format_html('<span style="color: red;">✗ Истёк</span>')

    is_valid_status.short_description = "Статус"  # type: ignore[attr-defined]


@admin.register(ClientCertificate)
class ClientCertificateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "server",
        "status",
        "email",
        "created_at",
        "expires_at",
        "is_valid_status",
        "created_by",
    ]
    list_filter = ["status", "server", "created_at"]
    search_fields = ["name", "email", "server__name"]
    readonly_fields = ["created_at", "expires_at", "revoked_at"]

    fieldsets = (
        ("Информация о клиенте", {"fields": ("name", "email", "description", "server")}),
        ("Статус сертификата", {"fields": ("status", "created_at", "expires_at", "revoked_at")}),
        ("Сертификат и ключ", {"fields": ("client_cert", "client_key"), "classes": ("collapse",)}),
        (
            "Метаданные",
            {
                "fields": ("created_by",),
            },
        ),
    )

    def is_valid_status(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Действителен</span>')
        else:
            return format_html('<span style="color: red;">✗ Недействителен</span>')

    is_valid_status.short_description = "Статус"  # type: ignore[attr-defined]

    actions = ["revoke_certificates"]

    def revoke_certificates(self, request, queryset):
        count = 0
        for cert in queryset.filter(status="active"):
            cert.revoke()
            count += 1

        self.message_user(request, f"Отозвано {count} сертификатов.")

    revoke_certificates.short_description = "Отозвать выбранные сертификаты"  # type: ignore[attr-defined]


@admin.register(VPNConnection)
class VPNConnectionAdmin(admin.ModelAdmin):
    list_display = [
        "client",
        "client_ip",
        "virtual_ip",
        "connected_at",
        "duration_display",
        "bytes_received_display",
        "bytes_sent_display",
    ]
    list_filter = ["connected_at", "client__server"]
    search_fields = ["client__name", "client_ip", "virtual_ip"]
    readonly_fields = ["connected_at", "last_seen"]

    def duration_display(self, obj):
        duration = obj.duration()
        hours = duration.total_seconds() // 3600
        minutes = (duration.total_seconds() % 3600) // 60
        return f"{int(hours)}ч {int(minutes)}м"

    duration_display.short_description = "Время подключения"  # type: ignore[attr-defined]

    def bytes_received_display(self, obj):
        return obj.format_bytes(obj.bytes_received)

    bytes_received_display.short_description = "Получено"  # type: ignore[attr-defined]

    def bytes_sent_display(self, obj):
        return obj.format_bytes(obj.bytes_sent)

    bytes_sent_display.short_description = "Отправлено"  # type: ignore[attr-defined]


@admin.register(ServerTask)
class ServerTaskAdmin(admin.ModelAdmin):
    list_display = [
        "task_type",
        "server",
        "status",
        "progress",
        "created_at",
        "started_at",
        "completed_at",
        "created_by",
    ]
    list_filter = ["task_type", "status", "created_at"]
    search_fields = ["server__name", "task_id"]
    readonly_fields = ["task_id", "created_at", "started_at", "completed_at"]

    fieldsets = (
        (
            "Информация о задаче",
            {"fields": ("task_type", "server", "status", "progress", "task_id")},
        ),
        (
            "Параметры и результат",
            {"fields": ("parameters", "result", "error_message"), "classes": ("collapse",)},
        ),
        ("Временные метки", {"fields": ("created_at", "started_at", "completed_at", "created_by")}),
    )


# Customize admin site headers
admin.site.site_header = "OpenVPN Management System"
admin.site.site_title = "OpenVPN Admin"
admin.site.index_title = "Добро пожаловать в систему управления OpenVPN"
