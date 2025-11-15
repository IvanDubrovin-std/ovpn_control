#!/usr/bin/env python3
"""
OpenVPN Management Agent

This agent runs on the remote OpenVPN server and executes commands locally.
It communicates with the main Django application via HTTP API.

Features:
- No SSH overhead for local commands
- Progress reporting
- Long-running operations support
- Systemd service integration
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging - write to /tmp if no permissions for /var/log
# IMPORTANT: Logs go to stderr and file, JSON output goes to stdout!
log_file = "/var/log/ovpn-agent.log"
try:
    # Try to create log file
    Path(log_file).touch()
    handlers = [logging.StreamHandler(sys.stderr), logging.FileHandler(log_file)]
except PermissionError:
    # Fall back to /tmp if no permissions
    log_file = "/tmp/ovpn-agent.log"
    handlers = [logging.StreamHandler(sys.stderr), logging.FileHandler(log_file)]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger("ovpn_agent")


class TaskStatus(Enum):
    """Task execution status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class TaskResult:
    """Result of task execution"""

    status: TaskStatus
    message: str
    output: str = ""
    error: str = ""
    progress: int = 0  # 0-100


class OpenVPNAgent:
    """OpenVPN Management Agent"""

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize agent

        Args:
            api_url: URL of main Django application API
            api_key: Authentication key for API
        """
        self.api_url = api_url
        self.api_key = api_key
        self.easy_rsa_dir = Path.home() / "easy-rsa"

    def execute_command(self, command: str, cwd: Optional[str] = None) -> tuple[str, str, int]:
        """
        Execute shell command locally

        Args:
            command: Command to execute
            cwd: Working directory

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        logger.info(f"Executing: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            exit_code = result.returncode

            if exit_code == 0:
                logger.info(f"Command succeeded: {stdout[:100]}")
            else:
                logger.error(f"Command failed (exit {exit_code}): {stderr[:200]}")

            return stdout, stderr, exit_code

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return "", "Command timeout", 124
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return "", str(e), 1

    def report_progress(self, task_id: str, progress: int, message: str) -> None:
        """
        Report progress to main application

        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            message: Progress message
        """
        if not self.api_url:
            logger.info(f"Progress [{progress}%]: {message}")
            return

        # TODO: Send progress to API endpoint
        logger.info(f"Progress [{progress}%]: {message}")

    def _get_pki_setup_steps(self) -> List[Dict]:
        """Get PKI initialization steps"""
        return [
            {"cmd": "rm -rf ~/easy-rsa 2>/dev/null || true", "desc": "Cleaning old easy-rsa", "progress": 5},
            {"cmd": "mkdir -p ~/easy-rsa", "desc": "Creating easy-rsa directory", "progress": 10},
            {"cmd": "cp -r /usr/share/easy-rsa/* ~/easy-rsa/ 2>/dev/null || true", "desc": "Copying easy-rsa files", "progress": 15},
            {"cmd": "echo 'set_var EASYRSA_ALGO \"ec\"' > ~/easy-rsa/vars", "desc": "Configuring PKI algorithm (EC)", "progress": 20},
            {"cmd": "echo 'set_var EASYRSA_DIGEST \"sha512\"' >> ~/easy-rsa/vars", "desc": "Configuring digest algorithm", "progress": 22},
            {"cmd": "cd ~/easy-rsa && ./easyrsa init-pki", "desc": "Initializing PKI", "progress": 25},
        ]

    def _get_certificate_generation_steps(self) -> List[Dict]:
        """Get certificate generation steps"""
        return [
            {"cmd": "cd ~/easy-rsa && ./easyrsa --batch gen-req server nopass", "desc": "Generating server certificate request", "progress": 30},
            {"cmd": "cd ~/easy-rsa && ./easyrsa --batch build-ca nopass", "desc": "Building Certificate Authority", "progress": 40},
            {"cmd": "cd ~/easy-rsa && ./easyrsa --batch sign-req server server", "desc": "Signing server certificate", "progress": 50},
            {"cmd": "cd ~/easy-rsa && ./easyrsa --batch gen-dh", "desc": "Generating DH parameters (this may take several minutes...)", "progress": 55},
            {"cmd": "cd ~/easy-rsa && openvpn --genkey secret ta.key", "desc": "Generating TLS-Crypt key", "progress": 70},
        ]

    def _get_certificate_installation_steps(self) -> List[Dict]:
        """Get certificate installation steps"""
        return [
            {"cmd": "sudo cp ~/easy-rsa/pki/private/server.key /etc/openvpn/", "desc": "Copying server key", "progress": 75},
            {"cmd": "sudo cp ~/easy-rsa/pki/issued/server.crt /etc/openvpn/", "desc": "Copying server certificate", "progress": 77},
            {"cmd": "sudo cp ~/easy-rsa/pki/ca.crt /etc/openvpn/", "desc": "Copying CA certificate", "progress": 79},
            {"cmd": "sudo cp ~/easy-rsa/pki/dh.pem /etc/openvpn/", "desc": "Copying DH parameters", "progress": 81},
            {"cmd": "sudo cp ~/easy-rsa/ta.key /etc/openvpn/", "desc": "Copying TLS-Crypt key", "progress": 83},
            {"cmd": "cd ~/easy-rsa && ./easyrsa gen-crl", "desc": "Generating Certificate Revocation List", "progress": 85},
            {"cmd": "sudo cp ~/easy-rsa/pki/crl.pem /etc/openvpn/", "desc": "Copying CRL", "progress": 87},
            {"cmd": "sudo chmod 644 /etc/openvpn/crl.pem", "desc": "Setting CRL permissions", "progress": 89},
        ]

    def _execute_configuration_steps(self, task_id: str, steps: List[Dict]) -> tuple[bool, List[str]]:
        """Execute configuration steps and return success status and outputs"""
        all_output = []
        for step in steps:
            self.report_progress(task_id, step["progress"], step["desc"])
            stdout, stderr, exit_code = self.execute_command(step["cmd"])
            all_output.append(f"=== {step['desc']} ===\n{stdout}\n{stderr}")
            if exit_code != 0 and "2>/dev/null" not in step["cmd"]:
                return False, all_output
        return True, all_output

    def _build_server_config(self, port: int, protocol: str, subnet: str, netmask: str, dns_servers: List[str]) -> str:
        """Build OpenVPN server configuration"""
        dns_config = "\n".join([f'push "dhcp-option DNS {dns}"' for dns in dns_servers])
        exit_notify = "" if protocol == "tcp" else "explicit-exit-notify 1\n"

        return f"""
port {port}
proto {protocol}
dev tun
ca ca.crt
cert server.crt
key server.key
dh dh.pem
crl-verify crl.pem
server {subnet} {netmask}
ifconfig-pool-persist /var/log/openvpn/ipp.txt
push "redirect-gateway def1 bypass-dhcp"
{dns_config}
keepalive 10 120
tls-crypt ta.key
cipher AES-256-GCM
auth SHA256
management localhost 7505
management-client-auth
user nobody
group nogroup
persist-key
persist-tun
status /var/log/openvpn/openvpn-status.log
log-append /var/log/openvpn/openvpn.log
verb 3
{exit_notify}mssfix 0
"""

    def install_openvpn(self, task_id: str) -> TaskResult:
        """
        Install OpenVPN and dependencies

        Args:
            task_id: Task identifier

        Returns:
            TaskResult
        """
        self.report_progress(task_id, 0, "Starting OpenVPN installation")

        commands = [
            ("sudo apt update -y", "Updating package list"),
            (
                "sudo DEBIAN_FRONTEND=noninteractive apt install -y openvpn easy-rsa netcat-openbsd",
                "Installing packages",
            ),
            ("sudo systemctl enable openvpn", "Enabling OpenVPN service"),
            ("sudo mkdir -p /etc/openvpn", "Creating directories"),
            ("sudo mkdir -p /var/log/openvpn", "Creating log directory"),
        ]

        all_output = []
        total_steps = len(commands)

        for idx, (cmd, desc) in enumerate(commands):
            progress = int((idx / total_steps) * 100)
            self.report_progress(task_id, progress, desc)

            stdout, stderr, exit_code = self.execute_command(cmd)
            all_output.append(f"=== {desc} ===\n{stdout}\n{stderr}")

            if exit_code != 0 and "openvpn" in cmd:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    message=f"Installation failed at: {desc}",
                    output="\n".join(all_output),
                    error=stderr,
                    progress=progress,
                )

        self.report_progress(task_id, 100, "OpenVPN installed successfully")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            message="OpenVPN installed successfully",
            output="\n".join(all_output),
            progress=100,
        )

    def configure_openvpn(
        self,
        task_id: str,
        port: int = 1194,
        protocol: str = "udp",
        subnet: str = "10.8.0.0",
        netmask: str = "255.255.255.0",
        dns_servers: Optional[List[str]] = None,
    ) -> TaskResult:
        """
        Configure OpenVPN server

        Args:
            task_id: Task identifier
            port: OpenVPN port
            protocol: Protocol (udp/tcp)
            subnet: VPN subnet
            netmask: VPN netmask
            dns_servers: List of DNS servers

        Returns:
            TaskResult
        """
        if dns_servers is None:
            dns_servers = ["8.8.8.8", "8.8.4.4"]

        self.report_progress(task_id, 0, "Starting OpenVPN configuration")

        # Execute PKI setup
        success, all_output = self._execute_configuration_steps(task_id, self._get_pki_setup_steps())
        if not success:
            return TaskResult(status=TaskStatus.FAILED, message="PKI setup failed", output="\n".join(all_output), progress=25)

        # Execute certificate generation
        success, cert_output = self._execute_configuration_steps(task_id, self._get_certificate_generation_steps())
        all_output.extend(cert_output)
        if not success:
            return TaskResult(status=TaskStatus.FAILED, message="Certificate generation failed", output="\n".join(all_output), progress=70)

        # Execute certificate installation
        success, install_output = self._execute_configuration_steps(task_id, self._get_certificate_installation_steps())
        all_output.extend(install_output)
        if not success:
            return TaskResult(status=TaskStatus.FAILED, message="Certificate installation failed", output="\n".join(all_output), progress=89)

        # Create server configuration
        self.report_progress(task_id, 90, "Creating server configuration")
        server_config = self._build_server_config(port, protocol, subnet, netmask, dns_servers)

        # Write config file
        config_path = "/tmp/server.conf"
        try:
            with open(config_path, "w") as f:
                f.write(server_config)
            stdout, stderr, exit_code = self.execute_command(f"sudo mv {config_path} /etc/openvpn/server.conf")
            if exit_code != 0:
                return TaskResult(status=TaskStatus.FAILED, message="Failed to write server configuration", output="\n".join(all_output), error=stderr, progress=90)
        except Exception as e:
            return TaskResult(status=TaskStatus.FAILED, message=f"Failed to create configuration: {e}", output="\n".join(all_output), error=str(e), progress=90)

        # Configure system
        self.report_progress(task_id, 95, "Configuring system settings")
        system_commands = [
            "sudo sysctl -w net.ipv4.ip_forward=1",
            "echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf",
            f"sudo ufw allow {port}/{protocol}",
            "sudo ufw allow OpenSSH",
        ]
        for cmd in system_commands:
            stdout, stderr, exit_code = self.execute_command(cmd)
            all_output.append(f"$ {cmd}\n{stdout}\n{stderr}")

        self.report_progress(task_id, 100, "OpenVPN configured successfully")
        return TaskResult(status=TaskStatus.SUCCESS, message="OpenVPN configured successfully", output="\n".join(all_output), progress=100)


    def reinstall_openvpn(self, task_id: str, config: Dict) -> TaskResult:
        """
        Complete reinstallation of OpenVPN

        Args:
            task_id: Task identifier
            config: Server configuration

        Returns:
            TaskResult
        """
        self.report_progress(task_id, 0, "Starting complete reinstallation")

        # Step 1: Stop service
        self.report_progress(task_id, 5, "Stopping OpenVPN service")
        self.execute_command(
            "sudo systemctl stop openvpn@server 2>/dev/null || sudo systemctl stop openvpn 2>/dev/null || true"
        )

        # Step 2: Disable autostart
        self.report_progress(task_id, 10, "Disabling autostart")
        self.execute_command(
            "sudo systemctl disable openvpn@server 2>/dev/null || sudo systemctl disable openvpn 2>/dev/null || true"
        )

        # Step 3: Cleanup
        self.report_progress(task_id, 15, "Removing old configurations")
        self.execute_command("sudo rm -rf /etc/openvpn/*")
        self.execute_command("rm -rf ~/easy-rsa")
        self.execute_command("sudo mkdir -p /etc/openvpn")
        self.execute_command("sudo mkdir -p /var/log/openvpn")

        # Step 4: Install
        self.report_progress(task_id, 20, "Reinstalling OpenVPN")
        install_result = self.install_openvpn(f"{task_id}_install")

        if install_result.status != TaskStatus.SUCCESS:
            return install_result

        # Step 5: Configure
        self.report_progress(task_id, 40, "Configuring OpenVPN")
        config_result = self.configure_openvpn(
            f"{task_id}_config",
            port=config.get("port", 1194),
            protocol=config.get("protocol", "udp"),
            subnet=config.get("subnet", "10.8.0.0"),
            netmask=config.get("netmask", "255.255.255.0"),
            dns_servers=config.get("dns_servers", ["8.8.8.8", "8.8.4.4"]),
        )

        if config_result.status != TaskStatus.SUCCESS:
            return config_result

        # Step 6: Start service
        self.report_progress(task_id, 95, "Starting OpenVPN service")
        stdout, stderr, exit_code = self.execute_command(
            "sudo systemctl start openvpn@server && sudo systemctl enable openvpn@server"
        )

        if exit_code != 0:
            return TaskResult(
                status=TaskStatus.FAILED,
                message="Failed to start OpenVPN service",
                error=stderr,
                progress=95,
            )

        # Step 7: Verify
        self.report_progress(task_id, 100, "Verifying service status")
        stdout, stderr, exit_code = self.execute_command("sudo systemctl is-active openvpn@server")

        is_running = "active" in stdout.lower()

        return TaskResult(
            status=TaskStatus.SUCCESS if is_running else TaskStatus.FAILED,
            message=(
                "OpenVPN reinstalled successfully"
                if is_running
                else "OpenVPN installed but not running"
            ),
            output=f"Installation: {install_result.output}\n\nConfiguration: {config_result.output}",
            progress=100,
        )

    def list_clients(self, task_id: str) -> TaskResult:
        """
        List all clients on the server

        Returns list of clients with their certificate information

        Args:
            task_id: Task identifier

        Returns:
            TaskResult with clients list in output
        """
        self.report_progress(task_id, 0, "Listing clients")

        # Check if easy-rsa exists
        if not self.easy_rsa_dir.exists():
            return TaskResult(
                status=TaskStatus.SUCCESS,
                message="No clients found (PKI not initialized)",
                output="[]",
                progress=100,
            )

        self.report_progress(task_id, 30, "Scanning issued certificates")

        # List issued certificates directory (most reliable method)
        issued_dir = self.easy_rsa_dir / "pki" / "issued"
        if not issued_dir.exists():
            return TaskResult(
                status=TaskStatus.SUCCESS,
                message="No clients found (PKI not initialized)",
                output="[]",
                progress=100,
            )

        clients = []
        for cert_file in issued_dir.glob("*.crt"):
            client_name = cert_file.stem

            # Skip server certificate
            if client_name == "server":
                continue

            self.report_progress(task_id, 50, f"Reading certificate: {client_name}")

            # Get certificate info
            cert_stdout, _, cert_exit = self.execute_command(
                f"openssl x509 -in {cert_file} -noout -subject -dates -serial"
            )

            # Parse certificate dates
            not_before = ""
            not_after = ""
            serial = ""
            for line in cert_stdout.split("\n"):
                if "notBefore" in line:
                    not_before = line.split("=", 1)[1].strip() if "=" in line else ""
                elif "notAfter" in line:
                    not_after = line.split("=", 1)[1].strip() if "=" in line else ""
                elif "serial" in line:
                    serial = line.split("=", 1)[1].strip() if "=" in line else ""

            clients.append({
                "name": client_name,
                "cert_file": str(cert_file),
                "not_before": not_before,
                "not_after": not_after,
                "serial": serial,
            })

        self.report_progress(task_id, 100, f"Found {len(clients)} clients")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            message=f"Found {len(clients)} clients",
            output=json.dumps(clients),
            progress=100,
        )

    def create_client(self, task_id: str, client_name: str, config: dict) -> TaskResult:
        """
        Create a new client certificate and configuration

        Args:
            task_id: Task identifier
            client_name: Name of the client to create
            config: Configuration dictionary with server settings

        Returns:
            TaskResult with client data in output
        """
        self.report_progress(task_id, 0, f"Creating client '{client_name}'")

        # Validate client name (alphanumeric, underscore, hyphen only)
        if not re.match(r"^[a-zA-Z0-9_-]+$", client_name):
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Invalid client name: {client_name}",
                output="",
                progress=100,
            )

        # Check if easy-rsa is initialized
        if not self.easy_rsa_dir.exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                message="PKI not initialized. Run 'reinstall' first.",
                output="",
                progress=100,
            )

        self.report_progress(task_id, 20, "Checking if client already exists")

        # Check if client already exists
        cert_file = self.easy_rsa_dir / "pki" / "issued" / f"{client_name}.crt"
        if cert_file.exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Client '{client_name}' already exists",
                output="",
                progress=100,
            )

        self.report_progress(task_id, 40, "Generating client certificate")

        # Generate client certificate (non-interactive)
        stdout, stderr, exit_code = self.execute_command(
            f"cd {self.easy_rsa_dir} && "
            f"./easyrsa --batch build-client-full {client_name} nopass"
        )

        if exit_code != 0:
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to generate client certificate: {stderr}",
                output=stderr,
                progress=100,
            )

        self.report_progress(task_id, 70, "Creating client configuration file")

        # Read necessary files for .ovpn config
        ca_file = self.easy_rsa_dir / "pki" / "ca.crt"
        client_cert_file = self.easy_rsa_dir / "pki" / "issued" / f"{client_name}.crt"
        client_key_file = self.easy_rsa_dir / "pki" / "private" / f"{client_name}.key"
        ta_key_file = self.easy_rsa_dir / "ta.key"  # Read from easy-rsa, not /etc/openvpn

        try:
            ca_cert = ca_file.read_text()
            client_cert = client_cert_file.read_text()
            client_key = client_key_file.read_text()
            ta_key = ta_key_file.read_text() if ta_key_file.exists() else None
        except Exception as e:
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to read certificate files: {str(e)}",
                output="",
                progress=100,
            )

        # Get server configuration
        server_host = config.get("server_host", "")
        server_port = config.get("port", 1194)
        protocol = config.get("protocol", "udp")
        cipher = config.get("cipher", "AES-256-GCM")
        auth = config.get("auth", "SHA256")

        # Build .ovpn configuration
        ovpn_config_parts = [
            "client",
            "dev tun",
            "proto " + protocol,
            f"remote {server_host} {server_port}",
            "resolv-retry infinite",
            "nobind",
            "persist-key",
            "persist-tun",
            f"cipher {cipher}",
            f"auth {auth}",
            "verb 3",
            "<ca>",
            ca_cert,
            "</ca>",
            "<cert>",
            client_cert,
            "</cert>",
            "<key>",
            client_key,
            "</key>",
        ]

        # Add tls-crypt key if available
        if ta_key:
            ovpn_config_parts.extend([
                "<tls-crypt>",
                ta_key,
                "</tls-crypt>",
            ])

        ovpn_config = "\n".join(ovpn_config_parts)

        # Save to client-configs directory
        client_configs_dir = Path.home() / "client-configs"
        client_configs_dir.mkdir(exist_ok=True)

        ovpn_file = client_configs_dir / f"{client_name}.ovpn"
        ovpn_file.write_text(ovpn_config)

        self.report_progress(task_id, 100, f"Client '{client_name}' created successfully")

        # Return client data
        client_data = {
            "name": client_name,
            "cert_file": str(client_cert_file),
            "key_file": str(client_key_file),
            "ovpn_file": str(ovpn_file),
            "created": True,
        }

        return TaskResult(
            status=TaskStatus.SUCCESS,
            message=f"Client '{client_name}' created successfully",
            output=json.dumps(client_data),
            progress=100,
        )

    def get_status(self, task_id: str) -> TaskResult:
        """
        Get OpenVPN server status and active connections

        Reads management interface to get real-time connection information

        Args:
            task_id: Task identifier

        Returns:
            TaskResult with status data in output
        """
        self.report_progress(task_id, 0, "Connecting to management interface")

        try:
            import socket

            # Connect to management interface
            management_host = "localhost"
            management_port = 7505

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((management_host, management_port))

            self.report_progress(task_id, 30, "Querying status")

            # Read welcome message
            sock.recv(4096)

            # Get status
            sock.sendall(b"status\n")
            status_data = b""
            while True:
                chunk = sock.recv(4096)
                status_data += chunk
                if b"END" in chunk:
                    break

            # Get version
            sock.sendall(b"version\n")
            version_data = sock.recv(4096)

            sock.close()

            self.report_progress(task_id, 70, "Parsing status data")

            # Parse status data
            status_text = status_data.decode("utf-8", errors="ignore")
            connections = []
            stats = {
                "connected_clients": 0,
                "total_bytes_in": 0,
                "total_bytes_out": 0,
            }

            in_client_list = False
            for line in status_text.split("\n"):
                line = line.strip()

                if line.startswith("CLIENT_LIST"):
                    in_client_list = True
                    parts = line.split(",")
                    if len(parts) >= 8:
                        connections.append({
                            "common_name": parts[1],
                            "real_address": parts[2],
                            "virtual_address": parts[3],
                            "bytes_received": int(parts[4]) if parts[4].isdigit() else 0,
                            "bytes_sent": int(parts[5]) if parts[5].isdigit() else 0,
                            "connected_since": parts[7] if len(parts) > 7 else "",
                        })
                        stats["total_bytes_in"] += int(parts[4]) if parts[4].isdigit() else 0
                        stats["total_bytes_out"] += int(parts[5]) if parts[5].isdigit() else 0

                elif line.startswith("ROUTING_TABLE"):
                    in_client_list = False

            stats["connected_clients"] = len(connections)

            self.report_progress(task_id, 100, f"Found {len(connections)} active connections")

            result_data = {
                "is_running": True,
                "connections": connections,
                "stats": stats,
                "version": version_data.decode("utf-8", errors="ignore").strip(),
            }

            return TaskResult(
                status=TaskStatus.SUCCESS,
                message=f"Status retrieved: {len(connections)} active connections",
                output=json.dumps(result_data),
                progress=100,
            )

        except Exception as e:
            # If management interface is not available, check if service is running
            stdout, stderr, exit_code = self.execute_command("systemctl is-active openvpn@server")

            is_running = "active" in stdout.lower()

            result_data = {
                "is_running": is_running,
                "connections": [],
                "stats": {"connected_clients": 0, "total_bytes_in": 0, "total_bytes_out": 0},
                "error": str(e) if not is_running else None,
            }

            return TaskResult(
                status=TaskStatus.SUCCESS if is_running else TaskStatus.FAILED,
                message=f"Service is {'running' if is_running else 'not running'}",
                output=json.dumps(result_data),
                progress=100,
            )

    def revoke_client(self, task_id: str, client_name: str) -> TaskResult:
        """
        Revoke a client certificate

        Args:
            task_id: Task identifier
            client_name: Name of the client to revoke

        Returns:
            TaskResult with revocation status
        """
        self.report_progress(task_id, 0, f"Revoking client '{client_name}'")

        # Check if easy-rsa is initialized
        if not self.easy_rsa_dir.exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                message="PKI not initialized",
                output="",
                progress=100,
            )

        # Check if client certificate exists
        cert_file = self.easy_rsa_dir / "pki" / "issued" / f"{client_name}.crt"
        if not cert_file.exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Client '{client_name}' not found",
                output="",
                progress=100,
            )

        self.report_progress(task_id, 40, "Revoking certificate")

        # Revoke certificate
        stdout, stderr, exit_code = self.execute_command(
            f"cd {self.easy_rsa_dir} && "
            f"./easyrsa --batch revoke {client_name}"
        )

        if exit_code != 0 and "already revoked" not in stderr.lower():
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to revoke certificate: {stderr}",
                output=stderr,
                progress=100,
            )

        self.report_progress(task_id, 70, "Updating CRL")

        # Update CRL (Certificate Revocation List)
        stdout, stderr, exit_code = self.execute_command(
            f"cd {self.easy_rsa_dir} && ./easyrsa gen-crl"
        )

        if exit_code != 0:
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to generate CRL: {stderr}",
                output=stderr,
                progress=100,
            )

        # Copy CRL to OpenVPN directory
        crl_file = self.easy_rsa_dir / "pki" / "crl.pem"
        openvpn_crl = Path("/etc/openvpn") / "crl.pem"

        stdout, stderr, exit_code = self.execute_command(
            f"sudo cp {crl_file} {openvpn_crl} && sudo chmod 644 {openvpn_crl}"
        )

        if exit_code != 0:
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to copy CRL: {stderr}",
                output=stderr,
                progress=100,
            )

        self.report_progress(task_id, 100, f"Client '{client_name}' revoked successfully")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            message=f"Client '{client_name}' revoked successfully",
            output=json.dumps({"revoked": True, "client_name": client_name}),
            progress=100,
        )

    def disconnect_client(self, task_id: str, client_name: str) -> TaskResult:
        """
        Disconnect a specific client from the server

        Args:
            task_id: Task identifier
            client_name: Common name of the client to disconnect

        Returns:
            TaskResult with disconnect status
        """
        self.report_progress(task_id, 0, f"Disconnecting client '{client_name}'")

        try:
            import socket

            # Connect to management interface
            management_host = "localhost"
            management_port = 7505

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((management_host, management_port))

            # Read welcome message
            sock.recv(4096)

            self.report_progress(task_id, 50, f"Sending kill command for '{client_name}'")

            # Send kill command
            sock.sendall(f"kill {client_name}\n".encode())
            response = sock.recv(4096).decode("utf-8", errors="ignore")

            sock.close()

            self.report_progress(task_id, 100, f"Client '{client_name}' disconnected")

            return TaskResult(
                status=TaskStatus.SUCCESS,
                message=f"Client '{client_name}' disconnected",
                output=json.dumps({"disconnected": True, "client_name": client_name, "response": response}),
                progress=100,
            )

        except Exception as e:
            return TaskResult(
                status=TaskStatus.FAILED,
                message=f"Failed to disconnect client: {str(e)}",
                output=json.dumps({"disconnected": False, "error": str(e)}),
                progress=100,
            )


