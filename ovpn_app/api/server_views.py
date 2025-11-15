"""
Server Management API Views
Handles OpenVPN server operations: installation, configuration, control
"""

import asyncio
import json
import logging
import uuid

from asgiref.sync import sync_to_async
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..agent import AgentClient, AgentDeployer
from ..models import OpenVPNServer
from ..openvpn_service_simple import OpenVPNConfigurator, OpenVPNInstaller
from ..ssh_key_manager import SSHKeyManager
from ..ssh_service import SSHCredentials, SSHService
from ..vpn_monitor import VPNMonitor
from .base import BaseAPIView

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def install_openvpn(request, server_id: int) -> Response:
    """
    Install OpenVPN on the specified server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with installation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Create SSH connection config
        connection_config = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key,
        )

        # Initialize services
        ssh_service = SSHService()
        installer = OpenVPNInstaller(ssh_service)

        # Update server status
        server.status = "installing"
        server.save()

        # Execute installation
        result = asyncio.run(installer.install_openvpn(connection_config))

        # Check result type and handle accordingly
        if hasattr(result, "message"):
            # InstallationResult
            if result.success:
                server.status = "installed"
                server.save()

                return BaseAPIView.success_response(
                    message=result.message, data={"output": result.output}
                )
            else:
                server.status = "error"
                server.save()

                return BaseAPIView.error_response(
                    error=result.error,
                    data={"message": result.message, "output": result.output},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Fallback for CommandResult
            if result.success:
                server.status = "installed"
                server.save()

                return BaseAPIView.success_response(
                    message="OpenVPN installation completed", data={"output": result.output}
                )
            else:
                server.status = "error"
                server.save()

                return BaseAPIView.error_response(
                    error=result.error if hasattr(result, "error") else result.stderr,
                    data={"message": "Installation failed", "output": result.output},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response(
            error="Server not found", status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error installing OpenVPN on server {server_id}: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"install_openvpn(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def configure_openvpn(request, server_id: int) -> Response:
    """
    Configure OpenVPN server after installation

    Args:
        request: HTTP request with configuration parameters
        server_id: Server ID

    Returns:
        Response with configuration result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Create SSH credentials from server model (secure method)
        connection_config = SSHCredentials.from_server(server)

        # Get configuration from request or use server defaults
        server_config = {
            "port": request.data.get("port", server.openvpn_port),
            "protocol": request.data.get("protocol", server.openvpn_protocol.lower()),
            "subnet": request.data.get("subnet", server.server_subnet),
            "netmask": request.data.get("netmask", server.server_netmask),
            "dns_servers": request.data.get("dns_servers", server.get_dns_servers_list()),
            "use_stunnel": server.use_stunnel,  # Pass Stunnel flag to configurator
        }

        # Initialize services
        ssh_service = SSHService()
        configurator = OpenVPNConfigurator(ssh_service)

        # Execute configuration
        result = asyncio.run(configurator.configure_openvpn(connection_config, server_config))

        if result.success:
            # Update server status
            server.status = "running"
            server.save()

            return BaseAPIView.success_response(
                message="OpenVPN configured successfully", data={"output": result.output}
            )
        else:
            return BaseAPIView.error_response(
                error=result.error if hasattr(result, "error") else result.stderr,
                data={"output": result.output},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as e:
        logger.error(f"Error configuring OpenVPN: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"configure_openvpn(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_openvpn_server(request, server_id: int) -> Response:
    """
    Start OpenVPN server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with start result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Start server using SSH commands
        credentials = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key,
        )

        async def start_service():
            ssh_service = SSHService()
            result = await ssh_service.execute_command(
                credentials, "sudo systemctl start openvpn@server"
            )
            return result

        result = asyncio.run(start_service())
        success = result.exit_code == 0

        if success:
            server.status = "running"
            server.save()

            return BaseAPIView.success_response("OpenVPN server started successfully")
        else:
            return BaseAPIView.error_response(
                "Failed to start OpenVPN server", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"start_openvpn_server(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stop_openvpn_server(request, server_id: int) -> Response:
    """
    Stop OpenVPN server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with stop result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        credentials = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key,
        )

        ssh_service = SSHService()

        async def stop_service():
            result = await ssh_service.execute_command(
                credentials,
                "sudo systemctl stop openvpn@server 2>/dev/null || sudo systemctl stop openvpn",
            )
            return result

        result = asyncio.run(stop_service())

        if result.exit_code == 0:
            server.status = "stopped"
            server.save()

            # Remove all active connections
            from ..models import VPNConnection

            VPNConnection.objects.filter(client__server=server).delete()

            return BaseAPIView.success_response("OpenVPN server stopped successfully")
        else:
            return BaseAPIView.error_response(
                f"Failed to stop server: {result.stderr}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except Exception as e:
        logger.error(f"Error stopping server: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"stop_openvpn_server(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def restart_openvpn_server(request, server_id: int) -> Response:
    """
    Restart OpenVPN server

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with restart result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        credentials = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key,
        )

        ssh_service = SSHService()

        async def restart_service():
            result = await ssh_service.execute_command(
                credentials,
                "sudo systemctl restart openvpn@server 2>/dev/null || sudo systemctl restart openvpn",
            )
            return result

        result = asyncio.run(restart_service())

        if result.exit_code == 0:
            server.status = "running"
            server.save()

            # Remove old connections
            from ..models import VPNConnection

            VPNConnection.objects.filter(client__server=server).delete()

            return BaseAPIView.success_response("OpenVPN server restarted successfully")
        else:
            return BaseAPIView.error_response(
                f"Failed to restart server: {result.stderr}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except Exception as e:
        logger.error(f"Error restarting server: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"restart_openvpn_server(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_ssh_key(request, server_id: int) -> Response:
    """
    Generate SSH key and install it on server

    Requires SSH password in request.data

    Args:
        request: HTTP request with password and optional key_type
        server_id: Server ID

    Returns:
        Response with generation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Check for password
        password = request.data.get("password")
        if not password:
            if not server.ssh_password:
                return BaseAPIView.error_response(
                    "Password required. Please provide SSH password.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            password = server.ssh_password

        # Get key type (default: ed25519)
        key_type = request.data.get("key_type", "ed25519")
        if key_type not in ["rsa", "ed25519"]:
            return BaseAPIView.error_response(
                f'Invalid key type: {key_type}. Use "rsa" or "ed25519".',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"Generating {key_type} SSH key for server {server.name}...")

        # Create key manager
        key_manager = SSHKeyManager(key_type=key_type)

        # Generate and install key
        async def generate_and_install_async():
            result = await key_manager.generate_and_install(
                host=server.host,
                username=server.ssh_username,
                password=password,
                port=server.ssh_port,
            )
            return result

        result = asyncio.run(generate_and_install_async())

        if result is None:
            return BaseAPIView.error_response(
                "Failed to generate SSH key pair", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        private_key, public_key, install_success = result

        if not install_success:
            return BaseAPIView.error_response(
                "SSH key generated but failed to install on server",
                data={"private_key": private_key, "public_key": public_key},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Save private key to database
        server.ssh_private_key = private_key
        if request.data.get("clear_password", False):
            server.ssh_password = None
        server.save()

        logger.info(f"✓ SSH key successfully generated and installed for {server.name}")

        return BaseAPIView.success_response(
            f"{key_type.upper()} SSH key successfully generated and installed",
            data={"key_type": key_type, "public_key": public_key, "private_key_saved": True},
        )

    except Exception as e:
        logger.error(f"Error generating SSH key: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"generate_ssh_key(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_server_status(request, server_id: int) -> Response:
    """
    Check and update server status

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with server status
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        # Create VPN monitor
        monitor = VPNMonitor(server)

        # Check status
        async def check_status_async():
            status_result = await monitor.check_server_status()
            await monitor.update_server_status()
            return status_result

        status_result = asyncio.run(check_status_async())

        return BaseAPIView.success_response(
            "Server status checked", data={"status": status_result, "server_name": server.name}
        )

    except Exception as e:
        logger.error(f"Error checking server status: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"check_server_status(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_agent(request, server_id: int) -> Response:
    """
    Update OpenVPN management agent on server

    Deploys the latest version of the agent to the server without
    affecting OpenVPN server operation.

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with update result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        logger.info(f"Starting agent update on server {server.name}")

        # Create SSH credentials
        credentials = SSHCredentials.from_server(server)

        # Deploy agent
        async def update_agent_async():
            from ovpn_app.agent.deployment import AgentDeployer

            deployer = AgentDeployer()
            result = await deployer.deploy_agent(credentials)

            if not result.success:
                raise Exception(f"Agent deployment failed: {result.stderr}")

            return result

        # Run async operation
        result = asyncio.run(update_agent_async())

        logger.info(f"Agent successfully updated on server {server.name}")

        return Response(
            {
                "success": True,
                "message": "Agent successfully updated",
                "output": result.stdout,
            },
            status=status.HTTP_200_OK,
        )

    except OpenVPNServer.DoesNotExist:
        return Response(
            {"success": False, "error": "Server not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error updating agent: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"update_agent(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reinstall_openvpn(request, server_id: int) -> Response:
    """
    Complete reinstallation of OpenVPN server using autonomous agent

    This endpoint deploys an agent to the server and uses it to perform
    reinstallation without SSH timeout issues. Perfect for long operations
    like DH 4096 generation.

    Features:
    - No SSH timeouts
    - Real progress tracking
    - Supports DH 4096 (5-30 minutes)
    - Autonomous execution

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with reinstallation result
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        logger.info(f"Starting agent-based reinstallation of OpenVPN on server {server.name}")

        # Create SSH credentials
        credentials = SSHCredentials.from_server(server)

        # Update server status
        server.status = "reinstalling"
        server.save()

        async def reinstall_via_agent_async():
            """Async reinstallation via agent"""

            # Step 1: Always redeploy agent to ensure latest version
            logger.info("Step 1: Deploying latest agent version...")
            deployer = AgentDeployer()

            deploy_result = await deployer.deploy_agent(credentials)

            if not deploy_result.success:
                return {
                    "success": False,
                    "message": "Failed to deploy agent",
                    "error": deploy_result.stderr,
                    "steps": ["Agent deployment failed"],
                }

            logger.info("Agent deployed successfully")

            # Step 2: Execute reinstallation via agent
            logger.info("Step 2: Executing reinstallation via agent...")

            agent_client = AgentClient()
            task_id = f"reinstall-{server.id}-{uuid.uuid4().hex[:8]}"

            config = {
                "port": server.openvpn_port,
                "protocol": server.openvpn_protocol,
                "subnet": server.server_subnet,
                "netmask": server.server_netmask,
                "dns_servers": server.get_dns_servers_list(),
                "use_stunnel": server.use_stunnel,
            }

            result = await agent_client.reinstall_openvpn(credentials, task_id, config)

            # Step 3: Sync clients after reinstall
            if result.get("status") == "success":
                logger.info("Step 3: Syncing clients with server...")
                sync_task_id = f"sync-clients-{server.id}"
                clients_result = await agent_client.list_clients(credentials, sync_task_id)

                if clients_result.get("status") == "success":
                    # Parse clients list from agent
                    try:
                        clients_on_server = json.loads(clients_result.get("output", "[]"))
                        client_names_on_server = {c["name"] for c in clients_on_server}

                        # Remove clients from DB that don't exist on server (sync operation)
                        from ..models import ClientCertificate

                        @sync_to_async
                        def sync_clients_to_db():
                            db_clients = list(ClientCertificate.objects.filter(server=server))
                            removed_count = 0

                            for db_client in db_clients:
                                if db_client.name not in client_names_on_server:
                                    logger.info(f"Removing orphaned client: {db_client.name}")
                                    db_client.delete()
                                    removed_count += 1

                            return removed_count

                        removed_count = await sync_clients_to_db()
                        logger.info(f"Removed {removed_count} orphaned clients from DB")

                    except json.JSONDecodeError:
                        logger.warning("Failed to parse clients list from agent")

            return result

        # Execute reinstallation
        result = asyncio.run(reinstall_via_agent_async())

        # Update server status based on result
        if result.get("status") == "success":
            server.status = "active"
            server.save()

            return BaseAPIView.success_response(
                message=result.get("message", "OpenVPN reinstalled successfully"),
                data={
                    "output": result.get("output", ""),
                    "progress": result.get("progress", 100),
                },
            )
        else:
            server.status = "error"
            server.save()

            return BaseAPIView.error_response(
                error=result.get("error", "Reinstallation failed"),
                data={
                    "message": result.get("message", "Unknown error"),
                    "output": result.get("output", ""),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response(
            error="Server not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error reinstalling OpenVPN: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"reinstall_openvpn(server_id={server_id})")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_clients(request, server_id: int) -> Response:
    """
    Synchronize clients in database with actual clients on server

    This endpoint queries the server via agent to get list of actual clients
    and removes any clients from database that don't exist on server anymore.

    Args:
        request: HTTP request
        server_id: Server ID

    Returns:
        Response with sync results
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)

        logger.info(f"Syncing clients for server {server.name}")

        # Get SSH credentials
        credentials = SSHCredentials.from_server(server)

        async def sync_clients_async():
            """Async client synchronization"""

            # Deploy agent if needed
            deployer = AgentDeployer()
            if not await deployer.is_agent_installed(credentials):
                deploy_result = await deployer.deploy_agent(credentials)
                if not deploy_result.success:
                    return {
                        "success": False,
                        "error": "Failed to deploy agent",
                        "details": deploy_result.stderr,
                    }

            # Get clients list from server
            agent_client = AgentClient()
            task_id = f"sync-clients-{server.id}-{uuid.uuid4().hex[:8]}"

            result = await agent_client.list_clients(credentials, task_id)

            if result.get("status") != "success":
                return {
                    "success": False,
                    "error": "Failed to get clients list from server",
                    "details": result.get("error", "Unknown error"),
                }

            # Parse clients list
            try:
                clients_on_server = json.loads(result.get("output", "[]"))
                client_names_on_server = {c["name"] for c in clients_on_server}

                # Get clients from database and sync (async-safe)
                from ..models import ClientCertificate

                @sync_to_async
                def perform_sync():
                    db_clients = list(ClientCertificate.objects.filter(server=server))
                    db_client_names = {c.name for c in db_clients}

                    # Find clients to remove (exist in DB but not on server)
                    clients_to_remove = db_client_names - client_names_on_server

                    # Find new clients (exist on server but not in DB)
                    clients_to_add = client_names_on_server - db_client_names

                    # Remove orphaned clients
                    removed_count = 0
                    for client_name in clients_to_remove:
                        client = ClientCertificate.objects.get(server=server, name=client_name)
                        logger.info(f"Removing orphaned client: {client_name}")
                        client.delete()
                        removed_count += 1

                    return {
                        "clients_on_server": len(clients_on_server),
                        "clients_in_db": len(db_clients),
                        "clients_removed": removed_count,
                        "clients_to_add": len(clients_to_add),
                        "orphaned_clients": list(clients_to_remove),
                        "new_clients": list(clients_to_add),
                    }

                sync_result = await perform_sync()

                return {
                    "success": True,
                    **sync_result,
                }

            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": "Failed to parse clients list",
                    "details": str(e),
                }

        # Execute sync
        result = asyncio.run(sync_clients_async())

        if result.get("success"):
            return BaseAPIView.success_response(
                message=f"Clients synchronized. Removed {result.get('clients_removed', 0)} orphaned clients.",
                data=result,
            )
        else:
            return BaseAPIView.error_response(
                error=result.get("error", "Sync failed"),
                data=result,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    except OpenVPNServer.DoesNotExist:
        return BaseAPIView.error_response(
            error="Server not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error syncing clients: {e}", exc_info=True)
        return BaseAPIView.handle_exception(e, f"sync_clients(server_id={server_id})")
