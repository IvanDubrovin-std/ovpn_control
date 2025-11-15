"""
Stunnel Management API Views
Handles Stunnel operations for OpenVPN TCP tunneling
"""

import asyncio
import logging

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import OpenVPNServer
from ..ssh_service import SSHCredentials, SSHService
from ..stunnel_service import StunnelManager
from ..constants import ErrorMessages, SuccessMessages

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def setup_stunnel(request, server_id: int) -> Response:
    """
    Complete Stunnel setup: install, configure, generate certificates, start service

    Args:
        request: HTTP request with optional stunnel_port and openvpn_port
        server_id: Server ID

    Returns:
        Response with setup result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Get configuration from request or use defaults
        stunnel_port = request.data.get("stunnel_port", server.stunnel_port or 443)
        openvpn_port = request.data.get("openvpn_port", server.openvpn_port or 1194)

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Run setup asynchronously
        result = asyncio.run(
            stunnel_manager.setup_stunnel(
                credentials=credentials,
                stunnel_port=stunnel_port,
                openvpn_port=openvpn_port,
                server_name=server.name,
                server_ip=server.host,
            )
        )

        if result.success:
            # Update server model
            server.use_stunnel = True
            server.stunnel_port = stunnel_port
            server.stunnel_enabled = True
            server.save()

            logger.info(f"Stunnel setup completed successfully on {server.name}")
            return Response(
                {
                    "status": "success",
                    "message": result.message,
                    "output": result.output,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(f"Stunnel setup failed on {server.name}: {result.error}")
            return Response(
                {
                    "status": "error",
                    "message": result.message,
                    "output": result.output,
                    "error": result.error,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in setup_stunnel: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_stunnel(request, server_id: int) -> Response:
    """
    Start Stunnel service on server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with operation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        if not server.use_stunnel:
            return Response(
                {"status": "error", "message": "Stunnel is not configured for this server"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Start service
        result = asyncio.run(stunnel_manager.service_manager.start(credentials))

        if result.success:
            server.stunnel_enabled = True
            server.save()

            logger.info(f"Stunnel started successfully on {server.name}")
            return Response(
                {
                    "status": "success",
                    "message": SuccessMessages.STUNNEL_STARTED,
                    "output": result.stdout,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(f"Failed to start Stunnel on {server.name}: {result.stderr}")
            return Response(
                {
                    "status": "error",
                    "message": ErrorMessages.STUNNEL_START_FAILED,
                    "error": result.stderr,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in start_stunnel: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stop_stunnel(request, server_id: int) -> Response:
    """
    Stop Stunnel service on server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with operation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        if not server.use_stunnel:
            return Response(
                {"status": "error", "message": "Stunnel is not configured for this server"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Stop service
        result = asyncio.run(stunnel_manager.service_manager.stop(credentials))

        if result.success:
            server.stunnel_enabled = False
            server.save()

            logger.info(f"Stunnel stopped successfully on {server.name}")
            return Response(
                {
                    "status": "success",
                    "message": SuccessMessages.STUNNEL_STOPPED,
                    "output": result.stdout,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(f"Failed to stop Stunnel on {server.name}: {result.stderr}")
            return Response(
                {
                    "status": "error",
                    "message": ErrorMessages.STUNNEL_STOP_FAILED,
                    "error": result.stderr,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in stop_stunnel: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def restart_stunnel(request, server_id: int) -> Response:
    """
    Restart Stunnel service on server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with operation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        if not server.use_stunnel:
            return Response(
                {"status": "error", "message": "Stunnel is not configured for this server"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Restart service
        result = asyncio.run(stunnel_manager.service_manager.restart(credentials))

        if result.success:
            server.stunnel_enabled = True
            server.save()

            logger.info(f"Stunnel restarted successfully on {server.name}")
            return Response(
                {
                    "status": "success",
                    "message": SuccessMessages.STUNNEL_RESTARTED,
                    "output": result.stdout,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(f"Failed to restart Stunnel on {server.name}: {result.stderr}")
            return Response(
                {
                    "status": "error",
                    "message": ErrorMessages.STUNNEL_RESTART_FAILED,
                    "error": result.stderr,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in restart_stunnel: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stunnel_status(request, server_id: int) -> Response:
    """
    Check Stunnel service status on server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with service status
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        if not server.use_stunnel:
            return Response(
                {
                    "status": "info",
                    "message": "Stunnel is not configured for this server",
                    "configured": False,
                    "running": False,
                },
                status=status.HTTP_200_OK,
            )

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Check status
        result = asyncio.run(stunnel_manager.check_status(credentials))

        # Update server model status
        is_running = result.success and "active" in result.stdout.lower()
        if server.stunnel_enabled != is_running:
            server.stunnel_enabled = is_running
            server.save()

        return Response(
            {
                "status": "success",
                "configured": True,
                "running": is_running,
                "stunnel_port": server.stunnel_port,
                "output": result.stdout,
            },
            status=status.HTTP_200_OK,
        )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in stunnel_status: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def configure_stunnel(request, server_id: int) -> Response:
    """
    Configure Stunnel (without installation)

    Args:
        request: HTTP request with stunnel_port and openvpn_port
        server_id: Server ID

    Returns:
        Response with configuration result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Get configuration from request
        stunnel_port = request.data.get("stunnel_port", server.stunnel_port or 443)
        openvpn_port = request.data.get("openvpn_port", server.port or 1194)

        # Create SSH credentials from server model (secure method)
        credentials = SSHCredentials.from_server(server)

        # Initialize Stunnel manager
        ssh_service = SSHService()
        stunnel_manager = StunnelManager(ssh_service)

        # Configure Stunnel
        result = asyncio.run(
            stunnel_manager.configurator.configure(
                credentials=credentials,
                stunnel_port=stunnel_port,
                openvpn_port=openvpn_port,
                server_name=server.name,
            )
        )

        if result.success:
            # Update server model
            server.use_stunnel = True
            server.stunnel_port = stunnel_port
            server.save()

            logger.info(f"Stunnel configured successfully on {server.name}")
            return Response(
                {
                    "status": "success",
                    "message": SuccessMessages.STUNNEL_CONFIGURED,
                    "output": result.stdout,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(f"Stunnel configuration failed on {server.name}: {result.stderr}")
            return Response(
                {
                    "status": "error",
                    "message": ErrorMessages.STUNNEL_CONFIG_FAILED,
                    "error": result.stderr,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in configure_stunnel: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
