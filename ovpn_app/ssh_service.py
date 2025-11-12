"""
SSH Service Module

Provides secure SSH connectivity with proper abstraction and error handling.
Follows SOLID principles and clean architecture patterns.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager

import paramiko
import asyncssh
from django.conf import settings

from .models import OpenVPNServer


logger = logging.getLogger(__name__)


@dataclass
class SSHCredentials:
    """Value object for SSH connection credentials"""
    hostname: str
    port: int
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_content: Optional[str] = None


@dataclass
class CommandResult:
    """Value object for command execution results"""
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    
    @property
    def output(self) -> str:
        """Combined output for display"""
        return self.stdout + self.stderr
    
    @property
    def error(self) -> str:
        """Alias for stderr for compatibility"""
        return self.stderr


class SSHConnectionError(Exception):
    """Raised when SSH connection fails"""
    pass


class SSHCommandError(Exception):
    """Raised when SSH command execution fails"""
    pass


class ISSHConnection(Protocol):
    """Interface for SSH connections"""
    
    async def execute_command(self, command: str) -> CommandResult:
        """Execute a command and return result"""
        ...
    
    async def close(self) -> None:
        """Close the connection"""
        ...


class ISSHService(ABC):
    """Abstract SSH Service interface"""
    
    @abstractmethod
    async def create_connection(self, credentials: SSHCredentials) -> ISSHConnection:
        """Create SSH connection"""
        pass
    
    @abstractmethod
    async def execute_command(
        self, 
        credentials: SSHCredentials, 
        command: str
    ) -> CommandResult:
        """Execute single command"""
        pass


class AsyncSSHConnection:
    """Async SSH connection wrapper"""
    
    def __init__(self, connection: asyncssh.SSHClientConnection):
        self._connection = connection
        self._closed = False
    
    async def execute_command(self, command: str) -> CommandResult:
        """Execute command and return structured result"""
        if self._closed:
            raise SSHConnectionError("Connection is closed")
        
        try:
            logger.info(f"Executing SSH command: {command}")
            result = await self._connection.run(command)
            
            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status,
                success=result.exit_status == 0
            )
        except Exception as e:
            logger.error(f"SSH command execution failed: {e}")
            raise SSHCommandError(f"Command execution failed: {e}")
    
    async def close(self) -> None:
        """Close SSH connection"""
        if not self._closed:
            self._connection.close()
            await self._connection.wait_closed()
            self._closed = True
            logger.info("SSH connection closed")


class SSHService(ISSHService):
    """Production SSH service implementation"""
    
    def __init__(self):
        self._connections: Dict[str, AsyncSSHConnection] = {}
    
    async def create_connection(self, credentials: SSHCredentials) -> AsyncSSHConnection:
        """Create and return SSH connection"""
        connection_key = f"{credentials.username}@{credentials.hostname}:{credentials.port}"
        
        try:
            # Prepare connection options
            connect_kwargs = {
                'host': credentials.hostname,
                'port': credentials.port,
                'username': credentials.username,
                'known_hosts': None,  # In production, use proper known_hosts
            }
            
            # Add authentication method
            if credentials.private_key_content:
                # Import key from string content
                try:
                    key = asyncssh.import_private_key(credentials.private_key_content)
                    connect_kwargs['client_keys'] = [key]
                except Exception as e:
                    logger.error(f"Failed to import private key: {e}")
                    raise SSHConnectionError(f"Invalid private key format: {e}")
            elif credentials.private_key_path:
                connect_kwargs['client_keys'] = [credentials.private_key_path]
            elif credentials.password:
                connect_kwargs['password'] = credentials.password
            else:
                raise SSHConnectionError("No authentication method provided")
            
            # Create connection
            logger.info(f"Creating SSH connection to {connection_key}")
            conn = await asyncssh.connect(**connect_kwargs)
            
            ssh_connection = AsyncSSHConnection(conn)
            self._connections[connection_key] = ssh_connection
            
            logger.info(f"SSH connection established to {connection_key}")
            return ssh_connection
            
        except Exception as e:
            logger.error(f"Failed to create SSH connection: {e}")
            raise SSHConnectionError(f"Connection failed: {e}")
    
    async def execute_command(
        self, 
        credentials: SSHCredentials, 
        command: str
    ) -> CommandResult:
        """Execute single command with temporary connection"""
        connection = await self.create_connection(credentials)
        try:
            return await connection.execute_command(command)
        finally:
            await connection.close()
    
    @asynccontextmanager
    async def connection_context(self, credentials: SSHCredentials):
        """Context manager for SSH connections"""
        connection = await self.create_connection(credentials)
        try:
            yield connection
        finally:
            await connection.close()
    
    async def close_all_connections(self) -> None:
        """Close all active connections"""
        for connection in self._connections.values():
            await connection.close()
        self._connections.clear()


class SSHCredentialsFactory:
    """Factory for creating SSH credentials from server models"""
    
    @staticmethod
    def from_server(server: OpenVPNServer) -> SSHCredentials:
        """Create SSH credentials from OpenVPN server model"""
        return SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password if hasattr(server, 'ssh_password') else None,
            private_key_content=server.ssh_private_key if hasattr(server, 'ssh_private_key') else None
        )
    
    @staticmethod
    def create_credentials(
        hostname: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_content: Optional[str] = None
    ) -> SSHCredentials:
        """Create SSH credentials manually"""
        return SSHCredentials(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            private_key_path=private_key_path,
            private_key_content=private_key_content
        )


class OpenVPNCommandBuilder:
    """Builder for OpenVPN related commands"""
    
    @staticmethod
    def install_openvpn() -> List[str]:
        """Commands to install OpenVPN (non-interactive)"""
        return [
            "sudo apt update -y",
            "sudo DEBIAN_FRONTEND=noninteractive apt install -y openvpn easy-rsa",
            "sudo systemctl enable openvpn",
            "sudo mkdir -p /etc/openvpn",
            "sudo mkdir -p /var/log/openvpn",
        ]
    
    @staticmethod
    def check_sudo_access() -> str:
        """Check if user has sudo access"""
        return "sudo -n true"
    
    @staticmethod
    def check_openvpn_installed() -> str:
        """Check if OpenVPN is installed"""
        return "dpkg -l | grep openvpn"
    
    @staticmethod
    def check_openvpn_status() -> str:
        """Command to check OpenVPN status"""
        return "sudo systemctl status openvpn@server --no-pager -l"
    
    @staticmethod
    def start_openvpn() -> str:
        """Command to start OpenVPN"""
        return "sudo systemctl start openvpn@server"
    
    @staticmethod
    def stop_openvpn() -> str:
        """Command to stop OpenVPN"""
        return "sudo systemctl stop openvpn@server"
    
    @staticmethod
    def restart_openvpn() -> str:
        """Command to restart OpenVPN"""
        return "sudo systemctl restart openvpn@server"
    
    @staticmethod
    def enable_openvpn() -> str:
        """Command to enable OpenVPN service"""
        return "sudo systemctl enable openvpn@server"
    
    @staticmethod
    def disable_openvpn() -> str:
        """Command to disable OpenVPN service"""
        return "sudo systemctl disable openvpn@server"
    
    @staticmethod
    def get_system_info() -> List[str]:
        """Commands to get system information"""
        return [
            "uname -a",
            "lsb_release -a",
            "free -h",
            "df -h /",
        ]
    
    @staticmethod
    def generate_server_config(
        port: int,
        protocol: str,
        subnet: str,
        netmask: str
    ) -> str:
        """Command to generate server configuration"""
        return f"""sudo tee /etc/openvpn/server.conf > /dev/null << 'EOF'