def main():
    """Main entry point"""
    try:
        parser = argparse.ArgumentParser(description="OpenVPN Management Agent")
        parser.add_argument(
            "command",
            choices=["install", "configure", "reinstall", "list-clients", "create-client", "get-status", "revoke-client", "disconnect-client"],
            help="Command to execute"
        )
        parser.add_argument("--task-id", required=True, help="Task identifier")
        parser.add_argument("--config", help="Configuration JSON file")
        parser.add_argument("--api-url", help="Main application API URL")
        parser.add_argument("--api-key", help="API authentication key")
        parser.add_argument("--client-name", help="Client name (for create-client command)")

        args = parser.parse_args()

        # Initialize agent
        agent = OpenVPNAgent(api_url=args.api_url, api_key=args.api_key)

        # Load configuration if provided
        config = {}
        if args.config and Path(args.config).exists():
            with open(args.config) as f:
                config = json.load(f)

        # Execute command
        if args.command == "install":
            result = agent.install_openvpn(args.task_id)
        elif args.command == "configure":
            result = agent.configure_openvpn(
                args.task_id,
                port=config.get("port", 1194),
                protocol=config.get("protocol", "udp"),
                subnet=config.get("subnet", "10.8.0.0"),
                netmask=config.get("netmask", "255.255.255.0"),
                dns_servers=config.get("dns_servers"),
            )
        elif args.command == "reinstall":
            result = agent.reinstall_openvpn(args.task_id, config)
        elif args.command == "list-clients":
            result = agent.list_clients(args.task_id)
        elif args.command == "create-client":
            if not args.client_name:
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    message="--client-name is required for create-client command",
                    error="Missing client name",
                )
            else:
                result = agent.create_client(args.task_id, args.client_name, config)
        elif args.command == "get-status":
            result = agent.get_status(args.task_id)
        elif args.command == "revoke-client":
            if not args.client_name:
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    message="--client-name is required for revoke-client command",
                    error="Missing client name",
                )
            else:
                result = agent.revoke_client(args.task_id, args.client_name)
        elif args.command == "disconnect-client":
            if not args.client_name:
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    message="--client-name is required for disconnect-client command",
                    error="Missing client name",
                )
            else:
                result = agent.disconnect_client(args.task_id, args.client_name)
        else:
            result = TaskResult(
                status=TaskStatus.FAILED,
                message=f"Unknown command: {args.command}",
                error=f"Command '{args.command}' is not supported",
            )

        # Output result as JSON (serialize enum values)
        result_dict = asdict(result)
        result_dict["status"] = result.status.value  # Convert enum to its value
        print(json.dumps(result_dict))

        # Exit with appropriate code
        sys.exit(0 if result.status == TaskStatus.SUCCESS else 1)

    except Exception as e:
        # Catch any unhandled exception and return as JSON
        logger.error(f"Fatal error: {e}", exc_info=True)
        error_result = TaskResult(
            status=TaskStatus.FAILED,
            message=f"Fatal error: {str(e)}",
            error=str(e),
        )
        error_dict = asdict(error_result)
        error_dict["status"] = error_result.status.value  # Convert enum to its value
        print(json.dumps(error_dict))
        sys.exit(1)


if __name__ == "__main__":
    main()
