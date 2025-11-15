"""
Application Constants and Configuration

Centralizes all magic numbers and strings following Clean Code principles.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SSHConfig:
    """SSH connection configuration constants"""

    DEFAULT_PORT: Final[int] = 22
    DEFAULT_TIMEOUT: Final[int] = 30  # seconds
    CONNECTION_RETRY_DELAY: Final[int] = 5  # seconds
    MAX_RETRIES: Final[int] = 3
    COMMAND_TIMEOUT: Final[int] = 60  # seconds


@dataclass(frozen=True)
class OpenVPNPaths:
    """OpenVPN file system paths"""

    # Directories
    CONFIG_DIR: Final[str] = "/etc/openvpn"
    SERVER_CONFIG_DIR: Final[str] = "/etc/openvpn/server"
    EASY_RSA_DIR: Final[str] = "/etc/openvpn/easy-rsa"
    LOG_DIR: Final[str] = "/var/log/openvpn"

    # Files
    SERVER_CONFIG: Final[str] = "/etc/openvpn/server/server.conf"
    STATUS_LOG: Final[str] = "/var/log/openvpn/openvpn-status.log"
    IPS_PERSIST: Final[str] = "/var/log/openvpn/ipp.txt"

    # Easy-RSA paths
    EASY_RSA_PKI: Final[str] = "/etc/openvpn/easy-rsa/pki"
    EASY_RSA_CA_CERT: Final[str] = "/etc/openvpn/easy-rsa/pki/ca.crt"
    EASY_RSA_DH_PARAMS: Final[str] = "/etc/openvpn/easy-rsa/pki/dh.pem"


@dataclass(frozen=True)
class OpenVPNServices:
    """OpenVPN systemd service names"""

    SERVER_UNIT: Final[str] = "openvpn-server@server"
    LEGACY_UNIT: Final[str] = "openvpn@server"


@dataclass(frozen=True)
class OpenVPNDefaults:
    """OpenVPN default configuration values"""

    # Network
    DEFAULT_PORT: Final[int] = 1194
    DEFAULT_PROTOCOL: Final[str] = "udp"
    DEFAULT_SUBNET: Final[str] = "10.8.0.0"
    DEFAULT_NETMASK: Final[str] = "255.255.255.0"

    # DNS
    DEFAULT_DNS_SERVERS: Final[tuple] = ("8.8.8.8", "8.8.4.4")

    # Security
    DEFAULT_CIPHER: Final[str] = "AES-256-CBC"
    DEFAULT_AUTH: Final[str] = "SHA256"

    # Timeouts
    KEEPALIVE_PING: Final[int] = 10  # seconds
    KEEPALIVE_TIMEOUT: Final[int] = 120  # seconds

    # Logging
    LOG_VERBOSITY: Final[int] = 3  # 0-11 scale


@dataclass(frozen=True)
class CertificateConfig:
    """Certificate generation configuration"""

    # Validity periods
    CLIENT_CERT_VALIDITY_DAYS: Final[int] = 365  # 1 year
    SERVER_CERT_VALIDITY_DAYS: Final[int] = 3650  # 10 years
    CA_CERT_VALIDITY_DAYS: Final[int] = 3650  # 10 years

    # Key sizes
    RSA_KEY_SIZE: Final[int] = 4096
    DH_KEY_SIZE: Final[int] = 2048

    # Default certificate fields
    DEFAULT_COUNTRY: Final[str] = "RU"
    DEFAULT_STATE: Final[str] = "Moscow"
    DEFAULT_CITY: Final[str] = "Moscow"
    DEFAULT_ORG: Final[str] = "OpenVPN"


@dataclass(frozen=True)
class TaskConfig:
    """Background task configuration"""

    # Progress percentages for installation steps
    INSTALL_UPDATE_PACKAGES: Final[int] = 20
    INSTALL_PACKAGES: Final[int] = 40
    INSTALL_SETUP_EASY_RSA: Final[int] = 60
    INSTALL_GEN_CERTS: Final[int] = 80
    INSTALL_CONFIGURE: Final[int] = 90
    INSTALL_COMPLETE: Final[int] = 100

    # Task timeout
    TASK_TIMEOUT_SECONDS: Final[int] = 600  # 10 minutes


@dataclass(frozen=True)
class MonitoringConfig:
    """Connection monitoring configuration"""

    # Update intervals
    CONNECTION_UPDATE_INTERVAL: Final[int] = 10  # seconds
    SERVER_STATUS_CHECK_INTERVAL: Final[int] = 60  # seconds

    # Connection timeout
    CONNECTION_IDLE_TIMEOUT: Final[int] = 300  # 5 minutes

    # Batch sizes
    MAX_CONNECTIONS_PER_SERVER: Final[int] = 100


@dataclass(frozen=True)
class APIConfig:
    """API configuration constants"""

    # Pagination
    DEFAULT_PAGE_SIZE: Final[int] = 20
    MAX_PAGE_SIZE: Final[int] = 100

    # Timeouts
    API_TIMEOUT_SECONDS: Final[int] = 30

    # Rate limiting
    DEFAULT_RATE_LIMIT: Final[str] = "100/hour"


@dataclass(frozen=True)
class ErrorMessages:
    """User-facing error messages"""

    # SSH errors
    SSH_CONNECTION_FAILED: Final[str] = "Не удалось подключиться к серверу по SSH"
    SSH_AUTH_FAILED: Final[str] = "Ошибка аутентификации SSH"
    SSH_TIMEOUT: Final[str] = "Превышено время ожидания подключения SSH"
    SSH_COMMAND_FAILED: Final[str] = "Не удалось выполнить команду на сервере"

    # OpenVPN errors
    OPENVPN_NOT_INSTALLED: Final[str] = "OpenVPN не установлен на сервере"
    OPENVPN_INSTALL_FAILED: Final[str] = "Не удалось установить OpenVPN"
    OPENVPN_CONFIG_FAILED: Final[str] = "Не удалось настроить OpenVPN"
    OPENVPN_START_FAILED: Final[str] = "Не удалось запустить OpenVPN сервис"

    # Certificate errors
    CERT_GENERATION_FAILED: Final[str] = "Не удалось создать сертификат"
    CERT_REVOCATION_FAILED: Final[str] = "Не удалось отозвать сертификат"
    CERT_NOT_FOUND: Final[str] = "Сертификат не найден"
    CERT_EXPIRED: Final[str] = "Срок действия сертификата истёк"

    # Server errors
    SERVER_NOT_FOUND: Final[str] = "Сервер не найден"
    SERVER_NOT_ACCESSIBLE: Final[str] = "Сервер недоступен"
    SERVER_ALREADY_RUNNING: Final[str] = "Сервер уже запущен"
    SERVER_NOT_RUNNING: Final[str] = "Сервер не запущен"

    # Client errors
    CLIENT_NOT_FOUND: Final[str] = "Клиент не найден"
    CLIENT_ALREADY_EXISTS: Final[str] = "Клиент с таким именем уже существует"
    CLIENT_DISCONNECTION_FAILED: Final[str] = "Не удалось отключить клиента"

    # Generic errors
    INVALID_INPUT: Final[str] = "Некорректные входные данные"
    PERMISSION_DENIED: Final[str] = "Недостаточно прав для выполнения операции"
    INTERNAL_ERROR: Final[str] = "Внутренняя ошибка сервера"


@dataclass(frozen=True)
class SuccessMessages:
    """User-facing success messages"""

    OPENVPN_INSTALLED: Final[str] = "OpenVPN успешно установлен"
    OPENVPN_CONFIGURED: Final[str] = "OpenVPN успешно настроен"
    OPENVPN_STARTED: Final[str] = "OpenVPN сервис запущен"
    OPENVPN_STOPPED: Final[str] = "OpenVPN сервис остановлен"
    OPENVPN_RESTARTED: Final[str] = "OpenVPN сервис перезапущен"

    CERT_CREATED: Final[str] = "Сертификат успешно создан"
    CERT_REVOKED: Final[str] = "Сертификат успешно отозван"

    CLIENT_DISCONNECTED: Final[str] = "Клиент успешно отключён"

    SSH_KEY_GENERATED: Final[str] = "SSH ключ успешно сгенерирован"


# Export all configurations
__all__ = [
    "SSHConfig",
    "OpenVPNPaths",
    "OpenVPNServices",
    "OpenVPNDefaults",
    "CertificateConfig",
    "TaskConfig",
    "MonitoringConfig",
    "APIConfig",
    "ErrorMessages",
    "SuccessMessages",
]
