"""
Stunnel Service for OpenVPN TCP Tunneling

Implements clean architecture with SOLID principles for Stunnel management.
Provides installation, configuration, and lifecycle management for Stunnel.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from .constants import ErrorMessages, StunnelConfig as StunnelConfigConstants, SuccessMessages
from .exceptions import (
    StunnelCertificateError,
    StunnelConfigurationError,
    StunnelInstallationError,
    StunnelServiceError,
)
from .ssh_service import CommandResult, SSHCredentials, SSHService

logger = logging.getLogger(__name__)


# ============================================================================
# Interfaces (ISP - Interface Segregation Principle)
# ============================================================================


class IStunnelInstaller(ABC):
    """Interface for Stunnel installation operations"""

    @abstractmethod
    async def check_installed(self, credentials: SSHCredentials) -> bool:
        """Check if Stunnel is installed"""

    @abstractmethod
    async def install(self, credentials: SSHCredentials) -> CommandResult:
        """Install Stunnel on remote server"""


class IStunnelConfigurator(ABC):
    """Interface for Stunnel configuration operations"""

    @abstractmethod
    async def configure(
        self,
        credentials: SSHCredentials,
        stunnel_port: int,
        openvpn_port: int,
        server_name: str,
    ) -> CommandResult:
        """Configure Stunnel"""

    @abstractmethod
    async def generate_certificate(
        self, credentials: SSHCredentials, server_name: str, server_ip: str
    ) -> CommandResult:
        """Generate SSL certificate for Stunnel"""


class IStunnelService(ABC):
    """Interface for Stunnel service operations"""

    @abstractmethod
    async def start(self, credentials: SSHCredentials) -> CommandResult:
        """Start Stunnel service"""

    @abstractmethod
    async def stop(self, credentials: SSHCredentials) -> CommandResult:
        """Stop Stunnel service"""

    @abstractmethod
    async def restart(self, credentials: SSHCredentials) -> CommandResult:
        """Restart Stunnel service"""

    @abstractmethod
    async def status(self, credentials: SSHCredentials) -> CommandResult:
        """Check Stunnel service status"""


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class StunnelInstallResult:
    """Result of Stunnel installation"""

    success: bool
    message: str
    output: str
    error: str = ""


# ============================================================================
# Stunnel Installer (SRP - Single Responsibility Principle)
# ============================================================================


class StunnelInstaller(IStunnelInstaller):
    """
    Handles Stunnel installation on remote servers

    Responsibilities:
    - Check if Stunnel is installed
    - Install Stunnel package
    - Create necessary directories
    """

    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service

    async def check_installed(self, credentials: SSHCredentials) -> bool:
        """
        Check if Stunnel is installed on server

        Args:
            credentials: SSH connection credentials

        Returns:
            bool: True if installed, False otherwise
        """
        try:
            result = await self.ssh_service.execute_command(
                credentials, "which stunnel4 || which stunnel"
            )
            return result.success and len(result.stdout.strip()) > 0
        except Exception as e:
            logger.error(f"Error checking Stunnel installation: {e}")
            return False

    async def install(self, credentials: SSHCredentials) -> CommandResult:
        """
        Install Stunnel on remote server

        Args:
            credentials: SSH connection credentials

        Returns:
            CommandResult: Installation result

        Raises:
            StunnelInstallationError: If installation fails
        """
        try:
            logger.info("Starting Stunnel installation")

            # Check if already installed
            if await self.check_installed(credentials):
                logger.info("Stunnel already installed")
                return CommandResult(
                    stdout="Stunnel is already installed",
                    stderr="",
                    exit_code=0,
                    success=True,
                )

            # Install commands
            commands = self._get_install_commands()
            all_output = []

            for command in commands:
                logger.info(f"Executing: {command}")
                result = await self.ssh_service.execute_command(credentials, command)

                all_output.append(f"$ {command}")
                if result.stdout:
                    all_output.append(result.stdout)
                if result.stderr:
                    all_output.append(f"STDERR: {result.stderr}")

                if not result.success and not command.startswith("sudo"):
                    logger.error(f"Command failed: {command}")
                    raise StunnelInstallationError(
                        credentials.hostname, f"Command failed: {command}"
                    )

            # Verify installation
            if not await self.check_installed(credentials):
                raise StunnelInstallationError(
                    credentials.hostname, "Installation verification failed"
                )

            logger.info("Stunnel installation completed successfully")
            return CommandResult(stdout="\n".join(all_output), stderr="", exit_code=0, success=True)

        except StunnelInstallationError:
            raise
        except Exception as e:
            logger.error(f"Exception in install_stunnel: {e}")
            raise StunnelInstallationError(credentials.hostname, str(e))

    def _get_install_commands(self) -> List[str]:
        """Get list of commands for Stunnel installation"""
        return [
            "sudo apt update -y",
            "sudo DEBIAN_FRONTEND=noninteractive apt install -y stunnel4",
            "sudo systemctl enable stunnel4",
            f"sudo mkdir -p {StunnelConfigConstants.CONFIG_DIR}",
            f"sudo mkdir -p {StunnelConfigConstants.LOG_DIR}",
            f"sudo chown stunnel4:stunnel4 {StunnelConfigConstants.LOG_DIR}",
            f"sudo chmod 755 {StunnelConfigConstants.LOG_DIR}",
            "sudo mkdir -p /var/run/stunnel4",
            "sudo chown stunnel4:stunnel4 /var/run/stunnel4",
            "sudo chmod 755 /var/run/stunnel4",
            "echo 'Stunnel installation completed'",
        ]


# ============================================================================
# Stunnel Configurator (SRP - Single Responsibility Principle)
# ============================================================================


class StunnelConfigurator(IStunnelConfigurator):
    """
    Handles Stunnel configuration

    Responsibilities:
    - Generate Stunnel configuration files
    - Generate SSL certificates
    - Deploy configuration to server
    """

    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service

    async def configure(
        self,
        credentials: SSHCredentials,
        stunnel_port: int,
        openvpn_port: int,
        server_name: str,
    ) -> CommandResult:
        """
        Configure Stunnel on server

        Args:
            credentials: SSH connection credentials
            stunnel_port: External port for clients
            openvpn_port: Internal OpenVPN port
            server_name: Server name for logging

        Returns:
            CommandResult: Configuration result

        Raises:
            StunnelConfigurationError: If configuration fails
        """
        try:
            logger.info(f"Configuring Stunnel on {server_name}")

            # Generate configuration
            config_content = self._generate_config(stunnel_port, openvpn_port)

            # Deploy configuration
            commands = [
                # Create config file
                f"sudo tee {StunnelConfigConstants.CONFIG_FILE} > /dev/null << 'EOF'\n{config_content}\nEOF",
                # Set permissions
                f"sudo chmod 644 {StunnelConfigConstants.CONFIG_FILE}",
                # Enable stunnel4 in defaults
                "echo 'ENABLED=1' | sudo tee /etc/default/stunnel4",
                # Create PID directory
                "sudo mkdir -p /var/run/stunnel",
                "sudo chown stunnel4:stunnel4 /var/run/stunnel",
            ]

            all_output = []
            for command in commands:
                result = await self.ssh_service.execute_command(credentials, command)
                command_display = command[:50] if len(command) > 50 else command
                all_output.append(f"$ {command_display}...")
                if result.stderr and result.exit_code != 0:
                    all_output.append(f"ERROR: {result.stderr}")

                if result.exit_code != 0:
                    raise StunnelConfigurationError(
                        server_name, f"Failed to execute: {command[:50]}"
                    )

            logger.info("Stunnel configuration completed successfully")
            return CommandResult(stdout="\n".join(all_output), stderr="", exit_code=0, success=True)

        except StunnelConfigurationError:
            raise
        except Exception as e:
            logger.error(f"Exception in configure_stunnel: {e}")
            raise StunnelConfigurationError(server_name, str(e))

    async def generate_certificate(
        self, credentials: SSHCredentials, server_name: str, server_ip: str
    ) -> CommandResult:
        """
        Generate self-signed SSL certificate for Stunnel

        Args:
            credentials: SSH connection credentials
            server_name: Server name
            server_ip: Server IP address

        Returns:
            CommandResult: Certificate generation result

        Raises:
            StunnelCertificateError: If certificate generation fails
        """
        try:
            logger.info(f"Generating Stunnel certificate for {server_name}")

            # Generate self-signed certificate
            cert_command = (
                "sudo openssl req -new -x509 -days 3650 -nodes "
                f"-out {StunnelConfigConstants.CERT_FILE} "
                f"-keyout {StunnelConfigConstants.KEY_FILE} "
                f'-subj "/C=RU/ST=Moscow/L=Moscow/O=OpenVPN/CN={server_ip}"'
            )

            result = await self.ssh_service.execute_command(credentials, cert_command)

            if result.exit_code != 0:
                raise StunnelCertificateError(
                    server_name, f"Certificate generation failed: {result.stderr}"
                )

            # Set permissions
            perm_commands = [
                f"sudo chmod 600 {StunnelConfigConstants.KEY_FILE}",
                f"sudo chmod 644 {StunnelConfigConstants.CERT_FILE}",
                f"sudo chown stunnel4:stunnel4 {StunnelConfigConstants.CERT_FILE}",
                f"sudo chown stunnel4:stunnel4 {StunnelConfigConstants.KEY_FILE}",
            ]

            for cmd in perm_commands:
                await self.ssh_service.execute_command(credentials, cmd)

            logger.info("Stunnel certificate generated successfully")
            return CommandResult(
                stdout="Certificate generated successfully",
                stderr="",
                exit_code=0,
                success=True,
            )

        except StunnelCertificateError:
            raise
        except Exception as e:
            logger.error(f"Exception in generate_certificate: {e}")
            raise StunnelCertificateError(server_name, str(e))

    def _generate_config(self, stunnel_port: int, openvpn_port: int) -> str:
        """
        Generate Stunnel configuration content

        Args:
            stunnel_port: External port for clients
            openvpn_port: Internal OpenVPN port

        Returns:
            str: Configuration file content
        """
        config = f"""# Stunnel configuration for OpenVPN TCP tunneling
