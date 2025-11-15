"""
Base classes and interfaces for API views
Following SOLID principles and clean architecture
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class BaseAPIView(ABC):
    """
    Base class for all API views
    Implements common error handling and response patterns
    """

    @staticmethod
    def success_response(
        message: str, data: Optional[Dict[str, Any]] = None, status_code: int = status.HTTP_200_OK
    ) -> Response:
        """
        Standard success response format

        Args:
            message: Success message
            data: Additional response data
            status_code: HTTP status code

        Returns:
            Response object with standard format
        """
        response_data = {"success": True, "message": message}
        if data:
            response_data.update(data)
        return Response(response_data, status=status_code)

    @staticmethod
    def error_response(
        error: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """
        Standard error response format

        Args:
            error: Error message
            status_code: HTTP status code
            data: Additional error data

        Returns:
            Response object with standard format
        """
        response_data = {"success": False, "error": error}
        if data:
            response_data.update(data)
        return Response(response_data, status=status_code)

    @classmethod
    def handle_exception(cls, exception: Exception, context: str = "") -> Response:
        """
        Handle exceptions with logging

        Args:
            exception: Caught exception
            context: Context description for logging

        Returns:
            Error response
        """
        logger.error(f"{context}: {str(exception)}", exc_info=True)
        return cls.error_response(
            error=str(exception), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ISSHCommandExecutor(ABC):
    """Interface for SSH command execution"""

    @abstractmethod
    async def execute_command(self, credentials: Any, command: str) -> Any:
        """Execute SSH command"""


class IServerManager(ABC):
    """Interface for server management operations"""

    @abstractmethod
    async def install_openvpn(self, server: Any) -> Dict[str, Any]:
        """Install OpenVPN on server"""

    @abstractmethod
    async def configure_openvpn(self, server: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure OpenVPN server"""

    @abstractmethod
    async def start_server(self, server: Any) -> bool:
        """Start OpenVPN server"""

    @abstractmethod
    async def stop_server(self, server: Any) -> bool:
        """Stop OpenVPN server"""

    @abstractmethod
    async def restart_server(self, server: Any) -> bool:
        """Restart OpenVPN server"""


class IClientManager(ABC):
    """Interface for client certificate management"""

    @abstractmethod
    async def create_client(self, server: Any, client_name: str) -> Any:
        """Create client certificate"""

    @abstractmethod
    async def revoke_client(self, client: Any) -> bool:
        """Revoke client certificate"""

    @abstractmethod
    async def get_client_config(self, client: Any) -> str:
        """Get client configuration file"""


class IMonitoringService(ABC):
    """Interface for monitoring operations"""

    @abstractmethod
    async def get_active_connections(self, server: Any) -> list:
        """Get active VPN connections"""

    @abstractmethod
    async def disconnect_client(self, connection: Any) -> bool:
        """Disconnect VPN client"""

    @abstractmethod
    async def get_server_stats(self, server: Any) -> Dict[str, Any]:
        """Get server statistics"""
