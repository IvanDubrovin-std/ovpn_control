"""
Agent configuration dataclass
Type-safe configuration for agent operations
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentConfig:
    """Configuration for agent operations"""

    # Server configuration
    port: int
    protocol: str
    subnet: str
    netmask: str
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "8.8.4.4"])
    use_stunnel: bool = False

    # Optional advanced settings
    cipher: str = "AES-256-GCM"
    auth: str = "SHA256"
    keepalive_ping: int = 10
    keepalive_timeout: int = 120
    max_clients: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "port": self.port,
            "protocol": self.protocol,
            "subnet": self.subnet,
            "netmask": self.netmask,
            "dns_servers": self.dns_servers,
            "use_stunnel": self.use_stunnel,
            "cipher": self.cipher,
            "auth": self.auth,
            "keepalive_ping": self.keepalive_ping,
            "keepalive_timeout": self.keepalive_timeout,
            "max_clients": self.max_clients,
        }

    @classmethod
    def from_server(cls, server) -> "AgentConfig":
        """Create config from OpenVPNServer model"""
        return cls(
            port=server.openvpn_port,
            protocol=server.openvpn_protocol,
            subnet=server.server_subnet,
            netmask=server.server_netmask,
            dns_servers=server.get_dns_servers_list(),
            use_stunnel=server.use_stunnel,
        )
