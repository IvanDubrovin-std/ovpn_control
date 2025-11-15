"""
API ViewSets for OpenVPN management
Following REST framework patterns with DRF ViewSets
"""

import asyncio
import logging
from typing import Any, Dict

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import ClientCertificate, OpenVPNServer, ServerTask
from ..services.monitoring_service import MonitoringService
from ..services.server_service import ServerManagementService
from ..ssh_service import SSHCredentials, SSHService

logger = logging.getLogger(__name__)


class OpenVPNServerViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for OpenVPN servers

    Provides CRUD operations and custom actions for server management
    """

    queryset = OpenVPNServer.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return serializer class for server"""
        from rest_framework import serializers

        class OpenVPNServerSerializer(serializers.ModelSerializer):
            class Meta:
                model = OpenVPNServer
                fields = "__all__"

        return OpenVPNServerSerializer

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """
        Get server status

        Returns:
            Response with current server status
        """
        server = self.get_object()

        try:
            # Check OpenVPN status with SSH commands
            credentials = SSHCredentials(
                hostname=server.host,
                port=server.ssh_port,
                username=server.ssh_username,
                password=server.ssh_password,
                private_key_content=server.ssh_private_key,
            )

            async def check_status():
                ssh_service = SSHService()
                result = await ssh_service.execute_command(
                    credentials, "sudo systemctl is-active openvpn@server"
                )
                return result.stdout.strip() == "active"

            is_active = asyncio.run(check_status())
            status_result = "running" if is_active else "stopped"

            return Response({"status": status_result, "last_check": timezone.now()})
        except Exception as e:
            logger.error(f"Failed to get server status: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="ssh-command")
    def ssh_command(self, request, pk=None):
        """
        Execute SSH command on server

        Args:
            request: Request with 'command' in data

        Returns:
            Response with command output
        """
        server = self.get_object()
        command = request.data.get("command", "").strip()

        if not command:
            return Response({"output": ""})

        async def execute_ssh_command() -> Dict[str, Any]:
            try:
                connection_config = SSHCredentials(
                    hostname=server.host,
                    port=server.ssh_port,
                    username=server.ssh_username,
                    password=server.ssh_password,
                    private_key_content=server.ssh_private_key,
                )

                ssh_service = SSHService()
                result = await ssh_service.execute_command(connection_config, command)

                return {
                    "output": result.output,
                    "success": result.success,
                    "exit_code": result.exit_code,
                }

            except Exception as e:
                logger.error(f"SSH command execution failed: {e}")
                return {"output": f"Error: {str(e)}\\n", "success": False, "exit_code": 1}

        try:
            result = asyncio.run(execute_ssh_command())
            return Response(result)
        except Exception as e:
            return Response(
                {"output": f"Execution error: {str(e)}\\n", "success": False, "exit_code": 1}
            )

    @action(detail=True, methods=["get"])
    def connections(self, request, pk=None):
        """
        Get active VPN connections for server

        Returns:
            Response with list of active connections
        """
        server = self.get_object()

        try:
            monitoring_service = MonitoringService()
            connections = monitoring_service.get_active_connections(server)

            return Response({"connections": connections, "count": len(connections)})
        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientCertificateViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for client certificates

    Provides CRUD operations and certificate management
    """

    queryset = ClientCertificate.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return serializer class for client certificate"""
        from rest_framework import serializers

        class ClientCertificateSerializer(serializers.ModelSerializer):
            class Meta:
                model = ClientCertificate
                fields = "__all__"

        return ClientCertificateSerializer

    def perform_create(self, serializer):
        """
        Create client certificate with OpenVPN service

        Args:
            serializer: Validated serializer with client data

        Raises:
            Exception: If certificate creation fails
        """
        client = serializer.save(created_by=self.request.user)

        try:
            # TODO: Use ClientManagementService instead
            # For now, just save the client - actual certificate creation happens via API endpoint
            pass
        except Exception as e:
            client.delete()
            raise Exception(f"Failed to create certificate: {str(e)}")

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """
        Revoke client certificate

        Returns:
            Response confirming revocation
        """
        client = self.get_object()

        if client.status == "revoked":
            return Response(
                {"error": "Certificate is already revoked"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client.revoke()
            return Response({"message": "Certificate revoked successfully"})
        except Exception as e:
            logger.error(f"Failed to revoke certificate: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"])
    def download_config(self, request, pk=None):
        """
        Download client OpenVPN configuration file

        Returns:
            Response with .ovpn file content
        """
        client = self.get_object()

        if client.is_revoked:
            return Response({"error": "Certificate is revoked"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            config = self._generate_client_config(client)

            response = Response(config, content_type="application/x-openvpn-profile")
            response["Content-Disposition"] = f'attachment; filename="{client.name}.ovpn"'
            return response
        except Exception as e:
            logger.error(f"Failed to generate config: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_client_config(self, client) -> str:
        """
        Generate OpenVPN client configuration

        Args:
            client: ClientCertificate instance

        Returns:
            str: OpenVPN configuration file content
        """
        server = client.server

        config = f"""client
dev tun
proto {server.openvpn_protocol.lower()}
remote {server.host} {server.openvpn_port}
resolv-retry infinite
nobind
persist-key
persist-tun
cipher AES-256-CBC
auth SHA256
verb 3

<ca>
{client.ca_cert}
</ca>

<cert>
{client.client_cert}
</cert>

<key>
{client.client_key}
</key>
"""
        return config


class ServerTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet for server tasks

    Provides read-only access to task history
    """

    queryset = ServerTask.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return serializer class for server task"""
        from rest_framework import serializers

        class ServerTaskSerializer(serializers.ModelSerializer):
            class Meta:
                model = ServerTask
                fields = "__all__"

        return ServerTaskSerializer
