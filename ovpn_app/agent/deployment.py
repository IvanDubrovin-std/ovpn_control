"""
Agent Deployment Module

Automatically deploys and manages ovpn-agent on remote OpenVPN servers
"""

import logging
from pathlib import Path
from typing import Optional

from ..ssh_service import CommandResult, SSHCredentials, SSHService

logger = logging.getLogger(__name__)


class AgentDeployer:
    """Deploy and manage agent on remote servers"""

    def __init__(self, ssh_service: Optional[SSHService] = None):
        """
        Initialize deployer

        Args:
            ssh_service: SSH service for remote connections
        """
        self.ssh_service = ssh_service or SSHService()
        self.agent_path = Path(__file__).parent / "ovpn_agent.py"

    async def is_agent_installed(self, credentials: SSHCredentials) -> bool:
        """
        Check if agent is installed on server

        Args:
            credentials: SSH credentials

        Returns:
            True if agent is installed
        """
        result = await self.ssh_service.execute_command(
            credentials, "test -f /usr/local/bin/ovpn-agent && echo 'installed'"
        )

        return "installed" in result.stdout

    async def deploy_agent(self, credentials: SSHCredentials) -> CommandResult:
        """
        Deploy agent to remote server

        Args:
            credentials: SSH credentials

        Returns:
            CommandResult
        """
        logger.info(f"Deploying agent to {credentials.hostname}")

        # Read agent code
        if not self.agent_path.exists():
            logger.error(f"Agent file not found: {self.agent_path}")
            return CommandResult(
                stdout="",
                stderr=f"Agent file not found: {self.agent_path}",
                exit_code=1,
                success=False,
            )

        with open(self.agent_path) as f:
            agent_code = f.read()

        # Deploy agent in single SSH command (batched)
        temp_path = "/tmp/ovpn-agent.py"
        deploy_cmd = f"""cat > {temp_path} << 'AGENT_EOF'
{agent_code}
AGENT_EOF
sudo mv {temp_path} /usr/local/bin/ovpn-agent && \
sudo chmod +x /usr/local/bin/ovpn-agent && \
sudo chown root:root /usr/local/bin/ovpn-agent"""

        result = await self.ssh_service.execute_command(credentials, deploy_cmd)

        if not result.success:
            logger.error(f"Failed to deploy agent: {result.stderr}")
            return result

        logger.info("Agent deployed successfully")

        return CommandResult(
            stdout="Agent deployed to /usr/local/bin/ovpn-agent",
            stderr="",
            exit_code=0,
            success=True,
        )

    async def install_agent_service(self, credentials: SSHCredentials) -> CommandResult:
        """
        Install agent as systemd service

        Args:
            credentials: SSH credentials

        Returns:
            CommandResult
        """
        logger.info("Installing agent systemd service")

        service_content = """[Unit]
Description=OpenVPN Management Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/ovpn-agent daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

        # Create service file
        create_service_cmd = f"sudo tee /etc/systemd/system/ovpn-agent.service > /dev/null << 'EOF'\n{service_content}\nEOF"

        result = await self.ssh_service.execute_command(credentials, create_service_cmd)

        if not result.success:
            return result

        # Enable and start service
        systemd_commands = [
            "sudo systemctl daemon-reload",
            "sudo systemctl enable ovpn-agent",
            "sudo systemctl start ovpn-agent",
        ]

        for cmd in systemd_commands:
            result = await self.ssh_service.execute_command(credentials, cmd)
            if not result.success:
                logger.warning(f"Service setup command failed: {cmd}")

        return CommandResult(
            stdout="Agent service installed",
            stderr="",
            exit_code=0,
            success=True,
        )

    async def remove_agent(self, credentials: SSHCredentials) -> CommandResult:
        """
        Remove agent from server

        Args:
            credentials: SSH credentials

        Returns:
            CommandResult
        """
        logger.info("Removing agent")

        commands = [
            "sudo systemctl stop ovpn-agent 2>/dev/null || true",
            "sudo systemctl disable ovpn-agent 2>/dev/null || true",
            "sudo rm -f /etc/systemd/system/ovpn-agent.service",
            "sudo systemctl daemon-reload",
            "sudo rm -f /usr/local/bin/ovpn-agent",
        ]

        for cmd in commands:
            await self.ssh_service.execute_command(credentials, cmd)

        return CommandResult(
            stdout="Agent removed",
            stderr="",
            exit_code=0,
            success=True,
        )
