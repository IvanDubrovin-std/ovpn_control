"""
OpenVPN management services
"""

import os
import tempfile
import subprocess
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from .models import OpenVPNServer, ClientCertificate, ServerTask
import paramiko
import uuid


class SSHService:
    """Service for SSH operations"""
    
    def __init__(self):
        self.client = None
    
    def connect(self, server):
        """Connect to server via SSH"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if server.ssh_key_path:
                # Connect using SSH key
                self.client.connect(
                    server.host,
                    port=server.ssh_port,
                    username=server.ssh_username,
                    key_filename=server.ssh_key_path,
                    timeout=30
                )
            else:
                # Connect using password
                self.client.connect(
                    server.host,
                    port=server.ssh_port,
                    username=server.ssh_username,
                    password=server.ssh_password,
                    timeout=30
                )
            return True
        except Exception as e:
            raise Exception(f"Failed to connect to {server.host}: {str(e)}")
    
    def execute_command(self, command, sudo=False):
        """Execute command on remote server"""
        if not self.client:
            raise Exception("Not connected to server")
        
        if sudo:
            command = f"sudo {command}"
        
        stdin, stdout, stderr = self.client.exec_command(command)
        
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        return {
            'exit_code': exit_code,
            'output': output,
            'error': error
        }
    
    def check_openvpn_status(self, server):
        """Check OpenVPN service status"""
        try:
            self.connect(server)
            
            # Check if OpenVPN is installed
            result = self.execute_command("which openvpn")
            if result['exit_code'] != 0:
                return 'pending'
            
            # Check if service is running
            result = self.execute_command("systemctl is-active openvpn-server@server", sudo=True)
            if result['exit_code'] == 0 and 'active' in result['output']:
                return 'running'
            else:
                return 'stopped'
                
        except Exception as e:
            return 'error'
        finally:
            self.disconnect()
    
    def disconnect(self):
        """Disconnect from server"""
        if self.client:
            self.client.close()
            self.client = None


class OpenVPNService:
    """Service for OpenVPN operations"""
    
    def __init__(self):
        self.ssh_service = SSHService()
    
    def install_server(self, server, user):
        """Install OpenVPN on server"""
        # Create task
        task = ServerTask.objects.create(
            server=server,
            task_type='install',
            task_id=str(uuid.uuid4()),
            created_by=user
        )
        
        try:
            # Update server status
            server.status = 'installing'
            server.save()
            
            # Start installation
            task.status = 'running'
            task.started_at = timezone.now()
            task.save()
            
            # Connect to server
            self.ssh_service.connect(server)
            
            # Update package lists
            result = self.ssh_service.execute_command("apt update", sudo=True)
            if result['exit_code'] != 0:
                raise Exception("Failed to update package lists")
            
            task.progress = 20
            task.save()
            
            # Install OpenVPN and Easy-RSA
            result = self.ssh_service.execute_command(
                "apt install -y openvpn easy-rsa", sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to install OpenVPN")
            
            task.progress = 40
            task.save()
            
            # Setup Easy-RSA
            self._setup_easy_rsa(server)
            
            task.progress = 60
            task.save()
            
            # Generate server certificates
            self._generate_server_certificates(server)
            
            task.progress = 80
            task.save()
            
            # Configure OpenVPN
            self._configure_openvpn_server(server)
            
            task.progress = 90
            task.save()
            
            # Start OpenVPN service
            result = self.ssh_service.execute_command(
                "systemctl enable --now openvpn-server@server", sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to start OpenVPN service")
            
            # Update server status
            server.status = 'running'
            server.save()
            
            task.mark_completed({'message': 'OpenVPN installed successfully'})
            
        except Exception as e:
            server.status = 'error'
            server.save()
            task.mark_failed(str(e))
            raise
        finally:
            self.ssh_service.disconnect()
        
        return task
    
    def _setup_easy_rsa(self, server):
        """Setup Easy-RSA for certificate management"""
        commands = [
            "mkdir -p /etc/openvpn/easy-rsa",
            "cp -r /usr/share/easy-rsa/* /etc/openvpn/easy-rsa/",
            "cd /etc/openvpn/easy-rsa && ./easyrsa init-pki",
        ]
        
        for cmd in commands:
            result = self.ssh_service.execute_command(cmd, sudo=True)
            if result['exit_code'] != 0:
                raise Exception(f"Failed to execute: {cmd}")
    
    def _generate_server_certificates(self, server):
        """Generate server certificates"""
        ca = server.ca if hasattr(server, 'ca') else None
        
        if not ca:
            # Build CA
            result = self.ssh_service.execute_command(
                'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa build-ca nopass',
                sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to build CA")
        
        # Generate server certificate
        result = self.ssh_service.execute_command(
            'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa build-server-full server nopass',
            sudo=True
        )
        if result['exit_code'] != 0:
            raise Exception("Failed to generate server certificate")
        
        # Generate DH parameters
        result = self.ssh_service.execute_command(
            'cd /etc/openvpn/easy-rsa && ./easyrsa gen-dh',
            sudo=True
        )
        if result['exit_code'] != 0:
            raise Exception("Failed to generate DH parameters")
    
    def _configure_openvpn_server(self, server):
        """Configure OpenVPN server"""
        
        # Create server configuration
        config = f"""
