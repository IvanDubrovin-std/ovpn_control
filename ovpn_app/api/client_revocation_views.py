"""
Client Certificate Revocation API Views
Handles certificate revocation with CRL generation and connection termination
"""

import asyncio
import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import ClientCertificate
from ..openvpn_service_simple import CertificateRevocationService
from ..ssh_service import SSHCredentials, SSHService

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_client_certificate(request, client_id: int) -> Response:
    """
    Revoke client certificate and update CRL

    This endpoint:
    1. Marks certificate as revoked in database
    2. Revokes certificate on OpenVPN server using easy-rsa
    3. Regenerates CRL (Certificate Revocation List)
    4. Restarts OpenVPN to apply changes
    5. Terminates active client connection if exists

    Args:
        request: HTTP request
        client_id: Client certificate ID

    Returns:
        Response with revocation result
    """
    try:
        client = get_object_or_404(ClientCertificate, id=client_id)

        # Check if already revoked
        if client.status == "revoked":
            return Response(
                {
                    "status": "error",
                    "message": "Certificate is already revoked",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get server
        server = client.server

        # Create SSH credentials
        credentials = SSHCredentials.from_server(server)

        # Initialize revocation service
        ssh_service = SSHService()
        revocation_service = CertificateRevocationService(ssh_service)

        # Execute revocation on server
        result = asyncio.run(revocation_service.revoke_certificate(credentials, client.name))

        if result.success:
            # Update database
            client.revoke()

            logger.info(f"Certificate revoked successfully: {client.name} on server {server.name}")

            return Response(
                {
                    "status": "success",
                    "message": "Certificate revoked, CRL updated, client disconnected.",
                    "details": "The certificate has been revoked on the server, CRL regenerated, and the client connection terminated using management interface.",
                    "output": result.stdout,
                    "client": {
                        "id": client.id,
                        "name": client.name,
                        "status": client.status,
                        "revoked_at": client.revoked_at,
                    },
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Revocation failed on server, but mark in DB anyway for safety
            client.revoke()
            logger.error(f"Certificate revocation failed on server but marked in DB: {client.name}")

            return Response(
                {
                    "status": "partial",
                    "message": "Certificate marked as revoked in database, but server revocation failed",
                    "error": result.stderr,
                    "output": result.stdout,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ClientCertificate.DoesNotExist:
        return Response(
            {"status": "error", "message": "Client certificate not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in revoke_client_certificate: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def terminate_client_connection(request, client_id: int) -> Response:
    """
    Terminate active client connection

    Args:
        request: HTTP request
        client_id: Client certificate ID

    Returns:
        Response with termination result
    """
    try:
        client = get_object_or_404(ClientCertificate, id=client_id)
        server = client.server

        # Create SSH credentials
        credentials = SSHCredentials.from_server(server)

        # Initialize revocation service
        ssh_service = SSHService()
        revocation_service = CertificateRevocationService(ssh_service)

        # Kill client connection
        result = asyncio.run(revocation_service.kill_client_connection(credentials, client.name))

        if result.success:
            return Response(
                {
                    "status": "success",
                    "message": f"Connection terminated for client: {client.name}",
                    "output": result.stdout,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "status": "error",
                    "message": "Failed to terminate connection",
                    "error": result.stderr,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ClientCertificate.DoesNotExist:
        return Response(
            {"status": "error", "message": "Client certificate not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Exception in terminate_client_connection: {e}")
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
