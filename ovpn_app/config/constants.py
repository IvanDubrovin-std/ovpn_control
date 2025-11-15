"""
Constants for OpenVPN management
Centralized configuration to eliminate hardcode
"""

# Network configuration
DEFAULT_SUBNET = "10.8.0.0"
DEFAULT_NETMASK = "255.255.255.0"
DEFAULT_DNS_SERVERS = ["8.8.8.8", "8.8.4.4"]

# OpenVPN paths
OVPN_CONFIG_PATH = "/etc/openvpn"
OVPN_LOG_PATH = "/var/log/openvpn"
EASY_RSA_PATH = "~/easy-rsa"
CLIENT_CONFIGS_PATH = "~/client-configs"

# Ports and protocols
DEFAULT_OPENVPN_PORT = 1194
DEFAULT_PROTOCOL = "udp"
MANAGEMENT_PORT = 7505
MANAGEMENT_HOST = "localhost"

# System configuration
OVPN_USER = "nobody"
OVPN_GROUP = "nogroup"

# Certificate configuration
DEFAULT_CERT_VALIDITY_DAYS = 365
DH_KEY_SIZE = 2048

# Cipher configuration
CIPHER = "AES-256-GCM"
AUTH_ALGORITHM = "SHA256"

# Client configuration
MAX_CLIENTS = 100
KEEPALIVE_PING = 10
KEEPALIVE_TIMEOUT = 120

# Timeouts
SSH_COMMAND_TIMEOUT = 600  # 10 minutes
AGENT_COMMAND_TIMEOUT = 3600  # 1 hour for long operations
