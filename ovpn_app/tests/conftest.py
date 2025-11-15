"""
Test configuration and fixtures
"""

import pytest
from django.contrib.auth.models import User

from ovpn_app.models import ClientCertificate, OpenVPNServer


@pytest.fixture
def admin_user(db):
    """Create admin user for tests"""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="admin123",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def test_server(db, admin_user):
    """Create test OpenVPN server"""
    return OpenVPNServer.objects.create(
        name="Test Server",
        host="192.168.1.100",
        ssh_port=22,
        ssh_username="test",
        ssh_password="test123",
        openvpn_port=1194,
        openvpn_protocol="udp",
        server_subnet="10.8.0.0",
        server_netmask="255.255.255.0",
        status="pending",
        user=admin_user,
    )


@pytest.fixture
def test_client(db, test_server):
    """Create test client certificate"""
    return ClientCertificate.objects.create(
        server=test_server, name="test-client", email="test@example.com"
    )
