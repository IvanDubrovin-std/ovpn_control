"""
WebSocket consumers for real-time functionality

Implements clean architecture patterns with proper separation of concerns.
Uses dependency injection and follows SOLID principles.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import OpenVPNServer
from .ssh_service import (
    AsyncSSHConnection,
    ISSHService,
    SSHCommandError,
    SSHConnectionError,
    SSHCredentialsFactory,
    SSHServiceContainer,
)

logger = logging.getLogger(__name__)


class IWebSocketMessageHandler(ABC):
    """Interface for WebSocket message handlers"""

    @abstractmethod
    async def handle_message(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming WebSocket message"""


class IWebSocketAuthenticator(ABC):
    """Interface for WebSocket authentication"""

    @abstractmethod
    async def authenticate(self, scope: Dict[str, Any]) -> bool:
        """Authenticate WebSocket connection"""


class WebSocketAuthenticator(IWebSocketAuthenticator):
    """Default WebSocket authenticator"""

    async def authenticate(self, scope: Dict[str, Any]) -> bool:
        """Check if user is authenticated"""
        user = scope.get("user")
        if user is None:
            return False
        return not isinstance(user, AnonymousUser)


class SSHTerminalHandler(IWebSocketMessageHandler):
    """Handles SSH terminal WebSocket messages"""

    def __init__(self, server_id: int, ssh_service: Optional[ISSHService] = None):
        self._server_id = server_id
        self._ssh_service = ssh_service or SSHServiceContainer.get_ssh_service()
        self._server: Optional[OpenVPNServer] = None
        self._connection: Optional[AsyncSSHConnection] = None

    async def handle_message(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SSH terminal messages"""
        try:
            if message_type == "connect":
                return await self._handle_connect()
            elif message_type == "command":
                return await self._handle_command(data.get("command", ""))
            elif message_type == "disconnect":
                return await self._handle_disconnect()
            else:
                return {"type": "error", "message": f"Unknown message type: {message_type}"}

        except Exception as e:
            logger.error(f"SSH terminal handler error: {e}")
            return {"type": "error", "message": str(e)}

    async def _handle_connect(self) -> Dict[str, Any]:
        """Handle SSH connection request"""
        try:
            # Get server from database
            self._server = await self._get_server()
            if not self._server:
                return {"type": "error", "message": "Server not found"}

            # Create SSH credentials
            credentials = SSHCredentialsFactory.from_server(self._server)

            # Establish SSH connection
            connection = await self._ssh_service.create_connection(credentials)
            self._connection = connection  # type: ignore[assignment]

            # Send welcome messages
            welcome_output = f"""Connected to {self._server.host}
OpenVPN Management Terminal
Type 'help' for available commands.

{self._server.ssh_username}@{self._server.host}:~$ """

            return {
                "type": "connected",
                "message": "SSH connection established",
                "output": welcome_output,
            }

        except SSHConnectionError as e:
            logger.error(f"SSH connection failed: {e}")
            return {"type": "error", "message": f"SSH connection failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return {"type": "error", "message": f"Connection error: {str(e)}"}

    async def _handle_command(self, command: str) -> Dict[str, Any]:
        """Handle SSH command execution"""
        if not self._connection:
            return {"type": "error", "message": "SSH not connected"}

        if not command.strip():
            return {"type": "output", "data": ""}

        try:
            # Execute command via SSH
            result = await self._connection.execute_command(command)

            # Format output
            output = result.output
            if not output.endswith("\n"):
                output += "\n"

            # Add prompt for next command
            if self._server is None:
                prompt = "~$ "
            else:
                prompt = f"{self._server.ssh_username}@{self._server.host}:~$ "

            return {
                "type": "output",
                "data": output + prompt,
                "success": result.success,
                "exit_code": result.exit_code,
            }

        except SSHCommandError as e:
            logger.error(f"SSH command error: {e}")
            prompt = "~$ "
            if self._server is not None:
                prompt = f"{self._server.ssh_username}@{self._server.host}:~$ "
            return {
                "type": "output",
                "data": f"Error: {str(e)}\n{prompt}",
                "success": False,
            }

    async def _handle_disconnect(self) -> Dict[str, Any]:
        """Handle SSH disconnection"""
        if self._connection:
            try:
                await self._connection.close()
                self._connection = None
                return {"type": "disconnected", "message": "SSH connection closed"}
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
                return {"type": "error", "message": f"Disconnect error: {str(e)}"}

        return {"type": "disconnected", "message": "Already disconnected"}

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self._connection:
            try:
                await self._connection.close()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    @database_sync_to_async
    def _get_server(self) -> Optional[OpenVPNServer]:
        """Get server from database"""
        try:
            server: OpenVPNServer = OpenVPNServer.objects.get(id=self._server_id)
            return server
        except OpenVPNServer.DoesNotExist:
            return None


class BaseWebSocketConsumer(AsyncWebsocketConsumer):
    """Base WebSocket consumer with common functionality"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._authenticator: IWebSocketAuthenticator = WebSocketAuthenticator()
        self._message_handler: Optional[IWebSocketMessageHandler] = None

    async def connect(self):
        """Handle WebSocket connection"""
        # Authenticate user
        is_authenticated = await self._authenticator.authenticate(self.scope)
        if not is_authenticated:
            await self.close(code=4001)  # Unauthorized
            return

        # Initialize message handler
        self._message_handler = await self._create_message_handler()
        if not self._message_handler:
            await self.close(code=4000)  # Bad Request
            return

        await self.accept()
        logger.info(f"WebSocket connection accepted for {self.scope['user']}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self._message_handler and hasattr(self._message_handler, "cleanup"):
            await self._message_handler.cleanup()

        logger.info(f"WebSocket connection closed with code: {close_code}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if not message_type:
                await self._send_error("Message type is required")
                return

            if not self._message_handler:
                await self._send_error("Message handler not initialized")
                return

            # Handle message
            response = await self._message_handler.handle_message(message_type, data)
            await self.send(text_data=json.dumps(response))

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"WebSocket message handling error: {e}")
            await self._send_error(f"Internal error: {str(e)}")

    async def _send_error(self, message: str) -> None:
        """Send error message to client"""
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    @abstractmethod
    async def _create_message_handler(self) -> Optional[IWebSocketMessageHandler]:
        """Create message handler for this consumer"""


class SSHConsumer(BaseWebSocketConsumer):
    """WebSocket consumer for SSH terminal"""

    async def _create_message_handler(self) -> Optional[IWebSocketMessageHandler]:
        """Create SSH terminal message handler"""
        server_id = self.scope["url_route"]["kwargs"].get("server_id")

        if not server_id:
            logger.error("Server ID not provided in WebSocket URL")
            return None

        try:
            server_id = int(server_id)
            return SSHTerminalHandler(server_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid server ID: {server_id}")
            return None


class MonitoringConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time monitoring"""

    async def connect(self):
        """Accept WebSocket connection for monitoring"""
        if isinstance(self.scope["user"], AnonymousUser):
            await self.close(code=4001)
            return

        # Join monitoring group
        await self.channel_layer.group_add("monitoring", self.channel_name)
        await self.accept()
        logger.info("Monitoring WebSocket connection established")

    async def disconnect(self, close_code):
        """Leave monitoring group"""
        await self.channel_layer.group_discard("monitoring", self.channel_name)
        logger.info(f"Monitoring WebSocket disconnected: {close_code}")

    async def receive(self, text_data):
        """Handle monitoring requests"""
        try:
            json.loads(text_data)
            # Handle monitoring-specific messages
            await self.send(
                text_data=json.dumps(
                    {"type": "monitoring_response", "message": "Monitoring data request received"}
                )
            )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "message": "Invalid JSON format"})
            )

    async def monitoring_update(self, event):
        """Send monitoring update to WebSocket"""
        await self.send(text_data=json.dumps({"type": "monitoring_update", "data": event["data"]}))
