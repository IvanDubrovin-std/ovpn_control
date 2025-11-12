
"""
Simplified OpenVPN Service

Clean implementation for OpenVPN installation and management.
"""

import logging
from typing import List
from dataclasses import dataclass

from .ssh_service import SSHService, SSHCredentials, CommandResult


logger = logging.getLogger(__name__)

@dataclass
class InstallationResult:
    """Result of OpenVPN installation"""
    success: bool
    message: str
    output: str
    error: str = ""
    
    # For compatibility with CommandResult interface
    @property
    def stderr(self) -> str:
        return self.error
    
    @property 
    def stdout(self) -> str:
        return self.output


class OpenVPNInstaller:
    """Simple OpenVPN installer"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    def get_install_commands(self) -> List[str]:
        """Get commands for OpenVPN installation"""
        return [
            "sudo apt update -y",
            "sudo DEBIAN_FRONTEND=noninteractive apt install -y openvpn easy-rsa",
            "sudo systemctl enable openvpn",
            "sudo mkdir -p /etc/openvpn",
            "sudo mkdir -p /var/log/openvpn",
            "echo 'OpenVPN installation completed'"
        ]
    
    async def check_sudo_access(self, credentials: SSHCredentials) -> bool:
        """Check if user has sudo access"""
        try:
            # Try non-interactive sudo first
            result = await self.ssh_service.execute_command(credentials, "sudo -n true")
            return result.success
        except Exception as e:
            logger.warning(f"Error checking sudo access: {e}")
            return False
    
    async def check_openvpn_installed(self, credentials: SSHCredentials) -> bool:
        """Check if OpenVPN is installed"""
        result = await self.ssh_service.execute_command(credentials, "dpkg -l | grep openvpn")
        return result.success and "openvpn" in result.stdout.lower()
    
    async def install_openvpn(self, credentials: SSHCredentials) -> InstallationResult:
        """Install OpenVPN on remote server"""
        try:
            logger.info("Starting OpenVPN installation")
            logger.info(f"Credentials: hostname={credentials.hostname}, port={credentials.port}, username={credentials.username}")
            
            # Check if already installed
            logger.info("Checking if OpenVPN is already installed")
            if await self.check_openvpn_installed(credentials):
                logger.info("OpenVPN already installed")
                return InstallationResult(
                    success=True,
                    message="OpenVPN уже установлен на сервере",
                    output="OpenVPN is already installed"
                )
            
            # Check sudo access and warn if needed
            logger.info("Checking sudo access")
            has_sudo = await self.check_sudo_access(credentials)
            
            if not has_sudo:
                logger.warning("Sudo access verification failed - user cannot use sudo without password")
                return InstallationResult(
                    success=False,
                    message="Пользователь не может использовать sudo без пароля. Пожалуйста, настройте NOPASSWD для sudo или используйте пользователя root.",
                    output="Для установки OpenVPN требуется:\n1. Добавить пользователя в sudoers с NOPASSWD\n2. Или использовать пользователя root\n\nКоманда для настройки:\necho 'username ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/username",
                    error="Sudo access denied - passwordless sudo required"
                )
            
            logger.info("Sudo access OK")
            
            # Install OpenVPN
            commands = self.get_install_commands()
            all_output = []
            
            for command in commands:
                logger.info(f"Executing: {command}")
                result = await self.ssh_service.execute_command(credentials, command)
                
                all_output.append(f"$ {command}")
                if result.stdout:
                    all_output.append(result.stdout)
                if result.stderr:
                    all_output.append(f"STDERR: {result.stderr}")
                
                # For sudo commands, don't immediately fail on non-zero exit codes
                # Some sudo commands may prompt for password but still work
                if not result.success and not command.startswith('sudo'):
                    logger.error(f"Command failed: {command}")
                    return InstallationResult(
                        success=False,
                        message=f"Ошибка при выполнении команды: {command}",
                        output="\n".join(all_output),
                        error=result.stderr
                    )
                elif not result.success and command.startswith('sudo'):
                    # Log sudo issues but continue
                    logger.warning(f"Sudo command may have required password: {command}")
                    all_output.append(f"Note: sudo command may have required password prompt")
            
            # Verify installation
            if not await self.check_openvpn_installed(credentials):
                logger.error("Installation verification failed")
                return InstallationResult(
                    success=False,
                    message="Установка завершена, но проверка не прошла. Возможно, требуется ручной ввод пароля sudo.",
                    output="\n".join(all_output),
                    error="Installation verification failed - may need manual sudo password"
                )
            
            logger.info("OpenVPN installation completed successfully")
            return InstallationResult(
                success=True,
                message="OpenVPN успешно установлен и настроен",
                output="\n".join(all_output)
            )
            
        except Exception as e:
            logger.error(f"Exception in install_openvpn: {e}")
            return InstallationResult(
                success=False,
                message=f"Ошибка установки: {str(e)}",
                output="",
                error=str(e)
            )


class OpenVPNConfigurator:
    """OpenVPN configuration setup"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    def get_setup_commands(self, server_config: dict, username: str = "root") -> List[str]:
        """Get commands for OpenVPN setup - following DigitalOcean guide"""
        port = server_config.get('port', 1194)
        protocol = server_config.get('protocol', 'udp')
        subnet = server_config.get('subnet', '10.8.0.0')
        netmask = server_config.get('netmask', '255.255.255.0')
        dns_servers = server_config.get('dns_servers', ['8.8.8.8', '8.8.4.4'])
        
        # Build full path to user's home directory
        # Use current directory instead of absolute path to avoid permission issues
        easy_rsa_path = "easy-rsa"
        
        # Build DNS push commands
        dns_push_lines = []
        for dns in dns_servers:
            dns_push_lines.append(f"push \"dhcp-option DNS {dns}\"")
        dns_config = "\n".join(dns_push_lines)
        
        return [
            # Step 1: Clean and recreate easy-rsa directory (without sudo!)
            "rm -rf ~/easy-rsa 2>/dev/null || true",
            "mkdir -p ~/easy-rsa",
            
            # Step 2: Copy easyrsa files from package
            "cp -r /usr/share/easy-rsa/* ~/easy-rsa/ 2>/dev/null || true",
            
            # Step 3: Configure vars file (use full path)
            "echo 'set_var EASYRSA_ALGO \"ec\"' > ~/easy-rsa/vars",
            "echo 'set_var EASYRSA_DIGEST \"sha512\"' >> ~/easy-rsa/vars",
            
            # Step 4: Initialize PKI
            "cd ~/easy-rsa && ./easyrsa init-pki",
            
            # Step 5: Generate server certificate request
            "cd ~/easy-rsa && ./easyrsa --batch gen-req server nopass",
            
            # Step 6: Build CA and sign server certificate
            "cd ~/easy-rsa && ./easyrsa --batch build-ca nopass",
            "cd ~/easy-rsa && ./easyrsa --batch sign-req server server",
            
            # Step 7: Generate DH parameters
            "cd ~/easy-rsa && ./easyrsa --batch gen-dh",
            
            # Step 8: Generate ta.key for TLS auth
            "cd ~/easy-rsa && openvpn --genkey secret ta.key",
            
            # Step 9: Create /etc/openvpn directory
            "sudo mkdir -p /etc/openvpn",
            
            # Step 10: Copy files to /etc/openvpn/
            "sudo cp ~/easy-rsa/pki/private/server.key /etc/openvpn/",
            "sudo cp ~/easy-rsa/pki/issued/server.crt /etc/openvpn/",
            "sudo cp ~/easy-rsa/pki/ca.crt /etc/openvpn/",
            "sudo cp ~/easy-rsa/pki/dh.pem /etc/openvpn/",
            "sudo cp ~/easy-rsa/ta.key /etc/openvpn/",
            
            # Step 11: Create server config in /etc/openvpn/server.conf
            f"sudo tee /etc/openvpn/server.conf > /dev/null << 'EOF'\n"
            f"port {port}\n"
            f"proto {protocol}\n"
            f"dev tun\n"
            f"ca ca.crt\n"
            f"cert server.crt\n"
            f"key server.key\n"
            f"dh dh.pem\n"
            f"server {subnet} {netmask}\n"
            f"ifconfig-pool-persist /var/log/openvpn/ipp.txt\n"
            f"push \"redirect-gateway def1 bypass-dhcp\"\n"
            f"{dns_config}\n"
            f"keepalive 10 120\n"
            f"tls-crypt ta.key\n"
            f"cipher AES-256-GCM\n"
            f"auth SHA256\n"
            f"user nobody\n"
            f"group nogroup\n"
            f"persist-key\n"
            f"persist-tun\n"
            f"status /var/log/openvpn/openvpn-status.log\n"
            f"log-append /var/log/openvpn/openvpn.log\n"
            f"verb 3\n"
            f"explicit-exit-notify 1\n"
            f"mssfix 0\n"
            f"EOF",
            
            # Step 12: Create log directory
            "sudo mkdir -p /var/log/openvpn",
            
            # Step 13: Enable IP forwarding
            "sudo sysctl -w net.ipv4.ip_forward=1",
            "echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf",
            
            # Step 14: Configure firewall (basic)
            f"sudo ufw allow {port}/{protocol}",
            "sudo ufw allow OpenSSH",
        ]
    
    async def configure_openvpn(self, credentials: SSHCredentials, server_config: dict) -> InstallationResult:
        """Configure OpenVPN server"""
        try:
            logger.info("Starting OpenVPN configuration")
            
            commands = self.get_setup_commands(server_config, credentials.username)
            all_output = []
            
            for command in commands:
                logger.info(f"Executing: {command}")
                result = await self.ssh_service.execute_command(credentials, command)
                
                all_output.append(f"$ {command}")
                if result.stdout:
                    all_output.append(result.stdout)
                if result.stderr:
                    all_output.append(f"STDERR: {result.stderr}")
                
                if not result.success:
                    logger.error(f"Command failed: {command}")
                    return InstallationResult(
                        success=False,
                        message=f"Ошибка при выполнении команды: {command}",
                        output="\n".join(all_output),
                        error=result.stderr
                    )
            
            logger.info("OpenVPN configuration completed successfully")
            return InstallationResult(
                success=True,
                message="OpenVPN сервер успешно настроен",
                output="\n".join(all_output)
            )
            
        except Exception as e:
            logger.error(f"Exception in configure_openvpn: {e}")
            return InstallationResult(
                success=False,
                message=f"Ошибка настройки: {str(e)}",
                output="",
                error=str(e)
            )


