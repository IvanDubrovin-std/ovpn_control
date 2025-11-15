"""
API URL configuration for OpenVPN app
Modular structure following SOLID principles
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Import from modular API structure
from .api import (  # ViewSets; Server management; Client management; Monitoring; Statistics
    ClientCertificateViewSet,
    OpenVPNServerViewSet,
    ServerTaskViewSet,
    check_server_status,
    configure_openvpn,
    create_client,
    disconnect_client,
    download_client_config,
    generate_ssh_key,
    get_overall_stats,
    get_server_stats,
    install_openvpn,
    reinstall_openvpn,
    restart_openvpn_server,
    start_openvpn_server,
    stop_openvpn_server,
    sync_clients,
    update_agent,
    update_all_connections,
    update_connections,
)

# Import Client Revocation views
from .api.client_revocation_views import (
    revoke_client_certificate,
    terminate_client_connection,
)

# API router
router = DefaultRouter()
router.register(r"servers", OpenVPNServerViewSet)
router.register(r"clients", ClientCertificateViewSet)
router.register(r"tasks", ServerTaskViewSet)

urlpatterns = [
    # DRF Router URLs
    path("", include(router.urls)),
    # Server management endpoints
    path("servers/<int:server_id>/install-openvpn/", install_openvpn, name="install-openvpn"),
    path("servers/<int:server_id>/configure-openvpn/", configure_openvpn, name="configure-openvpn"),
    path("servers/<int:server_id>/reinstall-openvpn/", reinstall_openvpn, name="reinstall-openvpn"),
    path("servers/<int:server_id>/update-agent/", update_agent, name="update-agent"),
    path("servers/<int:server_id>/start-openvpn/", start_openvpn_server, name="start-openvpn"),
    path("servers/<int:server_id>/stop/", stop_openvpn_server, name="stop-openvpn"),
    path("servers/<int:server_id>/restart/", restart_openvpn_server, name="restart-openvpn"),
    path("servers/<int:server_id>/generate-ssh-key/", generate_ssh_key, name="generate-ssh-key"),
    path("servers/<int:server_id>/check-status/", check_server_status, name="check-server-status"),
    path("servers/<int:server_id>/sync-clients/", sync_clients, name="sync-clients"),
    # Client management endpoints
    path("servers/<int:server_id>/create-client/", create_client, name="create-client"),
    path(
        "servers/<int:server_id>/download-client/<str:client_name>/",
        download_client_config,
        name="download-client-config",
    ),
    path("clients/<int:client_id>/revoke/", revoke_client_certificate, name="revoke-client"),
    path(
        "clients/<int:client_id>/terminate/",
        terminate_client_connection,
        name="terminate-client-connection",
    ),
    # Statistics endpoints
    path("stats/overall/", get_overall_stats, name="overall-stats"),
    path("servers/<int:server_id>/stats/", get_server_stats, name="server-stats"),
    # Connection monitoring endpoints
    path(
        "servers/<int:server_id>/update-connections/", update_connections, name="update-connections"
    ),
    path("connections/update-all/", update_all_connections, name="update-all-connections"),
    path(
        "connections/<int:connection_id>/disconnect/", disconnect_client, name="disconnect-client"
    ),
]
