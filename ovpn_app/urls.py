"""
URL configuration for OpenVPN app
"""

from django.urls import path
from . import views

app_name = 'ovpn_app'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Servers
    path('servers/', views.ServerListView.as_view(), name='server_list'),
    path('servers/create/', views.ServerCreateView.as_view(), name='server_create'),
    path('servers/<int:pk>/', views.ServerDetailView.as_view(), name='server_detail'),
    path('servers/<int:pk>/edit/', views.ServerUpdateView.as_view(), name='server_edit'),
    path('servers/<int:pk>/delete/', views.ServerDeleteView.as_view(), name='server_delete'),
    path('servers/<int:server_id>/install/', views.install_openvpn, name='install_openvpn'),
    path('servers/<int:server_id>/status/', views.check_server_status, name='check_server_status'),
    
    # Clients
    path('clients/', views.ClientListView.as_view(), name='client_list'),
    path('clients/create/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:client_id>/revoke/', views.revoke_client, name='revoke_client'),
    path('clients/<int:client_id>/download/', views.download_client_config, name='download_client_config'),
    
    # Connections
    path('connections/', views.ConnectionListView.as_view(), name='connection_list'),
    path('monitoring/', views.monitoring_view, name='monitoring'),
    
    # Tasks
    path('tasks/<str:task_id>/status/', views.task_status, name='task_status'),
]