class OpenVPNClientManager:
    """Manage OpenVPN clients"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    def get_client_generation_commands(self, client_name: str, server_ip: str, server_port: int, protocol: str) -> List[str]:
        """Get commands to generate client certificate and .ovpn file"""
        return [
            # Step 1: Generate client certificate request
            f"cd ~/easy-rsa && ./easyrsa --batch gen-req {client_name} nopass",
            
            # Step 2: Sign client certificate
            f"cd ~/easy-rsa && ./easyrsa --batch sign-req client {client_name}",
            
            # Step 3: Create client-configs directory
            "mkdir -p ~/client-configs/files",
            "mkdir -p ~/client-configs/keys",
            
            # Step 4: Copy client files
            f"cp ~/easy-rsa/pki/private/{client_name}.key ~/client-configs/keys/",
            f"cp ~/easy-rsa/pki/issued/{client_name}.crt ~/client-configs/keys/",
            "cp ~/easy-rsa/pki/ca.crt ~/client-configs/keys/",
            "cp ~/easy-rsa/ta.key ~/client-configs/keys/",
            
            # Step 5: Create base client config
            f"cat > ~/client-configs/base.conf << 'EOF'\n"
            f"client\n"
            f"dev tun\n"
            f"proto {protocol}\n"
            f"remote {server_ip} {server_port}\n"
            f"resolv-retry infinite\n"
            f"nobind\n"
            f"user nobody\n"
            f"group nogroup\n"
            f"persist-key\n"
            f"persist-tun\n"
            f"remote-cert-tls server\n"
            f"cipher AES-256-GCM\n"
            f"auth SHA256\n"
            f"key-direction 1\n"
            f"verb 3\n"
            f"EOF",
            
            # Step 6: Create generation script
            "cat > ~/client-configs/make_config.sh << 'EOF'\n"
            "#!/bin/bash\n"
            "CLIENT=$1\n"
            "KEY_DIR=~/client-configs/keys\n"
            "OUTPUT_DIR=~/client-configs/files\n"
            "BASE_CONFIG=~/client-configs/base.conf\n"
            "\n"
            "cat ${BASE_CONFIG} \\\n"
            "    <(echo -e '<ca>') \\\n"
            "    ${KEY_DIR}/ca.crt \\\n"
            "    <(echo -e '</ca>\\n<cert>') \\\n"
            "    ${KEY_DIR}/${CLIENT}.crt \\\n"
            "    <(echo -e '</cert>\\n<key>') \\\n"
            "    ${KEY_DIR}/${CLIENT}.key \\\n"
            "    <(echo -e '</key>\\n<tls-crypt>') \\\n"
            "    ${KEY_DIR}/ta.key \\\n"
            "    <(echo -e '</tls-crypt>') \\\n"
            "    > ${OUTPUT_DIR}/${CLIENT}.ovpn\n"
            "EOF",
            
            # Step 7: Make script executable and run it
            "chmod +x ~/client-configs/make_config.sh",
            f"cd ~/client-configs && ./make_config.sh {client_name}",
        ]
    
    async def create_client(self, credentials: SSHCredentials, client_name: str, 
                          server_ip: str, server_port: int, protocol: str) -> InstallationResult:
        """Create client certificate and .ovpn config"""
        try:
            logger.info(f"Creating client: {client_name}")
            
            commands = self.get_client_generation_commands(client_name, server_ip, server_port, protocol)
            all_output = []
            
            for command in commands:
                logger.info(f"Executing: {command}")
                result = await self.ssh_service.execute_command(credentials, command)
                
                all_output.append(f"$ {command}")
                if result.stdout:
                    all_output.append(result.stdout)
                if result.stderr:
                    all_output.append(f"STDERR: {result.stderr}")
                
                if not result.success:
                    logger.error(f"Command failed: {command}")
                    return InstallationResult(
                        success=False,
                        message=f"Ошибка при выполнении команды: {command}",
                        output="\n".join(all_output),
                        error=result.stderr
                    )
            
            logger.info(f"Client {client_name} created successfully")
            return InstallationResult(
                success=True,
                message=f"Клиент {client_name} успешно создан",
                output="\n".join(all_output)
            )
            
        except Exception as e:
            logger.error(f"Exception in create_client: {e}")
            return InstallationResult(
                success=False,
                message=f"Ошибка создания клиента: {str(e)}",
                output="",
                error=str(e)
            )
    
    async def download_client_config(self, credentials: SSHCredentials, client_name: str) -> tuple[bool, str, bytes]:
        """Download .ovpn config file"""
        try:
            # Read the .ovpn file from server
            result = await self.ssh_service.execute_command(
                credentials,
                f"cat ~/client-configs/files/{client_name}.ovpn"
            )
            
            if result.success and result.stdout:
                return True, f"{client_name}.ovpn", result.stdout.encode('utf-8')
            else:
                return False, "", b""
                
        except Exception as e:
            logger.error(f"Exception downloading config: {e}")
            return False, "", b""


class OpenVPNManager:
    """Simple OpenVPN management"""    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def get_status(self, credentials: SSHCredentials) -> dict:
        """Get OpenVPN service status"""
        result = await self.ssh_service.execute_command(
            credentials, 
            "sudo systemctl status openvpn@server --no-pager -l"
        )
        
        return {
            'running': 'active (running)' in result.stdout,
            'output': result.stdout,
            'error': result.stderr if not result.success else None
        }
    
    async def start_service(self, credentials: SSHCredentials) -> CommandResult:
        """Start OpenVPN service"""
        return await self.ssh_service.execute_command(
            credentials, 
            "sudo systemctl start openvpn@server"
        )
    
    async def stop_service(self, credentials: SSHCredentials) -> CommandResult:
        """Stop OpenVPN service"""
        return await self.ssh_service.execute_command(
            credentials, 
            "sudo systemctl stop openvpn@server"
        )
    
    async def restart_service(self, credentials: SSHCredentials) -> CommandResult:
        """Restart OpenVPN service"""
        return await self.ssh_service.execute_command(
            credentials, 
            "sudo systemctl restart openvpn@server"
        )


import logging
from dataclasses import dataclass
from typing import List, Optional

from .ssh_service import SSHService, SSHCredentials, CommandResult, OpenVPNCommandBuilder


logger = logging.getLogger(__name__)


class OpenVPNInstaller:
    """Service for OpenVPN installation"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        self.command_builder = OpenVPNCommandBuilder()
    
    async def check_sudo_access(self, connection_config: SSHCredentials) -> bool:
        """Check if user has sudo access"""
        result = await self.ssh_service.execute_command(
            connection_config,
            self.command_builder.check_sudo_access()
        )
        return result.success
    
    async def check_openvpn_installed(self, connection_config: SSHCredentials) -> bool:
        """Check if OpenVPN is already installed"""
        result = await self.ssh_service.execute_command(
            connection_config,
            self.command_builder.check_openvpn_installed()
        )
        return result.success and "openvpn" in result.output.lower()
    
    async def install_openvpn(self, connection_config: SSHCredentials) -> CommandResult:
        """Install OpenVPN on remote server"""
        # First check if user has sudo access
        has_sudo = await self.check_sudo_access(connection_config)
        if not has_sudo:
            return CommandResult(
                stdout="",
                stderr="User doesn't have sudo privileges. Please ensure the SSH user has sudo access.",
                exit_code=1,
                success=False
            )
        
        # Check if already installed
        already_installed = await self.check_openvpn_installed(connection_config)
        if already_installed:
            return CommandResult(
                stdout="OpenVPN is already installed on this server.",
                stderr="",
                exit_code=0,
                success=True
            )
        
        # Install OpenVPN
        commands = self.command_builder.install_openvpn()
        all_output = []
        
        for command in commands:
            result = await self.ssh_service.execute_command(
                connection_config, 
                command
            )
            all_output.append(f"$ {command}")
            all_output.append(result.output)
            
            if not result.success:
                return CommandResult(
                    stdout="\n".join(all_output),
                    stderr=f"Failed to execute: {command}\nError: {result.stderr}",
                    exit_code=result.exit_code,
                    success=False
                )
        
        # Verify installation
        installed = await self.check_openvpn_installed(connection_config)
        if not installed:
            return CommandResult(
                stdout="\n".join(all_output),
                stderr="OpenVPN installation completed but verification failed.",
                exit_code=1,
                success=False
            )
        
        return CommandResult(
            stdout="OpenVPN has been successfully installed and configured.\n" + "\n".join(all_output),
            stderr="",
            exit_code=0,
            success=True
        )
