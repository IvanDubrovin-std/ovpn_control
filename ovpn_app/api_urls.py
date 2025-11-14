"""
API URL configuration for OpenVPN app
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# API router
router = DefaultRouter()
router.register(r'servers', api_views.OpenVPNServerViewSet)
router.register(r'clients', api_views.ClientCertificateViewSet)
router.register(r'tasks', api_views.ServerTaskViewSet)

urlpatterns = [
    # DRF Router URLs
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('servers/<int:server_id>/install-openvpn/', 
         api_views.install_openvpn, 
         name='install-openvpn'),
    path('servers/<int:server_id>/configure-openvpn/', 
         api_views.configure_openvpn, 
         name='configure-openvpn'),
    path('servers/<int:server_id>/start-openvpn/', 
         api_views.start_openvpn_server, 
         name='start-openvpn'),
    path('servers/<int:server_id>/stop/', 
         api_views.stop_openvpn_server, 
         name='stop-openvpn'),
    path('servers/<int:server_id>/restart/', 
         api_views.restart_openvpn_server, 
         name='restart-openvpn'),
    path('servers/<int:server_id>/create-client/', 
         api_views.create_client, 
         name='create-client'),
    path('servers/<int:server_id>/download-client/<str:client_name>/', 
         api_views.download_client_config, 
         name='download-client-config'),
    
    # SSH key management
    path('servers/<int:server_id>/generate-ssh-key/',
         api_views.generate_ssh_key,
         name='generate-ssh-key'),
    
    # Server status check
    path('servers/<int:server_id>/check-status/',
         api_views.check_server_status,
         name='check-server-status'),
    
    # Statistics
    path('stats/overall/',
         api_views.get_overall_stats,
         name='overall-stats'),
    path('servers/<int:server_id>/stats/',
         api_views.get_server_stats,
         name='server-stats'),
    
    # Connection monitoring
    path('servers/<int:server_id>/update-connections/', 
         api_views.update_connections, 
         name='update-connections'),
    path('connections/update-all/', 
         api_views.update_all_connections, 
         name='update-all-connections'),
    path('connections/<int:connection_id>/disconnect/',
         api_views.disconnect_client,
         name='disconnect-client'),
]
