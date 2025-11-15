"""
Client Management API Views
Handles client certificate creation and configuration download
"""

import asyncio
import logging
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import ClientCertificate, OpenVPNServer
from ..services.client_service import ClientManagementService
from .base import BaseAPIView

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_client(request, server_id: int) -> Response:
    """
    Create OpenVPN client certificate and configuration

    Args:
        request: HTTP request with client_name and optional email
        server_id: Server ID

    Returns:
        Response with client creation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        client_name = request.data.get("client_name", "").strip()

        if not client_name:
            return BaseAPIView.error_response(
                "Client name is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Use new ClientManagementService
        service = ClientManagementService(server)

        # Create client certificate via agent (run async in sync context)
        client_data = asyncio.run(service.create_client(client_name))

        # Save client to database (1 year expiration)
        expires_at = timezone.now() + timedelta(days=365)

        client = ClientCertificate.objects.create(
            server=server,
            name=client_name,
            email=request.data.get("email", ""),
            client_cert="",  # Cert managed by agent
            client_key="",  # Key managed by agent
            expires_at=expires_at,
            created_by=request.user,
        )

        return BaseAPIView.success_response(
            f"Client '{client_name}' created successfully",
            data={"client_id": client.id, "client_data": client_data}
        )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response("Server not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error creating client on server {server_id}: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"create_client(server_id={server_id})")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_client_config(request, server_id: int, client_name: str) -> HttpResponse:
    """
    Download client OpenVPN configuration file

    Args:
        request: HTTP request
        server_id: Server ID
        client_name: Client certificate name

    Returns:
        HttpResponse with .ovpn file or error Response
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Use new ClientManagementService
        service = ClientManagementService(server)

        # Download client config via agent
        config_content = asyncio.run(service.download_client_config(client_name))

        if config_content:
            # Return .ovpn file
            response = HttpResponse(config_content, content_type="application/x-openvpn-profile")
            response["Content-Disposition"] = f'attachment; filename="{client_name}.ovpn"'
            return response
        else:
            return Response(
                {
                    "success": False,
                    "error": "Failed to download config",
                    "message": "Config file not found on server",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"success": False, "error": "Server not found"}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error downloading client config: {e}", exc_info=True)
        return Response(
            {"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
