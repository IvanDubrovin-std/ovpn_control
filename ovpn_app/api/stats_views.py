"""
Statistics API Views
Provides overall and per-server statistics
"""

import asyncio
import logging
from typing import Any, Dict, List

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import ClientCertificate, OpenVPNServer, VPNConnection
from ..vpn_monitor import VPNMonitor
from .base import BaseAPIView

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_overall_stats(request) -> Response:
    """
    Get overall system statistics

    Provides aggregated statistics across all servers:
    - Server counts (total, running)
    - Active connections
    - Total clients
    - Data transfer totals

    Args:
        request: HTTP request

    Returns:
        Response with overall statistics
    """
    try:
        total_servers = OpenVPNServer.objects.count()
        running_servers = OpenVPNServer.objects.filter(status="running").count()
        active_connections = VPNConnection.objects.count()
        total_clients = ClientCertificate.objects.count()

        # Calculate total data transfer
        data_stats = VPNConnection.objects.aggregate(
            total_rx=Sum("bytes_received"), total_tx=Sum("bytes_sent")
        )

        total_bytes = (data_stats["total_rx"] or 0) + (data_stats["total_tx"] or 0)
        total_data_mb = round(total_bytes / (1024 * 1024), 2)

        return Response(
            {
                "total_servers": total_servers,
                "running_servers": running_servers,
                "active_connections": active_connections,
                "total_clients": total_clients,
                "total_data": f"{total_data_mb} MB",
                "avg_connection_time": "-",  # TODO: Calculate average duration
                "system_load": "-",  # TODO: Aggregate system load
            }
        )

    except Exception as e:
        logger.error(f"Error getting overall stats: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, "get_overall_stats()")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_server_stats(request, server_id: int) -> Response:
    """
    Get detailed statistics for specific server

    Includes:
    - Server status and info
    - Active connections with client details
    - System metrics (uptime, load, bandwidth)
    - Per-connection data transfer

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with server statistics
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Create VPN monitor
        monitor = VPNMonitor(server)

        # Get system information
        async def get_system_info() -> tuple:
            """
            Fetch system metrics asynchronously

            Returns:
                Tuple of (uptime, load)
            """
            uptime = await monitor.get_openvpn_uptime()
            load = await monitor.get_system_load()
            return uptime, load

        # Run async function
        uptime, load = asyncio.run(get_system_info())

        # Get active connections
        connections = VPNConnection.objects.filter(client__server=server)

        # Calculate statistics
        total_bandwidth = 0
        connections_data: List[Dict[str, Any]] = []

        for conn in connections:
            # Calculate data transfer
            total_bytes = conn.bytes_received + conn.bytes_sent
            data_transfer = f"{round(total_bytes / (1024 * 1024), 2)} MB"

            # Bandwidth estimate (bytes per second)
            # Note: This is rough estimate. For accurate bandwidth,
            # track changes over time intervals
            bandwidth_bps = (conn.bytes_received + conn.bytes_sent) / 60
            total_bandwidth += bandwidth_bps

            connections_data.append(
                {
                    "client_name": conn.client.name,
                    "virtual_ip": conn.virtual_ip,
                    "real_ip": conn.client_ip,
                    "duration": conn.format_duration(),
                    "data_transfer": data_transfer,
                    "bytes_received": conn.bytes_received,
                    "bytes_sent": conn.bytes_sent,
                }
            )

        # Format bandwidth
        if total_bandwidth > 1024 * 1024:
            bandwidth_str = f"{round(total_bandwidth / (1024 * 1024), 2)} MB/s"
        elif total_bandwidth > 1024:
            bandwidth_str = f"{round(total_bandwidth / 1024, 2)} KB/s"
        else:
            bandwidth_str = f"{round(total_bandwidth, 2)} B/s"

        # Status display mapping
        status_display_map = {
            "running": "Работает",
            "stopped": "Остановлен",
            "pending": "Ожидает",
            "installing": "Устанавливается",
            "error": "Ошибка",
        }

        return Response(
            {
                "status": server.status,
                "status_display": status_display_map.get(server.status, server.status),
                "active_connections": connections.count(),
                "bandwidth": bandwidth_str if total_bandwidth > 0 else "-",
                "uptime": uptime or "-",
                "load": load or "-",
                "server_info": {
                    "name": server.name,
                    "host": server.host,
                    "port": server.openvpn_port,
                    "protocol": server.openvpn_protocol.upper(),
                },
                "connections": connections_data,
            }
        )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response("Server not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting server stats: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"get_server_stats(server_id={server_id})")
