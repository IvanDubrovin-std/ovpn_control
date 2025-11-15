"""
Django models for OpenVPN management system
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class OpenVPNServer(models.Model):
    """OpenVPN Server model"""

    STATUS_CHOICES = [
        ("pending", "Pending Installation"),
        ("installing", "Installing"),
        ("installed", "Installed"),
        ("running", "Running"),
        ("stopped", "Stopped"),
        ("error", "Error"),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Имя сервера")
    description = models.TextField(blank=True, verbose_name="Описание")

    # Server connection details
    host = models.GenericIPAddressField(protocol="IPv4", verbose_name="IP адрес")
    ssh_port = models.PositiveIntegerField(default=22, verbose_name="SSH порт")
    ssh_username = models.CharField(max_length=50, verbose_name="SSH пользователь")
    ssh_password = models.CharField(max_length=255, blank=True, verbose_name="SSH пароль")
    ssh_key_path = models.CharField(max_length=500, blank=True, verbose_name="Путь к SSH ключу")
    ssh_private_key = models.TextField(blank=True, verbose_name="SSH приватный ключ")

    # OpenVPN configuration
    openvpn_port = models.PositiveIntegerField(default=1194, verbose_name="OpenVPN порт")
    openvpn_protocol = models.CharField(
        max_length=3,
        choices=[("udp", "UDP"), ("tcp", "TCP")],
        default="udp",
        verbose_name="Протокол",
    )
    server_subnet = models.GenericIPAddressField(
        protocol="IPv4", default="10.8.0.0", verbose_name="Подсеть сервера"
    )
    server_netmask = models.GenericIPAddressField(
        protocol="IPv4", default="255.255.255.0", verbose_name="Маска подсети"
    )
    dns_servers = models.JSONField(
        default=list, verbose_name="DNS серверы", help_text="Список DNS серверов в формате JSON"
    )

    # Server status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )
    last_check = models.DateTimeField(null=True, blank=True, verbose_name="Последняя проверка")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Создал")

    class Meta:
        verbose_name = "OpenVPN Сервер"
        verbose_name_plural = "OpenVPN Серверы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.host})"

    def get_dns_servers_list(self):
        """Get DNS servers as a list"""
        if isinstance(self.dns_servers, list):
            return self.dns_servers
        return ["8.8.8.8", "8.8.4.4"]

    def is_accessible(self):
        """Check if server is accessible via SSH"""
        # This will be implemented in the SSH manager
        return self.status not in ["error", "pending"]


class CertificateAuthority(models.Model):
    """Certificate Authority model"""

    server = models.OneToOneField(
        OpenVPNServer, on_delete=models.CASCADE, related_name="ca", verbose_name="Сервер"
    )

    # CA Details
    country = models.CharField(max_length=2, default="RU", verbose_name="Страна")
    state = models.CharField(max_length=100, default="Moscow", verbose_name="Область")
    city = models.CharField(max_length=100, default="Moscow", verbose_name="Город")
    organization = models.CharField(max_length=100, verbose_name="Организация")
    email = models.EmailField(verbose_name="Email")

    # CA Certificate data
    ca_cert = models.TextField(verbose_name="CA сертификат")
    ca_key = models.TextField(verbose_name="CA ключ")

    # Status
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    expires_at = models.DateTimeField(verbose_name="Истекает")

    class Meta:
        verbose_name = "Центр Сертификации"
        verbose_name_plural = "Центры Сертификации"

    def __str__(self):
        return f"CA для {self.server.name}"

    def is_valid(self):
        """Check if CA certificate is still valid"""
        return timezone.now() < self.expires_at


class ClientCertificate(models.Model):
    """Client Certificate model"""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]

    server = models.ForeignKey(
        OpenVPNServer, on_delete=models.CASCADE, related_name="clients", verbose_name="Сервер"
    )

    # Client details
    name = models.CharField(max_length=100, verbose_name="Имя клиента")
    email = models.EmailField(blank=True, verbose_name="Email клиента")
    description = models.TextField(blank=True, verbose_name="Описание")

    # Certificate data
    client_cert = models.TextField(verbose_name="Клиентский сертификат")
    client_key = models.TextField(verbose_name="Клиентский ключ")

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="Статус"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    expires_at = models.DateTimeField(verbose_name="Истекает")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Отозван")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Создал")

    class Meta:
        verbose_name = "Клиентский Сертификат"
        verbose_name_plural = "Клиентские Сертификаты"
        unique_together = ["server", "name"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.server.name})"

    def revoke(self):
        """Revoke the certificate"""
        self.status = "revoked"
        self.revoked_at = timezone.now()
        self.save()

    def is_valid(self):
        """Check if certificate is valid"""
        now = timezone.now()
        return self.status == "active" and now < self.expires_at and not self.revoked_at

    def generate_config(self):
        """Generate OpenVPN client configuration"""
        config = f"""client
