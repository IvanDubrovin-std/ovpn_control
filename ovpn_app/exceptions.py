"""
Custom Exceptions and Result Types

Provides domain-specific exceptions and Result pattern for better error handling.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, Optional, TypeVar

# Type variable for Result pattern
T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============================================================================
# Base Exceptions
# ============================================================================


class OpenVPNAppError(Exception):
    """Base exception for all application errors"""

    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR):
        super().__init__(message)
        self.message = message
        self.severity = severity


# ============================================================================
# SSH Exceptions
# ============================================================================


class SSHError(OpenVPNAppError):
    """Base exception for SSH-related errors"""


class SSHConnectionError(SSHError):
    """Raised when SSH connection fails"""

    def __init__(self, host: str, message: str = ""):
        self.host = host
        full_message = f"Failed to connect to {host}"
        if message:
            full_message += f": {message}"
        super().__init__(full_message, ErrorSeverity.ERROR)


class SSHAuthenticationError(SSHError):
    """Raised when SSH authentication fails"""

    def __init__(self, host: str, username: str):
        self.host = host
        self.username = username
        super().__init__(f"Authentication failed for {username}@{host}", ErrorSeverity.ERROR)


class SSHCommandError(SSHError):
    """Raised when SSH command execution fails"""

    def __init__(self, command: str, exit_code: int, stderr: str = ""):
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        message = f"Command '{command}' failed with exit code {exit_code}"
        if stderr:
            message += f": {stderr}"
        super().__init__(message, ErrorSeverity.ERROR)


class SSHTimeoutError(SSHError):
    """Raised when SSH operation times out"""

    def __init__(self, operation: str, timeout: int):
        self.operation = operation
        self.timeout = timeout
        super().__init__(
            f"SSH operation '{operation}' timed out after {timeout} seconds", ErrorSeverity.ERROR
        )


# ============================================================================
# OpenVPN Exceptions
# ============================================================================


class OpenVPNError(OpenVPNAppError):
    """Base exception for OpenVPN-related errors"""


class OpenVPNNotInstalledError(OpenVPNError):
    """Raised when OpenVPN is not installed on server"""

    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(
            f"OpenVPN is not installed on server '{server_name}'", ErrorSeverity.WARNING
        )


class OpenVPNInstallationError(OpenVPNError):
    """Raised when OpenVPN installation fails"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Failed to install OpenVPN on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class OpenVPNConfigurationError(OpenVPNError):
    """Raised when OpenVPN configuration fails"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Failed to configure OpenVPN on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class OpenVPNServiceError(OpenVPNError):
    """Raised when OpenVPN service operations fail"""

    def __init__(self, server_name: str, operation: str, reason: str = ""):
        self.server_name = server_name
        self.operation = operation
        message = f"Failed to {operation} OpenVPN on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


# ============================================================================
# Stunnel Exceptions
# ============================================================================


class StunnelError(OpenVPNAppError):
    """Base exception for Stunnel-related errors"""


class StunnelNotInstalledError(StunnelError):
    """Raised when Stunnel is not installed on server"""

    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(
            f"Stunnel is not installed on server '{server_name}'", ErrorSeverity.WARNING
        )


class StunnelInstallationError(StunnelError):
    """Raised when Stunnel installation fails"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Failed to install Stunnel on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class StunnelConfigurationError(StunnelError):
    """Raised when Stunnel configuration fails"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Failed to configure Stunnel on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class StunnelServiceError(StunnelError):
    """Raised when Stunnel service operations fail"""

    def __init__(self, server_name: str, operation: str, reason: str = ""):
        self.server_name = server_name
        self.operation = operation
        message = f"Failed to {operation} Stunnel on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class StunnelCertificateError(StunnelError):
    """Raised when Stunnel certificate operations fail"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Stunnel certificate error on server '{server_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


# ============================================================================
# Certificate Exceptions
# ============================================================================


class CertificateError(OpenVPNAppError):
    """Base exception for certificate-related errors"""


class CertificateGenerationError(CertificateError):
    """Raised when certificate generation fails"""

    def __init__(self, cert_name: str, reason: str = ""):
        self.cert_name = cert_name
        message = f"Failed to generate certificate '{cert_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class CertificateRevocationError(CertificateError):
    """Raised when certificate revocation fails"""

    def __init__(self, cert_name: str, reason: str = ""):
        self.cert_name = cert_name
        message = f"Failed to revoke certificate '{cert_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class CertificateNotFoundError(CertificateError):
    """Raised when certificate is not found"""

    def __init__(self, cert_name: str):
        self.cert_name = cert_name
        super().__init__(f"Certificate '{cert_name}' not found", ErrorSeverity.WARNING)


