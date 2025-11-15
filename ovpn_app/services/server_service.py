"""
Server Management Service
Single Responsibility: Handle server installation, configuration, and lifecycle
"""

import uuid
from typing import Dict

from ovpn_app.agent.client import AgentClient
from ovpn_app.agent.deployment import AgentDeployer
from ovpn_app.config import AgentConfig
from ovpn_app.models import OpenVPNServer
from ovpn_app.ssh_service import SSHCredentials


class ServerManagementService:
    """
    Service for managing OpenVPN server lifecycle

    Follows SOLID principles:
    - Single Responsibility: Only handles server operations
    - Open/Closed: Extensible through agent commands
    - Liskov Substitution: Can be replaced with mock for testing
    - Interface Segregation: Clean, focused interface
    - Dependency Inversion: Depends on abstract AgentClient
    """

    def __init__(self, server: OpenVPNServer):
        """
        Initialize server management service

        Args:
            server: OpenVPNServer instance to manage
        """
        self.server = server
        self.agent_client = AgentClient()
        self.deployer = AgentDeployer()
        self.credentials = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password or None,
            private_key_content=server.ssh_private_key or None,
        )

    async def install(self) -> Dict:
        """
        Install OpenVPN on the server

        Returns:
            Dictionary with installation result

        Raises:
            Exception: If installation fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Execute install command
        task_id = str(uuid.uuid4())
        result = await self.agent_client.execute_command(
            "install",
            task_id,
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to install OpenVPN"))

        return result

    async def configure(self) -> Dict:
        """
        Configure OpenVPN server with current settings

        Returns:
            Dictionary with configuration result

        Raises:
            Exception: If configuration fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Build configuration
        config = AgentConfig.from_server(self.server)

        # Execute configure command
        task_id = str(uuid.uuid4())
        result = await self.agent_client.execute_command(
            "configure",
            task_id,
            config=config.to_dict(),
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to configure OpenVPN"))

        return result

    async def reinstall(self) -> Dict:
        """
        Reinstall OpenVPN server (install + configure + generate certs)

        Returns:
            Dictionary with reinstallation result

        Raises:
            Exception: If reinstallation fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Build configuration
        config = AgentConfig.from_server(self.server)

        # Execute reinstall command
        task_id = str(uuid.uuid4())
        result = await self.agent_client.execute_command(
            "reinstall",
            task_id,
            config=config.to_dict(),
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to reinstall OpenVPN"))

        return result

    async def start(self) -> Dict:
        """
        Start OpenVPN service

        Returns:
            Dictionary with service control result
        """
        import asyncssh

        async with asyncssh.connect(
            self.server.host,
            username=self.server.ssh_username,
            client_keys=[self.server.ssh_key_path] if self.server.ssh_key_path else None,
            password=self.server.ssh_password if not self.server.ssh_key_path else None,
            known_hosts=None,
        ) as conn:
            result = await conn.run("sudo systemctl start openvpn@server", check=False)

            return {
                "success": result.exit_status == 0,
                "output": result.stdout,
                "error": result.stderr,
            }

    async def stop(self) -> Dict:
        """
        Stop OpenVPN service

        Returns:
            Dictionary with service control result
        """
        import asyncssh

        async with asyncssh.connect(
            self.server.host,
            username=self.server.ssh_username,
            client_keys=[self.server.ssh_key_path] if self.server.ssh_key_path else None,
            password=self.server.ssh_password if not self.server.ssh_key_path else None,
            known_hosts=None,
        ) as conn:
            result = await conn.run("sudo systemctl stop openvpn@server", check=False)

            return {
                "success": result.exit_status == 0,
                "output": result.stdout,
                "error": result.stderr,
            }

    async def restart(self) -> Dict:
        """
        Restart OpenVPN service

        Returns:
            Dictionary with service control result
        """
        import asyncssh

        async with asyncssh.connect(
            self.server.host,
            username=self.server.ssh_username,
            client_keys=[self.server.ssh_key_path] if self.server.ssh_key_path else None,
            password=self.server.ssh_password if not self.server.ssh_key_path else None,
            known_hosts=None,
        ) as conn:
            result = await conn.run("sudo systemctl restart openvpn@server", check=False)

            return {
                "success": result.exit_status == 0,
                "output": result.stdout,
                "error": result.stderr,
            }
