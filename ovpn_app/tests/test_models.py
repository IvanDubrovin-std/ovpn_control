"""
Tests for models
"""

import pytest

from ovpn_app.models import ClientCertificate, OpenVPNServer, VPNConnection


@pytest.mark.django_db
class TestOpenVPNServer:
    """Test OpenVPN Server model"""

    def test_server_creation(self, admin_user):
        """Test creating a new server"""
        server = OpenVPNServer.objects.create(
            name="Test Server",
            host="192.168.1.100",
            ssh_port=22,
            ssh_username="test",
            openvpn_port=443,
            openvpn_protocol="udp",
            server_subnet="10.8.0.0",
            server_netmask="255.255.255.0",
            user=admin_user,
        )

        assert server.name == "Test Server"
        assert server.host == "192.168.1.100"
        assert server.status == "pending"

    def test_server_str(self, test_server):
        """Test server string representation"""
        assert str(test_server) == "Test Server"

    def test_dns_servers_list(self, test_server):
        """Test DNS servers list parsing"""
        test_server.dns_servers = "8.8.8.8,1.1.1.1"
        test_server.save()

        dns_list = test_server.get_dns_servers_list()
        assert dns_list == ["8.8.8.8", "1.1.1.1"]


@pytest.mark.django_db
class TestClientCertificate:
    """Test Client Certificate model"""

    def test_client_creation(self, test_server):
        """Test creating a new client"""
        client = ClientCertificate.objects.create(
            server=test_server, name="test-client", email="test@example.com"
        )

        assert client.name == "test-client"
        assert client.server == test_server
        assert not client.is_revoked

    def test_client_revocation(self, test_client):
        """Test client revocation"""
        test_client.revoke()

        assert test_client.is_revoked
        assert test_client.revoked_at is not None

    def test_client_str(self, test_client):
        """Test client string representation"""
        assert str(test_client) == "test-client (Test Server)"


@pytest.mark.django_db
class TestVPNConnection:
    """Test VPN Connection model"""

    def test_connection_creation(self, test_client):
        """Test creating a VPN connection"""
        connection = VPNConnection.objects.create(
            client=test_client,
            client_ip="192.168.1.50",
            virtual_ip="10.8.0.6",
            bytes_received=1024,
            bytes_sent=2048,
        )

        assert connection.client == test_client
        assert connection.client_ip == "192.168.1.50"
        assert connection.virtual_ip == "10.8.0.6"

    def test_connection_duration(self, test_client):
        """Test connection duration calculation"""
        connection = VPNConnection.objects.create(
            client=test_client, client_ip="192.168.1.50", virtual_ip="10.8.0.6"
        )

        duration = connection.duration()
        assert duration.total_seconds() >= 0

    def test_format_duration(self, test_client):
        """Test duration formatting"""
        connection = VPNConnection.objects.create(
            client=test_client, client_ip="192.168.1.50", virtual_ip="10.8.0.6"
        )

        formatted = connection.format_duration()
        assert isinstance(formatted, str)
