"""
API views for OpenVPN management
"""

import asyncio
import logging
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import (
    OpenVPNServer, CertificateAuthority, ClientCertificate, 
    VPNConnection, ServerTask
)
from .services import OpenVPNService, MonitoringService
from .ssh_service import SSHService, SSHCredentials
from .openvpn_service_simple import OpenVPNInstaller
from .ssh_key_manager import SSHKeyManager
from .vpn_monitor import VPNMonitor


logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def install_openvpn(request, server_id):
    """Install OpenVPN on the specified server"""
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Create SSH connection config
        connection_config = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key
        )
        
        # Initialize services
        ssh_service = SSHService()
        installer = OpenVPNInstaller(ssh_service)
        
        # Update server status to installing
        server.status = 'installing'
        server.save()
        
        # Execute installation
        result = asyncio.run(installer.install_openvpn(connection_config))
        
        # Check if result is InstallationResult
        if hasattr(result, 'message'):
            # InstallationResult
            if result.success:
                # Update server status to installed
                server.status = 'installed'
                server.save()
                
                return Response({
                    'success': True,
                    'message': result.message,
                    'output': result.output
                })
            else:
                # Update server status to error
                server.status = 'error'
                server.save()
                
                return Response({
                    'success': False,
                    'error': result.error,
                    'message': result.message,
                    'output': result.output
                }, status=400)
        else:
            # Fallback for CommandResult or other types
            if result.success:
                # Update server status to installed
                server.status = 'installed'
                server.save()
                
                return Response({
                    'success': True,
                    'message': 'OpenVPN installation completed',
                    'output': result.output
                })
            else:
                # Update server status to error
                server.status = 'error'
                server.save()
                
                return Response({
                    'success': False,
                    'error': result.error if hasattr(result, 'error') else result.stderr,
                    'message': 'Installation failed',
                    'output': result.output
                }, status=400)
            
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=404)
    except Exception as e:
        import traceback
        logger.error(f"Error installing OpenVPN on server {server_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'success': False,
            'error': f'Installation failed: {str(e)}'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def configure_openvpn(request, server_id):
    """Configure OpenVPN server after installation"""
    try:
        from .openvpn_service_simple import OpenVPNConfigurator
        
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Create SSH connection config
        connection_config = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key
        )
        
        # Get configuration from request or use server defaults
        server_config = {
            'port': request.data.get('port', server.openvpn_port),
            'protocol': request.data.get('protocol', server.openvpn_protocol.lower()),
            'subnet': request.data.get('subnet', server.server_subnet),
            'netmask': request.data.get('netmask', server.server_netmask),
            'dns_servers': request.data.get('dns_servers', server.get_dns_servers_list()),
        }
        
        # Initialize services
        ssh_service = SSHService()
        configurator = OpenVPNConfigurator(ssh_service)
        
        # Execute configuration
        result = asyncio.run(configurator.configure_openvpn(connection_config, server_config))
        
        # Check if result is InstallationResult
        if hasattr(result, 'message'):
            if result.success:
                return Response({
                    'success': True,
                    'message': result.message,
                    'output': result.output
                })
            else:
                return Response({
                    'success': False,
                    'error': result.error,
                    'message': result.message,
                    'output': result.output
                }, status=400)
        else:
            if result.success:
                return Response({
                    'success': True,
                    'message': 'OpenVPN configuration completed',
                    'output': result.output
                })
            else:
                return Response({
                    'success': False,
                    'error': result.error if hasattr(result, 'error') else result.stderr,
                    'message': 'Configuration failed',
                    'output': result.output
                }, status=400)
            
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=404)
    except Exception as e:
        import traceback
        logger.error(f"Error configuring OpenVPN on server {server_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'success': False,
            'error': f'Configuration failed: {str(e)}'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_client(request, server_id):
    """Create OpenVPN client certificate and configuration"""
    try:
        from .openvpn_service_simple import OpenVPNClientManager
        
        server = get_object_or_404(OpenVPNServer, id=server_id)
        client_name = request.data.get('client_name', '').strip()
        
        if not client_name:
            return Response({
                'success': False,
                'error': 'Client name is required'
            }, status=400)
        
        # Create SSH connection config
        connection_config = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key
        )
        
        # Initialize client manager
        ssh_service = SSHService()
        client_manager = OpenVPNClientManager(ssh_service)
        
        # Create client
        result = asyncio.run(client_manager.create_client(
            connection_config,
            client_name,
            server.host,
            server.openvpn_port,
            server.openvpn_protocol.lower()
        ))
        
        if result.success:
            # Save client to database
            # Set expiration date to 1 year from now (default for Easy-RSA)
            expires_at = timezone.now() + timedelta(days=365)
            
            client = ClientCertificate.objects.create(
                server=server,
                name=client_name,
                email=request.data.get('email', ''),
                client_cert='',  # Will be populated later if needed
                client_key='',   # Will be populated later if needed
                expires_at=expires_at,
                created_by=request.user
            )
            
            return Response({
                'success': True,
                'message': result.message,
                'output': result.output,
                'client_id': client.id
            })
        else:
            return Response({
                'success': False,
                'error': result.error,
                'message': result.message,
                'output': result.output
            }, status=400)
            
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=404)
    except Exception as e:
        import traceback
        logger.error(f"Error creating client on server {server_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'success': False,
            'error': f'Client creation failed: {str(e)}'
            }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_openvpn_server(request, server_id):
    """Start OpenVPN server service"""
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        logger.info(f"Starting OpenVPN server on {server.name}")
        
        # Create SSH connection config
        credentials = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key
        )
        
        # Commands to start and enable OpenVPN service
        commands = [
            "sudo systemctl start openvpn@server",
            "sudo systemctl enable openvpn@server",
            "sudo systemctl status openvpn@server"
        ]
        
        # Execute commands
        ssh_service = SSHService()
        outputs = []
        
        for cmd in commands:
            result = asyncio.run(ssh_service.execute_command(credentials, cmd))
            outputs.append(f"$ {cmd}\n{result.output}\n")
            
            if not result.success and "status" not in cmd:
                logger.error(f"Command failed: {cmd}")
                return Response({
                    'success': False,
                    'error': f'Failed to start OpenVPN: {result.error}',
                    'output': '\n'.join(outputs)
                }, status=400)
        
        # Update server status
        server.status = 'running'
        server.save()
        
        logger.info(f"OpenVPN server started successfully on {server.name}")
        
        return Response({
            'success': True,
            'message': 'OpenVPN server started successfully',
            'output': '\n'.join(outputs)
        })
        
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error starting OpenVPN server: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': f'Failed to start server: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_client_config(request, server_id, client_name):
    """Download client .ovpn configuration file"""
    try:
        from .openvpn_service_simple import OpenVPNClientManager
        from django.http import HttpResponse
        
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Create SSH connection config
        connection_config = SSHCredentials(
            hostname=server.host,
            port=server.ssh_port,
            username=server.ssh_username,
            password=server.ssh_password,
            private_key_content=server.ssh_private_key
        )
        
        # Initialize client manager
        ssh_service = SSHService()
        client_manager = OpenVPNClientManager(ssh_service)
        
        # Download config
        success, filename, content = asyncio.run(
            client_manager.download_client_config(connection_config, client_name)
        )
        
        if success:
            response = HttpResponse(content, content_type='application/x-openvpn-profile')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            return Response({
                'success': False,
                'error': 'Failed to download client config'
            }, status=404)
            
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error downloading client config: {str(e)}")
        return Response({
            'success': False,
            'error': f'Download failed: {str(e)}'
        }, status=500)


