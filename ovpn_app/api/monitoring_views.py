"""
Monitoring API Views
Handles VPN connection monitoring and client disconnection
"""

import asyncio
import logging
from typing import Any, Dict

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import OpenVPNServer, VPNConnection
from ..services.monitoring_service import MonitoringService
from .base import BaseAPIView

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_connections(request, server_id: int) -> Response:
    """
    Update VPN connections for a specific server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with updated connection count
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Use new MonitoringService
        service = MonitoringService(server)

        # Get status via agent (includes connections)
        status_data = asyncio.run(service.get_status())

        # TODO: Sync connections to database
        # For now, just return connection count from status
        connection_count = len(status_data.get("connections", []))

        return BaseAPIView.success_response(
            f"Connections updated for {server.name}",
            data={"connection_count": connection_count, "connections": status_data.get("connections", [])}
        )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response("Server not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error updating connections: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"update_connections(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_all_connections(request) -> Response:
    """
    Update VPN connections for all active servers

    Args:
        request: HTTP request

    Returns:
        Response with total connection and server counts
    """
    try:
        # Update all servers
        servers = OpenVPNServer.objects.filter(status="running")

        total_connections = 0
        for server in servers:
            service = MonitoringService(server)
            try:
                status_data = asyncio.run(service.get_status())
                total_connections += len(status_data.get("connections", []))
            except Exception as e:
                logger.warning(f"Failed to get status for server {server.name}: {e}")

        return BaseAPIView.success_response(
            "All connections updated",
            data={"total_connections": total_connections, "active_servers": servers.count()},
        )

    except Exception as e:
        logger.error(f"Error updating all connections: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, "update_all_connections()")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disconnect_client(request, connection_id: int) -> Response:
    """
    Disconnect VPN client

    Terminates client connection via OpenVPN management interface

    Args:
        request: HTTP request
        connection_id: VPN connection ID

    Returns:
        Response with disconnect result
    """
    try:
        connection = get_object_or_404(VPNConnection, id=connection_id)
        server = connection.client.server
        client_name = connection.client.name

        # Use new MonitoringService
        service = MonitoringService(server)

        # Disconnect client via agent
        disconnect_result = asyncio.run(service.disconnect_client(client_name))

        # Delete connection from database
        connection.delete()

        return BaseAPIView.success_response(
            f"Client {client_name} disconnected successfully",
            data=disconnect_result
        )

    except VPNConnection.DoesNotExist:
        return BaseAPIView.error_response(
            "Connection not found", status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error disconnecting client: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"disconnect_client(connection_id={connection_id})")