class CertificateExpiredError(CertificateError):
    """Raised when certificate has expired"""

    def __init__(self, cert_name: str, expired_at: str):
        self.cert_name = cert_name
        self.expired_at = expired_at
        super().__init__(
            f"Certificate '{cert_name}' expired at {expired_at}", ErrorSeverity.WARNING
        )


# ============================================================================
# Server Exceptions
# ============================================================================


class ServerError(OpenVPNAppError):
    """Base exception for server-related errors"""


class ServerNotFoundError(ServerError):
    """Raised when server is not found"""

    def __init__(self, server_id: int):
        self.server_id = server_id
        super().__init__(f"Server with ID {server_id} not found", ErrorSeverity.WARNING)


class ServerNotAccessibleError(ServerError):
    """Raised when server is not accessible"""

    def __init__(self, server_name: str, reason: str = ""):
        self.server_name = server_name
        message = f"Server '{server_name}' is not accessible"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


class ServerAlreadyRunningError(ServerError):
    """Raised when trying to start an already running server"""

    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(f"Server '{server_name}' is already running", ErrorSeverity.INFO)


# ============================================================================
# Client Exceptions
# ============================================================================


class ClientError(OpenVPNAppError):
    """Base exception for client-related errors"""


class ClientNotFoundError(ClientError):
    """Raised when client is not found"""

    def __init__(self, client_name: str):
        self.client_name = client_name
        super().__init__(f"Client '{client_name}' not found", ErrorSeverity.WARNING)


class ClientAlreadyExistsError(ClientError):
    """Raised when client already exists"""

    def __init__(self, client_name: str):
        self.client_name = client_name
        super().__init__(f"Client '{client_name}' already exists", ErrorSeverity.WARNING)


class ClientDisconnectionError(ClientError):
    """Raised when client disconnection fails"""

    def __init__(self, client_name: str, reason: str = ""):
        self.client_name = client_name
        message = f"Failed to disconnect client '{client_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, ErrorSeverity.ERROR)


# ============================================================================
# Result Pattern
# ============================================================================


@dataclass
class Result(Generic[T]):
    """
    Result type for operations that can fail

    Usage:
        result = some_operation()
        if result.is_success():
            data = result.unwrap()
        else:
            error = result.error
    """

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        """Create successful result"""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, error_code: Optional[str] = None) -> "Result[T]":
        """Create failed result"""
        return cls(success=False, error=error, error_code=error_code)

    @classmethod
    def from_exception(cls, exception: Exception) -> "Result[T]":
        """Create failed result from exception"""
        error_code = exception.__class__.__name__
        return cls(success=False, error=str(exception), error_code=error_code)

    def is_success(self) -> bool:
        """Check if result is successful"""
        return self.success

    def is_failure(self) -> bool:
        """Check if result is failed"""
        return not self.success

    def unwrap(self) -> T:
        """
        Unwrap successful result or raise exception

        Raises:
            ValueError: If result is not successful
        """
        if not self.success:
            raise ValueError(f"Cannot unwrap failed result: {self.error}")
        if self.data is None:
            raise ValueError("Cannot unwrap None data")
        return self.data

    def unwrap_or(self, default: T) -> T:
        """Unwrap successful result or return default"""
        return self.data if self.success and self.data is not None else default

    def map(self, func: Callable[[T], "Result"]) -> "Result":
        """Map function over successful result"""
        if self.is_failure():
            return self
        if self.data is None:
            return Result.fail("Cannot map over None data")
        try:
            return func(self.data)
        except Exception as e:
            return Result.from_exception(e)

    def and_then(self, func: Callable[[T], "Result"]) -> "Result":
        """Chain operations on result (alias for map)"""
        return self.map(func)


# Export all exceptions and types
__all__ = [
    # Base
    "OpenVPNAppError",
    "ErrorSeverity",
    # SSH
    "SSHError",
    "SSHConnectionError",
    "SSHAuthenticationError",
    "SSHCommandError",
    "SSHTimeoutError",
    # OpenVPN
    "OpenVPNError",
    "OpenVPNNotInstalledError",
    "OpenVPNInstallationError",
    "OpenVPNConfigurationError",
    "OpenVPNServiceError",
    # Stunnel
    "StunnelError",
    "StunnelNotInstalledError",
    "StunnelInstallationError",
    "StunnelConfigurationError",
    "StunnelServiceError",
    "StunnelCertificateError",
    # Certificates
    "CertificateError",
    "CertificateGenerationError",
    "CertificateRevocationError",
    "CertificateNotFoundError",
    "CertificateExpiredError",
    # Server
    "ServerError",
    "ServerNotFoundError",
    "ServerNotAccessibleError",
    "ServerAlreadyRunningError",
    # Client
    "ClientError",
    "ClientNotFoundError",
    "ClientAlreadyExistsError",
    "ClientDisconnectionError",
    # Result pattern
    "Result",
]
