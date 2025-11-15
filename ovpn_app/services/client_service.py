"""
Client Management Service
Single Responsibility: Handle all client certificate operations via agent
"""

import uuid
from typing import Dict, List, Optional

from ovpn_app.agent.client import AgentClient
from ovpn_app.agent.deployment import AgentDeployer
from ovpn_app.config import AgentConfig
from ovpn_app.models import ClientCertificate, OpenVPNServer
from ovpn_app.ssh_service import SSHCredentials


class ClientManagementService:
    """
    Service for managing OpenVPN client certificates

    Follows SOLID principles:
    - Single Responsibility: Only handles client operations
    - Open/Closed: Extensible through agent commands
    - Liskov Substitution: Can be replaced with mock for testing
    - Interface Segregation: Clean, focused interface
    - Dependency Inversion: Depends on abstract AgentClient
    """

    def __init__(self, server: OpenVPNServer):
        """
        Initialize client management service

        Args:
            server: OpenVPNServer instance to manage clients for
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

    async def create_client(self, client_name: str) -> Dict:
        """
        Create a new client certificate

        Args:
            client_name: Name for the client certificate

        Returns:
            Dictionary with client data (name, cert_file, key_file, ovpn_file)

        Raises:
            Exception: If agent execution fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Build configuration
        config = AgentConfig.from_server(self.server)
        config_dict = config.to_dict()
        config_dict["server_host"] = self.server.host

        # Execute create-client command via agent
        task_id = str(uuid.uuid4())
        result = await self.agent_client.create_client(
            self.credentials,
            task_id,
            client_name,
            config_dict,
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to create client"))

        # Parse output
        import json
        client_data = json.loads(result.get("output", "{}"))

        return client_data

    async def revoke_client(self, client_name: str) -> Dict:
        """
        Revoke a client certificate

        Args:
            client_name: Name of the client to revoke

        Returns:
            Dictionary with revocation status

        Raises:
            Exception: If agent execution fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Execute revoke-client command via agent
        task_id = str(uuid.uuid4())
        result = await self.agent_client.revoke_client(
            self.credentials,
            task_id,
            client_name,
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to revoke client"))

        # Parse output
        import json
        revoke_data = json.loads(result.get("output", "{}"))

        return revoke_data

    async def list_clients(self) -> List[Dict]:
        """
        List all clients on the server

        Returns:
            List of client dictionaries with certificate information

        Raises:
            Exception: If agent execution fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Execute list-clients command via agent
        task_id = str(uuid.uuid4())
        result = await self.agent_client.list_clients(
            self.credentials,
            task_id,
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to list clients"))

        # Parse output
        import json
        clients = json.loads(result.get("output", "[]"))

        return clients

    async def download_client_config(self, client_name: str) -> bytes:
        """
        Download .ovpn configuration file for a client

        Args:
            client_name: Name of the client

        Returns:
            Bytes content of the .ovpn file

        Raises:
            Exception: If file download fails
        """
        # Use SSHService to download file
        from ovpn_app.ssh_service import SSHService

        ssh_service = SSHService()
        remote_path = f"/home/{self.server.ssh_username}/client-configs/{client_name}.ovpn"

        # Download file using SFTP
        content = await ssh_service.download_file(self.credentials, remote_path)
        return content
