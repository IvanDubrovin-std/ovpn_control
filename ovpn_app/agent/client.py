"""
Agent Client Module

Client for interacting with ovpn-agent on remote servers
"""

import json
import logging
from typing import Dict, Optional

from ..models import OpenVPNServer
from ..ssh_service import SSHCredentials, SSHService

logger = logging.getLogger(__name__)


class AgentClient:
    """Client for executing commands via agent"""

    def __init__(self, ssh_service: Optional[SSHService] = None):
        """
        Initialize agent client

        Args:
            ssh_service: SSH service for communication
        """
        self.ssh_service = ssh_service or SSHService()

    async def execute_via_agent(
        self, credentials: SSHCredentials, command: str, task_id: str, config: Optional[Dict] = None
    ) -> Dict:
        """
        Execute command via agent on remote server

        Args:
            credentials: SSH credentials
            command: Command to execute (install, configure, reinstall)
            task_id: Task identifier
            config: Configuration dictionary

        Returns:
            Result dictionary
        """
        logger.info(f"Executing '{command}' via agent on {credentials.hostname}")

        # Build command with inline config or separate file
        if config:
            config_json = json.dumps(config)
            config_path = f"/tmp/agent-config-{task_id}.json"

            # Execute in single SSH: create config → run agent (capture only agent output) → cleanup
            agent_cmd = f"""cat > {config_path} << 'EOF'
{config_json}
EOF
/usr/local/bin/ovpn-agent {command} --task-id {task_id} --config {config_path}
AGENT_EXIT_CODE=$?
rm -f {config_path}
exit $AGENT_EXIT_CODE"""
        else:
            # No config needed
            agent_cmd = f"/usr/local/bin/ovpn-agent {command} --task-id {task_id}"

        logger.info(f"Agent command: {agent_cmd}")

        result = await self.ssh_service.execute_command(credentials, agent_cmd)

        # Debug: Log raw output
        logger.info(f"Agent stdout length: {len(result.stdout)} chars")
        logger.info(f"Agent stderr length: {len(result.stderr)} chars")
        logger.info(f"Agent exit code: {result.exit_code}")
        logger.info(f"Agent stdout first 500 chars: {result.stdout[:500]}")
        logger.info(f"Agent stdout last 500 chars: {result.stdout[-500:]}")

        # Parse JSON result
        try:
            result_data = json.loads(result.stdout)
            return result_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response: {e}")
            logger.error(f"Full stdout: {result.stdout[:2000]}")
            logger.error(f"Full stderr: {result.stderr[:2000]}")
            return {
                "status": "failed",
                "message": "Invalid response from agent",
                "output": result.stdout,
                "error": result.stderr,
            }

    async def install_openvpn(self, credentials: SSHCredentials, task_id: str) -> Dict:
        """
        Install OpenVPN via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier

        Returns:
            Result dictionary
        """
        return await self.execute_via_agent(credentials, "install", task_id)

    async def configure_openvpn(
        self, credentials: SSHCredentials, task_id: str, config: Dict
    ) -> Dict:
        """
        Configure OpenVPN via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier
            config: Server configuration

        Returns:
            Result dictionary
        """
        return await self.execute_via_agent(credentials, "configure", task_id, config)

    async def reinstall_openvpn(
        self, credentials: SSHCredentials, task_id: str, config: Dict
    ) -> Dict:
        """
        Reinstall OpenVPN via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier
            config: Server configuration

        Returns:
            Result dictionary
        """
        return await self.execute_via_agent(credentials, "reinstall", task_id, config)

    async def list_clients(self, credentials: SSHCredentials, task_id: str) -> Dict:
        """
        List all clients on server via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier

        Returns:
            Result dictionary with clients list
        """
        return await self.execute_via_agent(credentials, "list-clients", task_id)

    async def create_client(
        self, credentials: SSHCredentials, task_id: str, client_name: str, config: Dict
    ) -> Dict:
        """
        Create client certificate via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier
            client_name: Name of the client
            config: Configuration dictionary

        Returns:
            Result dictionary with client data
        """
        # Build command with client name
        config_json = json.dumps(config)
        config_path = f"/tmp/agent-config-{task_id}.json"

        agent_cmd = f"""cat > {config_path} << 'EOF'
{config_json}
EOF
/usr/local/bin/ovpn-agent create-client --task-id {task_id} --config {config_path} --client-name {client_name}
AGENT_EXIT_CODE=$?
rm -f {config_path}
exit $AGENT_EXIT_CODE"""

        logger.info(f"Agent command: {agent_cmd}")

        result = await self.ssh_service.execute_command(credentials, agent_cmd)

        # Parse JSON result
        try:
            result_data = json.loads(result.stdout)
            return result_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response: {e}")
            return {
                "status": "failed",
                "message": "Invalid response from agent",
                "output": result.stdout,
                "error": result.stderr,
            }

    async def revoke_client(
        self, credentials: SSHCredentials, task_id: str, client_name: str
    ) -> Dict:
        """
        Revoke client certificate via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier
            client_name: Name of the client to revoke

        Returns:
            Result dictionary
        """
        agent_cmd = f"/usr/local/bin/ovpn-agent revoke-client --task-id {task_id} --client-name {client_name}"

        logger.info(f"Agent command: {agent_cmd}")

        result = await self.ssh_service.execute_command(credentials, agent_cmd)

        try:
            result_data = json.loads(result.stdout)
            return result_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response: {e}")
            return {
                "status": "failed",
                "message": "Invalid response from agent",
                "output": result.stdout,
                "error": result.stderr,
            }

    async def get_status(self, credentials: SSHCredentials, task_id: str) -> Dict:
        """
        Get server status and connections via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier

        Returns:
            Result dictionary with status and connections
        """
        return await self.execute_via_agent(credentials, "get-status", task_id)

    async def disconnect_client(
        self, credentials: SSHCredentials, task_id: str, client_name: str
    ) -> Dict:
        """
        Disconnect client via agent

        Args:
            credentials: SSH credentials
            task_id: Task identifier
            client_name: Name of the client to disconnect

        Returns:
            Result dictionary
        """
        agent_cmd = f"/usr/local/bin/ovpn-agent disconnect-client --task-id {task_id} --client-name {client_name}"

        logger.info(f"Agent command: {agent_cmd}")

        result = await self.ssh_service.execute_command(credentials, agent_cmd)

        try:
            result_data = json.loads(result.stdout)
            return result_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response: {e}")
            return {
                "status": "failed",
                "message": "Invalid response from agent",
                "output": result.stdout,
                "error": result.stderr,
            }

    @classmethod
    def from_server(cls, server: OpenVPNServer) -> "AgentClient":
        """
        Create agent client for specific server

        Args:
            server: OpenVPNServer instance

        Returns:
            AgentClient
        """
        return cls()
