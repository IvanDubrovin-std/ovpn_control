"""
API package for OpenVPN management
Split into logical modules following SOLID principles
"""

from .server_views import (
    install_openvpn,
    configure_openvpn,
    start_openvpn_server,
    stop_openvpn_server,
    restart_openvpn_server,
    generate_ssh_key,
    check_server_status,
)

from .client_views import (
    create_client,
    download_client_config,
)

from .monitoring_views import (
    update_connections,
    update_all_connections,
    disconnect_client,
)

from .stats_views import (
    get_overall_stats,
    get_server_stats,
)

from .viewsets import (
    OpenVPNServerViewSet,
    ClientCertificateViewSet,
    ServerTaskViewSet,
)

__all__ = [
    # Server management
    'install_openvpn',
    'configure_openvpn',
    'start_openvpn_server',
    'stop_openvpn_server',
    'restart_openvpn_server',
    'generate_ssh_key',
    'check_server_status',
    # Client management
    'create_client',
    'download_client_config',
    # Monitoring
    'update_connections',
    'update_all_connections',
    'disconnect_client',
    # Statistics
    'get_overall_stats',
    'get_server_stats',
    # ViewSets
    'OpenVPNServerViewSet',
    'ClientCertificateViewSet',
    'ServerTaskViewSet',
]
