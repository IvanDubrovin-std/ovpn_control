"""
Monitoring Service
Single Responsibility: Handle all server monitoring and connection management
"""

import uuid
from typing import Dict, List

from ovpn_app.agent.client import AgentClient
from ovpn_app.agent.deployment import AgentDeployer
from ovpn_app.models import OpenVPNServer
from ovpn_app.ssh_service import SSHCredentials


class MonitoringService:
    """
    Service for monitoring OpenVPN server status and connections

    Follows SOLID principles:
    - Single Responsibility: Only handles monitoring operations
    - Open/Closed: Extensible through agent commands
    - Liskov Substitution: Can be replaced with mock for testing
    - Interface Segregation: Clean, focused interface
    - Dependency Inversion: Depends on abstract AgentClient
    """

    def __init__(self, server: OpenVPNServer):
        """
        Initialize monitoring service

        Args:
            server: OpenVPNServer instance to monitor
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

    async def get_status(self) -> Dict:
        """
        Get server status and active connections

        Returns:
            Dictionary with:
                - is_running: Boolean indicating if OpenVPN is running
                - connections: List of active connections
                - stats: Statistics (connected_clients, total_bytes_in, total_bytes_out)
                - version: OpenVPN version (optional)

        Raises:
            Exception: If agent execution fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Execute get-status command via agent
        task_id = str(uuid.uuid4())
        result = await self.agent_client.get_status(
            self.credentials,
            task_id,
        )

        # Even if status is failed, we might have useful data
        import json
        status_data = json.loads(result.get("output", "{}"))

        return status_data

    async def disconnect_client(self, client_name: str) -> Dict:
        """
        Disconnect a specific client from the server

        Args:
            client_name: Common name of the client to disconnect

        Returns:
            Dictionary with disconnect status

        Raises:
            Exception: If agent execution fails
        """
        # Ensure agent is deployed
        await self.deployer.deploy_agent(self.credentials)

        # Execute disconnect-client command via agent
        task_id = str(uuid.uuid4())
        result = await self.agent_client.disconnect_client(
            self.credentials,
            task_id,
            client_name,
        )

        if result.get("status") != "success":
            raise Exception(result.get("message", "Failed to disconnect client"))

        # Parse output
        import json
        disconnect_data = json.loads(result.get("output", "{}"))

        return disconnect_data

    async def get_connection_stats(self) -> Dict:
        """
        Get aggregated connection statistics

        Returns:
            Dictionary with statistics:
                - connected_clients: Number of active connections
                - total_bytes_in: Total bytes received
                - total_bytes_out: Total bytes sent

        Raises:
            Exception: If status retrieval fails
        """
        status = await self.get_status()
        return status.get("stats", {
            "connected_clients": 0,
            "total_bytes_in": 0,
            "total_bytes_out": 0,
        })

    async def get_active_connections(self) -> List[Dict]:
        """
        Get list of active connections with details

        Returns:
            List of connection dictionaries with:
                - common_name: Client certificate name
                - real_address: Client's real IP:port
                - virtual_address: Client's VPN IP
                - bytes_received: Bytes received from client
                - bytes_sent: Bytes sent to client
                - connected_since: Connection timestamp

        Raises:
            Exception: If status retrieval fails
        """
        status = await self.get_status()
        return status.get("connections", [])

    async def is_running(self) -> bool:
        """
        Check if OpenVPN service is running

        Returns:
            True if service is running, False otherwise
        """
        try:
            status = await self.get_status()
            return status.get("is_running", False)
        except Exception:
            return False