dev tun
proto {self.server.openvpn_protocol}
remote {self.server.host} {self.server.openvpn_port}
resolv-retry infinite
nobind
user nobody
group nogroup
persist-key
persist-tun
verb 3
cipher AES-256-CBC
auth SHA256
key-direction 1

<ca>
{self.server.ca.ca_cert}
</ca>

<cert>
{self.client_cert}
</cert>

<key>
{self.client_key}
</key>
"""
        return config


class VPNConnection(models.Model):
    """Active VPN Connection model"""

    client = models.ForeignKey(
        ClientCertificate,
        on_delete=models.CASCADE,
        related_name="connections",
        verbose_name="Клиент",
    )

    # Connection details
    client_ip = models.GenericIPAddressField(protocol="IPv4", verbose_name="IP клиента")
    virtual_ip = models.GenericIPAddressField(protocol="IPv4", verbose_name="Виртуальный IP")

    # Connection stats
    bytes_received = models.BigIntegerField(default=0, verbose_name="Получено байт")
    bytes_sent = models.BigIntegerField(default=0, verbose_name="Отправлено байт")

    # Timestamps
    connected_at = models.DateTimeField(default=timezone.now, verbose_name="Подключен")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")

    class Meta:
        verbose_name = "VPN Подключение"
        verbose_name_plural = "VPN Подключения"
        ordering = ["-connected_at"]

    def __str__(self):
        return f"{self.client.name} ({self.client_ip})"

    def duration(self):
        """Get connection duration"""
        return timezone.now() - self.connected_at

    def format_duration(self):
        """Format duration in human readable format"""
        duration = self.duration()

        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def format_bytes(self, bytes_count):
        """Format bytes in human readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_count < 1024:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024
        return f"{bytes_count:.2f} TB"


class ServerTask(models.Model):
    """Background task tracking model"""

    TASK_TYPES = [
        ("install", "Install OpenVPN"),
        ("configure", "Configure Server"),
        ("create_client", "Create Client"),
        ("revoke_client", "Revoke Client"),
        ("check_status", "Check Status"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    server = models.ForeignKey(
        OpenVPNServer, on_delete=models.CASCADE, related_name="tasks", verbose_name="Сервер"
    )

    task_type = models.CharField(max_length=20, choices=TASK_TYPES, verbose_name="Тип задачи")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )

    # Task details
    task_id = models.CharField(max_length=255, unique=True, verbose_name="ID задачи")
    parameters = models.JSONField(default=dict, verbose_name="Параметры")
    result = models.JSONField(default=dict, blank=True, verbose_name="Результат")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")

    # Progress tracking
    progress = models.PositiveIntegerField(default=0, verbose_name="Прогресс (%)")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Начато")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершено")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Создал")

    class Meta:
        verbose_name = "Задача Сервера"
        verbose_name_plural = "Задачи Серверов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.server.name}"

    def mark_completed(self, result=None):
        """Mark task as completed"""
        self.status = "completed"
        self.progress = 100
        self.completed_at = timezone.now()
        if result:
            self.result = result
        self.save()

    def mark_failed(self, error_message):
        """Mark task as failed"""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()