port {port}
proto {protocol}
dev tun
ca ca.crt
cert server.crt
key server.key
dh dh.pem
server {subnet} {netmask}
ifconfig-pool-persist ipp.txt
keepalive 10 120
cipher AES-256-CBC
persist-key
persist-tun
status openvpn-status.log
verb 3
explicit-exit-notify 1
EOF"""


class SSHConnectionPool:
    """Pool for managing SSH connections"""
    
    def __init__(self, max_connections: int = 10):
        self._max_connections = max_connections
        self._pool: Dict[str, AsyncSSHConnection] = {}
        self._ssh_service = SSHService()
    
    async def get_connection(self, credentials: SSHCredentials) -> AsyncSSHConnection:
        """Get connection from pool or create new one"""
        key = self._get_connection_key(credentials)
        
        if key in self._pool:
            return self._pool[key]
        
        if len(self._pool) >= self._max_connections:
            await self._cleanup_oldest_connection()
        
        connection = await self._ssh_service.create_connection(credentials)
        self._pool[key] = connection
        return connection
    
    def _get_connection_key(self, credentials: SSHCredentials) -> str:
        """Generate unique key for connection"""
        return f"{credentials.username}@{credentials.hostname}:{credentials.port}"
    
    async def _cleanup_oldest_connection(self) -> None:
        """Remove oldest connection from pool"""
        if self._pool:
            key = next(iter(self._pool))
            connection = self._pool.pop(key)
            await connection.close()
    
    async def close_all(self) -> None:
        """Close all connections in pool"""
        for connection in self._pool.values():
            await connection.close()
        self._pool.clear()


# Dependency injection container
class SSHServiceContainer:
    """Container for SSH service dependencies"""
    
    _ssh_service: Optional[ISSHService] = None
    _connection_pool: Optional[SSHConnectionPool] = None
    
    @classmethod
    def get_ssh_service(cls) -> ISSHService:
        """Get SSH service instance"""
        if cls._ssh_service is None:
            cls._ssh_service = SSHService()
        return cls._ssh_service
    
    @classmethod
    def get_connection_pool(cls) -> SSHConnectionPool:
        """Get connection pool instance"""
        if cls._connection_pool is None:
            cls._connection_pool = SSHConnectionPool()
        return cls._connection_pool
    
    @classmethod
    def set_ssh_service(cls, service: ISSHService) -> None:
        """Set custom SSH service (for testing)"""
        cls._ssh_service = service