port {server.openvpn_port}
proto {server.openvpn_protocol}
dev tun
ca /etc/openvpn/easy-rsa/pki/ca.crt
cert /etc/openvpn/easy-rsa/pki/issued/server.crt
key /etc/openvpn/easy-rsa/pki/private/server.key
dh /etc/openvpn/easy-rsa/pki/dh.pem
server {server.server_subnet} {server.server_netmask}
ifconfig-pool-persist /var/log/openvpn/ipp.txt
"""
        
        # Add DNS servers
        dns_servers = server.get_dns_servers_list()
        for dns in dns_servers:
            config += f"push \"dhcp-option DNS {dns}\"\n"
        
        config += """
push "redirect-gateway def1 bypass-dhcp"
keepalive 10 120
cipher AES-256-CBC
auth SHA256
user nobody
group nogroup
persist-key
persist-tun
status /var/log/openvpn/openvpn-status.log
verb 3
explicit-exit-notify 1
"""
        
        # Write configuration to file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(config)
            temp_config = f.name
        
        # Copy configuration to server
        try:
            sftp = self.ssh_service.client.open_sftp()
            sftp.put(temp_config, '/tmp/server.conf')
            sftp.close()
            
            result = self.ssh_service.execute_command(
                "mv /tmp/server.conf /etc/openvpn/server/server.conf", sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to copy server configuration")
                
        finally:
            os.unlink(temp_config)
        
        # Enable IP forwarding
        result = self.ssh_service.execute_command(
            "echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf", sudo=True
        )
        
        # Apply sysctl changes
        result = self.ssh_service.execute_command("sysctl -p", sudo=True)
    
    def create_client_certificate(self, server, client_name, email=""):
        """Create client certificate"""
        try:
            self.ssh_service.connect(server)
            
            # Generate client certificate
            result = self.ssh_service.execute_command(
                f'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa build-client-full {client_name} nopass',
                sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to generate client certificate")
            
            # Get certificate and key content
            cert_result = self.ssh_service.execute_command(
                f"cat /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt", sudo=True
            )
            key_result = self.ssh_service.execute_command(
                f"cat /etc/openvpn/easy-rsa/pki/private/{client_name}.key", sudo=True
            )
            
            if cert_result['exit_code'] != 0 or key_result['exit_code'] != 0:
                raise Exception("Failed to read certificate files")
            
            # Create ClientCertificate object
            client = ClientCertificate.objects.create(
                server=server,
                name=client_name,
                email=email,
                client_cert=cert_result['output'],
                client_key=key_result['output'],
                expires_at=timezone.now() + timedelta(days=365),
                created_by_id=1  # This should be passed as parameter
            )
            
            return client
            
        except Exception as e:
            raise Exception(f"Failed to create client certificate: {str(e)}")
        finally:
            self.ssh_service.disconnect()
    
    def revoke_client_certificate(self, client):
        """Revoke client certificate"""
        try:
            self.ssh_service.connect(client.server)
            
            # Revoke certificate
            result = self.ssh_service.execute_command(
                f'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa revoke {client.name}',
                sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to revoke certificate")
            
            # Generate CRL
            result = self.ssh_service.execute_command(
                'cd /etc/openvpn/easy-rsa && ./easyrsa gen-crl',
                sudo=True
            )
            if result['exit_code'] != 0:
                raise Exception("Failed to generate CRL")
            
            # Copy CRL to OpenVPN directory
            result = self.ssh_service.execute_command(
                "cp /etc/openvpn/easy-rsa/pki/crl.pem /etc/openvpn/server/", sudo=True
            )
            
            # Restart OpenVPN service
            result = self.ssh_service.execute_command(
                "systemctl restart openvpn-server@server", sudo=True
            )
            
        except Exception as e:
            raise Exception(f"Failed to revoke certificate: {str(e)}")
        finally:
            self.ssh_service.disconnect()


class MonitoringService:
    """Service for monitoring OpenVPN connections"""
    
    def __init__(self):
        self.ssh_service = SSHService()
    
    def get_active_connections(self, server):
        """Get active VPN connections from server"""
        try:
            self.ssh_service.connect(server)
            
            # Read OpenVPN status file
            result = self.ssh_service.execute_command(
                "cat /var/log/openvpn/openvpn-status.log", sudo=True
            )
            
            if result['exit_code'] != 0:
                return []
            
            # Parse status file
            connections = []
            lines = result['output'].split('\n')
            
            parsing_clients = False
            for line in lines:
                if line.startswith('CLIENT_LIST'):
                    parsing_clients = True
                    continue
                elif line.startswith('ROUTING_TABLE'):
                    parsing_clients = False
                    continue
                
                if parsing_clients and line.strip():
                    parts = line.split(',')
                    if len(parts) >= 5:
                        connections.append({
                            'client_name': parts[0],
                            'real_address': parts[1].split(':')[0],
                            'virtual_address': parts[2],
                            'bytes_received': int(parts[3]) if parts[3].isdigit() else 0,
                            'bytes_sent': int(parts[4]) if parts[4].isdigit() else 0,
                            'connected_since': parts[5] if len(parts) > 5 else '',
                        })
            
            return connections
            
        except Exception as e:
            return []
        finally:
            self.ssh_service.disconnect()
