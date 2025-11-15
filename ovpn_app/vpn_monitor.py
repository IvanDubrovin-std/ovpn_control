"""
VPN Connection Monitor Service
Monitors OpenVPN server status and updates connection records
"""

import logging
from typing import Dict, List, Optional


from .models import ClientCertificate, OpenVPNServer, VPNConnection
from .ssh_service import SSHCredentials, SSHService

logger = logging.getLogger(__name__)


class VPNMonitor:
    """Monitor VPN connections on OpenVPN servers"""

    def __init__(self, server: OpenVPNServer):
        self.server = server
        self.ssh_service = SSHService()
        self.credentials = SSHCredentials(
            hostname=server.host,
            username=server.ssh_username,
            port=server.ssh_port,
            private_key_content=server.ssh_private_key,
        )

    async def get_active_connections(self) -> List[Dict]:
        """
        Get active connections from OpenVPN status
        Returns list of connection dictionaries
        """
        try:
            # Create SSH connection
            conn = await self.ssh_service.create_connection(self.credentials)

            # Read OpenVPN status file
            status_cmd = "sudo cat /var/log/openvpn/openvpn-status.log 2>/dev/null || sudo openvpn-status 2>/dev/null"
            result = await conn.execute_command(status_cmd)

            if result.exit_code != 0:
                logger.warning(f"Could not read status for {self.server.name}: {result.stderr}")
                return []

            return self._parse_status(result.stdout)

        except Exception as e:
            logger.error(f"Error getting connections for {self.server.name}: {e}")
            return []

    async def check_server_status(self) -> str:
        """
        Check if OpenVPN service is running on the server
        Returns: 'running', 'stopped', or 'error'
        """
        try:
            # Create SSH connection
            conn = await self.ssh_service.create_connection(self.credentials)

            # Check OpenVPN service status
            status_cmd = "sudo systemctl is-active openvpn@server 2>/dev/null || sudo systemctl is-active openvpn 2>/dev/null"
            result = await conn.execute_command(status_cmd)

            status_output = result.stdout.strip()

            if result.exit_code == 0 and status_output == "active":
                return "running"
            elif status_output in ("inactive", "failed", "unknown"):
                return "stopped"
            else:
                # Try alternative check via process
                ps_cmd = "ps aux | grep -v grep | grep openvpn"
                ps_result = await conn.execute_command(ps_cmd)

                if ps_result.exit_code == 0 and ps_result.stdout.strip():
                    return "running"
                else:
                    return "stopped"

        except Exception as e:
            logger.error(f"Error checking status for {self.server.name}: {e}")
            return "error"

    async def update_server_status(self):
        """Update server status in database"""
        try:
            status = await self.check_server_status()

            # Update in database
            from asgiref.sync import sync_to_async

            @sync_to_async
            def update_status():
                self.server.status = status
                self.server.save(update_fields=["status"])

            await update_status()
            logger.info(f"Server {self.server.name} status updated to: {status}")

        except Exception as e:
            logger.error(f"Error updating server status: {e}")

    async def get_server_uptime(self) -> Optional[str]:
        """Get server uptime"""
        try:
            conn = await self.ssh_service.create_connection(self.credentials)

            # Get uptime
            result = await conn.execute_command("uptime -p 2>/dev/null || uptime")

            if result.exit_code == 0:
                uptime_str = result.stdout.strip()
                # Remove "up " prefix if present
                if uptime_str.startswith("up "):
                    uptime_str = uptime_str[3:]
                return uptime_str

            return None
        except Exception as e:
            logger.error(f"Error getting uptime: {e}")
            return None

    async def get_system_load(self) -> Optional[str]:
        """Get system load average"""
        try:
            conn = await self.ssh_service.create_connection(self.credentials)

            # Get load average from /proc/loadavg
            result = await conn.execute_command("cat /proc/loadavg 2>/dev/null")

            if result.exit_code == 0:
                # Format: 0.52 0.58 0.59 1/820 29386
                # We take first 3 numbers (1min, 5min, 15min averages)
                parts = result.stdout.strip().split()
                if len(parts) >= 3:
                    return f"{parts[0]} {parts[1]} {parts[2]}"

            return None
        except Exception as e:
            logger.error(f"Error getting system load: {e}")
            return None

    async def get_openvpn_uptime(self) -> Optional[str]:
        """Get OpenVPN service uptime"""
        try:
            conn = await self.ssh_service.create_connection(self.credentials)

            # Get service start time
            result = await conn.execute_command(
                "systemctl show openvpn@server -p ActiveEnterTimestamp --value 2>/dev/null || "
                "systemctl show openvpn -p ActiveEnterTimestamp --value 2>/dev/null"
            )

            if result.exit_code == 0 and result.stdout.strip():
                from datetime import datetime
                from datetime import timezone as dt_timezone

                from dateutil import parser

                try:
                    # Parse timestamp
                    start_time = parser.parse(result.stdout.strip())
                    now = datetime.now(dt_timezone.utc)

                    # Calculate duration
                    duration = now - start_time

                    days = duration.days
                    hours = duration.seconds // 3600
                    minutes = (duration.seconds % 3600) // 60

                    if days > 0:
                        return f"{days}d {hours}h"
                    elif hours > 0:
                        return f"{hours}h {minutes}m"
                    else:
                        return f"{minutes}m"
                except Exception:
                    pass

            return None
        except Exception as e:
            logger.error(f"Error getting OpenVPN uptime: {e}")
            return None

    def _parse_status(self, status_output: str) -> List[Dict]:
        """
        Parse OpenVPN status output
        Format:
        Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
        client1,192.168.1.100:12345,1234567,7654321,Mon Nov 11 10:30:45 2024
        """
        connections = []
        lines = status_output.strip().split("\n")

        # Find the CLIENT LIST section
        in_client_section = False

        for line in lines:
            line = line.strip()

            if "CLIENT LIST" in line or "Common Name" in line:
                in_client_section = True
                continue

            if "ROUTING TABLE" in line or line.startswith("GLOBAL"):
                in_client_section = False
                break

            if not in_client_section or not line or line.startswith("Updated,"):
                continue

            # Parse line: CommonName,RealAddress,BytesReceived,BytesSent,ConnectedSince
            parts = line.split(",")
            if len(parts) >= 5:
                try:
                    connections.append(
                        {
                            "client_name": parts[0].strip(),
                            "real_address": parts[1].strip().split(":")[0],  # Remove port
                            "bytes_received": int(parts[2].strip()),
                            "bytes_sent": int(parts[3].strip()),
                            "connected_since": parts[4].strip(),
                        }
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse line: {line} - {e}")
                    continue

        return connections

    async def update_connections(self):  # noqa: C901
        """
        Update VPNConnection records based on current server status
        Also updates server status (running/stopped)
        """
        from asgiref.sync import sync_to_async

        logger.info(f"Updating connections for {self.server.name}")

        # First, update server status
        await self.update_server_status()

        # Get current active connections from server
        active_connections = await self.get_active_connections()

        if not active_connections:
            logger.info(f"No active connections found for {self.server.name}")
            # Mark all existing connections as disconnected
            await sync_to_async(VPNConnection.objects.filter(client__server=self.server).delete)()
            return

        # Get all clients for this server
        @sync_to_async
        def get_clients():
            return {
                client.name: client
                for client in ClientCertificate.objects.filter(server=self.server)
            }

        clients = await get_clients()
        active_client_names = set()

        # Update or create connections
        for conn_data in active_connections:
            client_name = conn_data["client_name"]
            active_client_names.add(client_name)

            # Find client certificate
            client = clients.get(client_name)
            if not client:
                logger.warning(f"Client '{client_name}' not found in database")
                continue

            # Get virtual IP from routing table
            virtual_ip = await self._get_virtual_ip(client_name)
            if not virtual_ip:
                virtual_ip = "10.8.0.0"  # Default fallback

            # Parse connected_since timestamp
            from datetime import timezone as dt_timezone

            from dateutil import parser as date_parser

            connected_at = None
            try:
                # Parse OpenVPN timestamp: "2025-11-11 23:05:27"
                # OpenVPN uses server's local time
                naive_dt = date_parser.parse(conn_data["connected_since"])

                # Make timezone aware (assume UTC)
                # If your server uses different timezone, adjust accordingly
                if naive_dt.tzinfo is None:
                    connected_at = naive_dt.replace(tzinfo=dt_timezone.utc)
                else:
                    connected_at = naive_dt

                logger.info(
                    f"Parsed connected_at: {connected_at} from '{conn_data['connected_since']}'"
                )
            except Exception as e:
                logger.warning(
                    f"Could not parse connected_since: {conn_data['connected_since']} - {e}"
                )

            # Update or create connection
            @sync_to_async
            def update_or_create_conn():
                # Check if connection exists
                existing = VPNConnection.objects.filter(client=client).first()

                if existing:
                    # Update existing connection (preserve connected_at)
                    existing.client_ip = conn_data["real_address"]
                    existing.virtual_ip = virtual_ip
                    existing.bytes_received = conn_data["bytes_received"]
                    existing.bytes_sent = conn_data["bytes_sent"]
                    existing.save()
                    return existing, False
                else:
                    # Create new connection with parsed timestamp
                    defaults = {
                        "client_ip": conn_data["real_address"],
                        "virtual_ip": virtual_ip,
                        "bytes_received": conn_data["bytes_received"],
                        "bytes_sent": conn_data["bytes_sent"],
                    }
                    if connected_at:
                        defaults["connected_at"] = connected_at

                    conn = VPNConnection.objects.create(client=client, **defaults)
                    return conn, True

            connection, created = await update_or_create_conn()

            action = "Created" if created else "Updated"
            logger.info(f"{action} connection for {client_name}")

        # Remove connections that are no longer active
        @sync_to_async
        def delete_inactive():
            return (
                VPNConnection.objects.filter(client__server=self.server)
                .exclude(client__name__in=active_client_names)
                .delete()
            )

        await delete_inactive()

        logger.info(f"Finished updating connections for {self.server.name}")

    async def _get_virtual_ip(self, client_name: str) -> Optional[str]:
        """Get virtual IP for client from routing table"""
        try:
            # Create SSH connection
            conn = await self.ssh_service.create_connection(self.credentials)

            # Try to get IP from status routing table
            status_cmd = "sudo cat /var/log/openvpn/openvpn-status.log 2>/dev/null"
            result = await conn.execute_command(status_cmd)

            if result.exit_code == 0:
                # Parse routing table section
                # Format: Virtual Address,Common Name,Real Address,Last Ref
                # Example: 10.8.0.6,myclientPC,195.7.13.139:1584,2025-11-11 23:18:11
                lines = result.stdout.split("\n")
                in_routing = False

                for line in lines:
                    if "ROUTING TABLE" in line:
                        in_routing = True
                        continue

                    if "GLOBAL STATS" in line:
                        in_routing = False
                        break

                    if in_routing and "," in line:
                        parts = line.split(",")
                        # parts[0] = Virtual Address, parts[1] = Common Name
                        if len(parts) >= 2 and parts[1].strip() == client_name:
                            virtual_ip = parts[0].strip()
                            logger.info(f"Found virtual IP {virtual_ip} for client {client_name}")
                            return virtual_ip

            return None

        except Exception as e:
            logger.error(f"Error getting virtual IP: {e}")
            return None


async def monitor_all_servers():
    """Monitor all running OpenVPN servers"""
    from asgiref.sync import sync_to_async

    # Get servers synchronously
    @sync_to_async
    def get_running_servers():
        return list(OpenVPNServer.objects.filter(status="running"))

    servers = await get_running_servers()

    for server in servers:
        try:
            monitor = VPNMonitor(server)
            await monitor.update_connections()
        except Exception as e:
            logger.error(f"Error monitoring {server.name}: {e}")


def sync_monitor_all_servers():
    """Synchronous wrapper for monitor_all_servers"""
    import asyncio

    # Use asyncio.run() which creates a new event loop
    asyncio.run(monitor_all_servers())
