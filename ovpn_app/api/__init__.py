"""
API package for OpenVPN management
Split into logical modules following SOLID principles
"""

from .client_views import (
    create_client,
    download_client_config,
)
from .monitoring_views import (
    disconnect_client,
    update_all_connections,
    update_connections,
)
from .server_views import (
    check_server_status,
    configure_openvpn,
    generate_ssh_key,
    install_openvpn,
    reinstall_openvpn,
    restart_openvpn_server,
    start_openvpn_server,
    stop_openvpn_server,
    sync_clients,
    update_agent,
)
from .stats_views import (
    get_overall_stats,
    get_server_stats,
)
from .viewsets import (
    ClientCertificateViewSet,
    OpenVPNServerViewSet,
    ServerTaskViewSet,
)

__all__ = [
    # Server management
    "install_openvpn",
    "configure_openvpn",
    "reinstall_openvpn",
    "update_agent",
    "start_openvpn_server",
    "stop_openvpn_server",
    "restart_openvpn_server",
    "generate_ssh_key",
    "check_server_status",
    "sync_clients",
    # Client management
    "create_client",
    "download_client_config",
    # Monitoring
    "update_connections",
    "update_all_connections",
    "disconnect_client",
    # Statistics
    "get_overall_stats",
    "get_server_stats",
    # ViewSets
    "OpenVPNServerViewSet",
    "ClientCertificateViewSet",
    "ServerTaskViewSet",
]