class OpenVPNServerViewSet(viewsets.ModelViewSet):
    """API ViewSet for OpenVPN servers"""
    
    queryset = OpenVPNServer.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        # Return a simple serializer for now
        from rest_framework import serializers
        
        class OpenVPNServerSerializer(serializers.ModelSerializer):
            class Meta:
                model = OpenVPNServer
                fields = '__all__'
                
        return OpenVPNServerSerializer
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get server status"""
        server = self.get_object()
        
        try:
            from .services import SSHService
            ssh_service = SSHService()
            status = ssh_service.check_openvpn_status(server)
            
            return Response({
                'status': status,
                'last_check': timezone.now()
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='ssh-command')
    def ssh_command(self, request, pk=None):
        """Execute SSH command through SSH service"""
        server = self.get_object()
        command = request.data.get('command', '').strip()
        
        if not command:
            return Response({'output': ''})
        
        async def execute_ssh_command():
            try:
                # Create SSH connection config
                connection_config = SSHCredentials(
                    hostname=server.host,
                    port=server.ssh_port,
                    username=server.ssh_username,
                    password=server.ssh_password,
                    private_key_content=server.ssh_private_key
                )
                
                # Execute command
                ssh_service = SSHService()
                result = await ssh_service.execute_command(connection_config, command)
                
                return {
                    'output': result.output,
                    'success': result.success,
                    'exit_code': result.exit_code
                }
                
            except Exception as e:
                logger.error(f"SSH command execution failed: {e}")
                return {
                    'output': f'Error: {str(e)}\\n',
                    'success': False,
                    'exit_code': 1
                }
        
        # Run async function in sync context
        try:
            result = asyncio.run(execute_ssh_command())
            return Response(result)
            
        except Exception as e:
            return Response({
                'output': f'Execution error: {str(e)}\\n',
                'success': False,
                'exit_code': 1
            })

    @action(detail=True, methods=['get'])
    def connections(self, request, pk=None):
        """Get active connections"""
        server = self.get_object()
        
        try:
            monitoring_service = MonitoringService()
            connections = monitoring_service.get_active_connections(server)
            
            return Response({
                'connections': connections,
                'count': len(connections)
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClientCertificateViewSet(viewsets.ModelViewSet):
    """API ViewSet for client certificates"""
    
    queryset = ClientCertificate.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        from rest_framework import serializers
        
        class ClientCertificateSerializer(serializers.ModelSerializer):
            class Meta:
                model = ClientCertificate
                fields = '__all__'
                
        return ClientCertificateSerializer
    
    def perform_create(self, serializer):
        """Create client certificate"""
        client = serializer.save(created_by=self.request.user)
        
        try:
            openvpn_service = OpenVPNService()
            openvpn_service.create_client_certificate(
                client.server, 
                client.name, 
                client.email
            )
        except Exception as e:
            client.delete()
            raise Exception(f"Failed to create certificate: {str(e)}")
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke client certificate"""
        client = self.get_object()
        
        if client.status == 'revoked':
            return Response(
                {'error': 'Certificate is already revoked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Update client status
            client.revoke()
            
            return Response({'message': 'Certificate revoked successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def download_config(self, request, pk=None):
        """Download client configuration file"""
        client = self.get_object()
        
        if client.is_revoked:
            return Response(
                {'error': 'Certificate is revoked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Generate client config
            config = self._generate_client_config(client)
            
            response = Response(config, content_type='application/x-openvpn-profile')
            response['Content-Disposition'] = f'attachment; filename="{client.name}.ovpn"'
            return response
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_client_config(self, client):
        """Generate OpenVPN client configuration"""
        server = client.server
        
        config = f"""client
dev tun
proto {server.openvpn_protocol.lower()}
remote {server.host} {server.openvpn_port}
resolv-retry infinite
nobind
persist-key
persist-tun
cipher AES-256-CBC
auth SHA256
verb 3

<ca>
{client.ca_cert}
</ca>

<cert>
{client.client_cert}
</cert>

<key>
{client.client_key}
</key>
"""
        return config


class ServerTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for server tasks"""
    
    queryset = ServerTask.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        from rest_framework import serializers
        
        class ServerTaskSerializer(serializers.ModelSerializer):
            class Meta:
                model = ServerTask
                fields = '__all__'
                
        return ServerTaskSerializer
    
    def get_queryset(self):
        """Filter tasks by user"""
        return self.queryset.filter(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get task status"""
        task = self.get_object()
        
        return Response({
            'task_id': task.task_id,
            'status': task.status,
            'progress': task.progress,
            'result': task.result,
            'error': task.error,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_connections(request, server_id):
    """Update VPN connections for a specific server"""
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Import here to avoid circular imports
        from .vpn_monitor import VPNMonitor
        
        # Run monitor
        monitor = VPNMonitor(server)
        asyncio.run(monitor.update_connections())
        
        # Get updated connection count
        connection_count = VPNConnection.objects.filter(client__server=server).count()
        
        return Response({
            'success': True,
            'message': f'Connections updated for {server.name}',
            'connection_count': connection_count
        })
    
    except Exception as e:
        logger.error(f"Error updating connections: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_all_connections(request):
    """Update VPN connections for all servers"""
    try:
        from .vpn_monitor import sync_monitor_all_servers
        
        sync_monitor_all_servers()
        
        total_connections = VPNConnection.objects.count()
        active_servers = OpenVPNServer.objects.filter(status='running').count()
        
        return Response({
            'success': True,
            'message': 'All connections updated',
            'total_connections': total_connections,
            'active_servers': active_servers
        })
    
    except Exception as e:
        logger.error(f"Error updating all connections: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_ssh_key(request, server_id):
    """
    Генерирует SSH ключ и устанавливает его на сервер
    
    Требует пароль для подключения к серверу в request.data
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Проверяем наличие пароля в запросе
        password = request.data.get('password')
        if not password:
            # Если пароль не передан, пытаемся использовать сохраненный
            if not server.ssh_password:
                return Response({
                    'success': False,
                    'error': 'Password required. Please provide SSH password.'
                }, status=status.HTTP_400_BAD_REQUEST)
            password = server.ssh_password
        
        # Получаем тип ключа из запроса (по умолчанию ed25519)
        key_type = request.data.get('key_type', 'ed25519')
        if key_type not in ['rsa', 'ed25519']:
            return Response({
                'success': False,
                'error': f'Invalid key type: {key_type}. Use "rsa" or "ed25519".'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Generating {key_type} SSH key for server {server.name}...")
        
        # Создаем менеджер ключей
        key_manager = SSHKeyManager(key_type=key_type)
        
        # Асинхронная генерация и установка ключа
        async def generate_and_install_async():
            result = await key_manager.generate_and_install(
                host=server.host,
                username=server.ssh_username,
                password=password,
                port=server.ssh_port
            )
            return result
        
        # Запускаем асинхронную функцию
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(generate_and_install_async())
        
        if result is None:
            return Response({
                'success': False,
                'error': 'Failed to generate SSH key pair'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        private_key, public_key, install_success = result
        
        if not install_success:
            return Response({
                'success': False,
                'error': 'SSH key generated but failed to install on server. Check server logs.',
                'private_key': private_key,
                'public_key': public_key
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Сохраняем приватный ключ в базе данных
        server.ssh_private_key = private_key
        # Очищаем пароль, так как теперь используем ключ
        if request.data.get('clear_password', False):
            server.ssh_password = None
        server.save()
        
        logger.info(f"✓ SSH key successfully generated and installed for {server.name}")
        
        return Response({
            'success': True,
            'message': f'{key_type.upper()} SSH key successfully generated and installed',
            'key_type': key_type,
            'public_key': public_key,
            'private_key_saved': True
        }, status=status.HTTP_200_OK)
        
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error generating SSH key: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_server_status(request, server_id):
    """
    Check OpenVPN server status and update database
    """
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        logger.info(f"Checking status for server {server.name}...")
        
        # Create VPN monitor
        monitor = VPNMonitor(server)
        
        # Check status asynchronously
        async def check_status_async():
            status = await monitor.check_server_status()
            await monitor.update_server_status()
            return status
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        server_status = loop.run_until_complete(check_status_async())
        
        # Refresh server from database
        server.refresh_from_db()
        
        logger.info(f"Server {server.name} status: {server_status}")
        
        return Response({
            'success': True,
            'status': server_status,
            'message': f'Server status: {server_status}',
            'server': {
                'id': server.id,
                'name': server.name,
                'status': server.status
            }
        }, status=status.HTTP_200_OK)
        
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_overall_stats(request):
    """Get overall system statistics"""
    try:
        from django.db.models import Sum
        
        total_servers = OpenVPNServer.objects.count()
        running_servers = OpenVPNServer.objects.filter(status='running').count()
        active_connections = VPNConnection.objects.count()
        total_clients = ClientCertificate.objects.count()
        
        # Calculate total data transfer
        data_stats = VPNConnection.objects.aggregate(
            total_rx=Sum('bytes_received'),
            total_tx=Sum('bytes_sent')
        )
        
        total_bytes = (data_stats['total_rx'] or 0) + (data_stats['total_tx'] or 0)
        total_data_mb = round(total_bytes / (1024 * 1024), 2)
        
        return Response({
            'total_servers': total_servers,
            'running_servers': running_servers,
            'active_connections': active_connections,
            'total_clients': total_clients,
            'total_data': f'{total_data_mb} MB',
            'avg_connection_time': '-',  # TODO: implement
            'system_load': '-'  # TODO: implement
        })
    
    except Exception as e:
        logger.error(f"Error getting overall stats: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_server_stats(request, server_id):
    """Get statistics for specific server"""
    try:
        server = get_object_or_404(OpenVPNServer, id=server_id)
        
        # Create VPN monitor to get system stats
        monitor = VPNMonitor(server)
        
        # Get system information asynchronously
        async def get_system_info():
            uptime = await monitor.get_openvpn_uptime()
            load = await monitor.get_system_load()
            return uptime, load
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        uptime, load = loop.run_until_complete(get_system_info())
        
        # Get active connections for this server
        connections = VPNConnection.objects.filter(client__server=server)
        
        # Calculate bandwidth (simple estimate from recent data)
        total_bandwidth = 0
        connections_data = []
        
        for conn in connections:
            # Calculate data transfer
            total_bytes = conn.bytes_received + conn.bytes_sent
            data_transfer = f'{round(total_bytes / (1024 * 1024), 2)} MB'
            
            # Simple bandwidth estimate (bytes per second)
            # This is approximate - for real bandwidth, need to track changes over time
            bandwidth_bps = (conn.bytes_received + conn.bytes_sent) / 60  # Rough estimate
            total_bandwidth += bandwidth_bps
            
            connections_data.append({
                'client_name': conn.client.name,
                'virtual_ip': conn.virtual_ip,
                'real_ip': conn.client_ip,
                'duration': conn.format_duration(),  # Use model method
                'data_transfer': data_transfer,
                'bytes_received': conn.bytes_received,
                'bytes_sent': conn.bytes_sent
            })
        
        # Format bandwidth
        if total_bandwidth > 1024 * 1024:
            bandwidth_str = f'{round(total_bandwidth / (1024 * 1024), 2)} MB/s'
        elif total_bandwidth > 1024:
            bandwidth_str = f'{round(total_bandwidth / 1024, 2)} KB/s'
        else:
            bandwidth_str = f'{round(total_bandwidth, 2)} B/s'
        
        # Get status display
        status_display_map = {
            'running': 'Работает',
            'stopped': 'Остановлен',
            'pending': 'Ожидает',
            'installing': 'Устанавливается',
            'error': 'Ошибка'
        }
        
        return Response({
            'status': server.status,
            'status_display': status_display_map.get(server.status, server.status),
            'active_connections': connections.count(),
            'bandwidth': bandwidth_str if total_bandwidth > 0 else '-',
            'uptime': uptime or '-',
            'load': load or '-',
            'server_info': {
                'name': server.name,
                'host': server.host,
                'port': server.openvpn_port,
                'protocol': server.openvpn_protocol.upper()
            },
            'connections': connections_data
        })
    
    except OpenVPNServer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Server not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting server stats: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