# Auto-generated by OpenVPN Management System

# Global options
foreground = no
debug = {StunnelConfigConstants.DEBUG_LEVEL}
# PID file used by init/systemd scripts - must be present for LSB init wrapper
pid = {StunnelConfigConstants.PID_FILE}
# Ensure stunnel drops privileges to the stunnel4 user (Debian package user)
setuid = stunnel4
setgid = stunnel4
output = {StunnelConfigConstants.LOG_FILE}

# Certificate files
cert = {StunnelConfigConstants.CERT_FILE}
key = {StunnelConfigConstants.KEY_FILE}

# Security options
ciphers = {StunnelConfigConstants.DEFAULT_CIPHER}
TIMEOUTclose = 0
options = {StunnelConfigConstants.TLS_OPTIONS}

# Service definition
[openvpn]
client = no
accept = 0.0.0.0:{stunnel_port}
connect = 127.0.0.1:{openvpn_port}
TIMEOUTclose = 0
"""
        return config


# ============================================================================
# Stunnel Service Manager (SRP - Single Responsibility Principle)
# ============================================================================


class StunnelServiceManager(IStunnelService):
    """
    Handles Stunnel service lifecycle

    Responsibilities:
    - Start/stop/restart Stunnel service
    - Check service status
    """

    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service

    async def start(self, credentials: SSHCredentials) -> CommandResult:
        """
        Start Stunnel service

        Args:
            credentials: SSH connection credentials

        Returns:
            CommandResult: Start operation result

        Raises:
            StunnelServiceError: If start fails
        """
        try:
            logger.info("Starting Stunnel service")
            result = await self.ssh_service.execute_command(
                credentials, f"sudo systemctl start {StunnelConfigConstants.SERVICE_NAME}"
            )

            if result.exit_code != 0:
                raise StunnelServiceError(
                    credentials.hostname, "start", f"Exit code: {result.exit_code}"
                )

            return result
        except StunnelServiceError:
            raise
        except Exception as e:
            raise StunnelServiceError(credentials.hostname, "start", str(e))

    async def stop(self, credentials: SSHCredentials) -> CommandResult:
        """
        Stop Stunnel service

        Args:
            credentials: SSH connection credentials

        Returns:
            CommandResult: Stop operation result

        Raises:
            StunnelServiceError: If stop fails
        """
        try:
            logger.info("Stopping Stunnel service")
            result = await self.ssh_service.execute_command(
                credentials, f"sudo systemctl stop {StunnelConfigConstants.SERVICE_NAME}"
            )

            if result.exit_code != 0:
                raise StunnelServiceError(
                    credentials.hostname, "stop", f"Exit code: {result.exit_code}"
                )

            return result
        except StunnelServiceError:
            raise
        except Exception as e:
            raise StunnelServiceError(credentials.hostname, "stop", str(e))

    async def restart(self, credentials: SSHCredentials) -> CommandResult:
        """
        Restart Stunnel service

        Args:
            credentials: SSH connection credentials

        Returns:
            CommandResult: Restart operation result

        Raises:
            StunnelServiceError: If restart fails
        """
        try:
            logger.info("Restarting Stunnel service")
            result = await self.ssh_service.execute_command(
                credentials, f"sudo systemctl restart {StunnelConfigConstants.SERVICE_NAME}"
            )

            if result.exit_code != 0:
                raise StunnelServiceError(
                    credentials.hostname, "restart", f"Exit code: {result.exit_code}"
                )

            return result
        except StunnelServiceError:
            raise
        except Exception as e:
            raise StunnelServiceError(credentials.hostname, "restart", str(e))

    async def status(self, credentials: SSHCredentials) -> CommandResult:
        """
        Check Stunnel service status

        Args:
            credentials: SSH connection credentials

        Returns:
            CommandResult: Status check result
        """
        try:
            logger.info("Checking Stunnel service status")
            result = await self.ssh_service.execute_command(
                credentials, f"sudo systemctl is-active {StunnelConfigConstants.SERVICE_NAME}"
            )

            return result
        except Exception as e:
            logger.error(f"Error checking Stunnel status: {e}")
            return CommandResult(stdout="", stderr=str(e), exit_code=1, success=False)


# ============================================================================
# Facade Pattern - Unified Stunnel Service
# ============================================================================


class StunnelManager:
    """
    Facade for all Stunnel operations

    Combines installer, configurator, and service manager into single interface.
    Follows Facade pattern for simplified client interaction.
    """

    def __init__(self, ssh_service: Optional[SSHService] = None):
        self.ssh_service = ssh_service or SSHService()
        self.installer = StunnelInstaller(self.ssh_service)
        self.configurator = StunnelConfigurator(self.ssh_service)
        self.service_manager = StunnelServiceManager(self.ssh_service)

    async def setup_stunnel(
        self,
        credentials: SSHCredentials,
        stunnel_port: int,
        openvpn_port: int,
        server_name: str,
        server_ip: str,
    ) -> StunnelInstallResult:
        """
        Complete Stunnel setup: install, configure, generate certs (without starting service)

        Args:
            credentials: SSH connection credentials
            stunnel_port: External port for clients
            openvpn_port: Internal OpenVPN port
            server_name: Server name
            server_ip: Server IP address

        Returns:
            StunnelInstallResult: Complete setup result
        """
        try:
            all_output = []

            # Step 1: Install
            logger.info("Step 1: Installing Stunnel")
            install_result = await self.installer.install(credentials)
            all_output.append("=== Installation ===")
            all_output.append(install_result.stdout)

            if not install_result.success:
                return StunnelInstallResult(
                    success=False,
                    message=ErrorMessages.STUNNEL_INSTALL_FAILED,
                    output="\n".join(all_output),
                    error=install_result.stderr,
                )

            # Step 2: Generate certificate
            logger.info("Step 2: Generating SSL certificate")
            cert_result = await self.configurator.generate_certificate(
                credentials, server_name, server_ip
            )
            all_output.append("=== Certificate Generation ===")
            all_output.append(cert_result.stdout)

            if not cert_result.success:
                return StunnelInstallResult(
                    success=False,
                    message=ErrorMessages.STUNNEL_CERT_GENERATION_FAILED,
                    output="\n".join(all_output),
                    error=cert_result.stderr,
                )

            # Step 3: Configure
            logger.info("Step 3: Configuring Stunnel")
            config_result = await self.configurator.configure(
                credentials, stunnel_port, openvpn_port, server_name
            )
            all_output.append("=== Configuration ===")
            all_output.append(config_result.stdout)

            if not config_result.success:
                return StunnelInstallResult(
                    success=False,
                    message=ErrorMessages.STUNNEL_CONFIG_FAILED,
                    output="\n".join(all_output),
                    error=config_result.stderr,
                )

            # Step 4: REMOVED - Do not start service automatically
            # User must click "Start Stunnel" button after setup completes
            logger.info("Stunnel setup completed successfully (service not started)")
            return StunnelInstallResult(
                success=True,
                message="Stunnel installed and configured. Click 'Start Stunnel' to activate.",
                output="\n".join(all_output),
            )

        except Exception as e:
            logger.error(f"Exception in setup_stunnel: {e}")
            return StunnelInstallResult(
                success=False,
                message=ErrorMessages.STUNNEL_CONFIG_FAILED,
                output="\n".join(all_output) if all_output else "",
                error=str(e),
            )

    async def check_status(self, credentials: SSHCredentials) -> bool:
        """
        Check if Stunnel is running

        Args:
            credentials: SSH connection credentials

        Returns:
            bool: True if running, False otherwise
        """
        try:
            result = await self.service_manager.status(credentials)
            return result.success and "active" in result.stdout.lower()
        except Exception as e:
            logger.error(f"Error checking Stunnel status: {e}")
            return False


# Export main classes
__all__ = [
    "IStunnelInstaller",
    "IStunnelConfigurator",
    "IStunnelService",
    "StunnelInstaller",
    "StunnelConfigurator",
    "StunnelServiceManager",
    "StunnelManager",
    "StunnelInstallResult",
]
