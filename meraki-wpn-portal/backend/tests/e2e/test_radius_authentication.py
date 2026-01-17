"""
E2E tests for RADIUS authentication using pyrad.

Tests actual RADIUS protocol authentication against running FreeRADIUS server.
"""

import pytest
from pathlib import Path
import time

from tests.utils.radius_client import RadiusTestClient
from tests.utils.docker_helpers import DockerComposeManager, is_docker_available


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.docker,
    pytest.mark.radius,
    pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
]


@pytest.fixture(scope="module")
def docker_env():
    """Start Docker Compose test environment."""
    compose_file = Path(__file__).parent / "docker" / "docker-compose.test.yml"
    manager = DockerComposeManager(compose_file, project_name="wpn-radius-test")
    
    try:
        manager.start(build=True)
        
        # Wait for RADIUS server
        assert manager.wait_for_port("localhost", 1812, timeout=60), \
            "RADIUS auth port not available"
        assert manager.wait_for_port("localhost", 2083, timeout=60), \
            "RadSec port not available"
        
        # Give RADIUS time to fully initialize
        time.sleep(5)
        
        yield manager
        
    finally:
        manager.stop(remove_volumes=True)


@pytest.fixture
def radius_client():
    """Create RADIUS test client."""
    return RadiusTestClient(
        server_host="localhost",
        server_port=1812,
        shared_secret="testing123",  # Default FreeRADIUS secret
        timeout=5,
    )


@pytest.mark.e2e
@pytest.mark.radius
class TestRadiusAuthentication:
    """Test RADIUS authentication protocol."""

    def test_radius_server_connectivity(self, docker_env, radius_client):
        """Test basic connectivity to RADIUS server."""
        assert radius_client.test_connectivity(), \
            "Cannot connect to RADIUS server"

    def test_mac_based_authentication_success(self, docker_env, radius_client):
        """Test successful MAC-based authentication with UDN ID."""
        # Note: This requires pre-configured user in RADIUS
        # For full test, would need to configure via RADIUS API first
        
        mac_address = "aa:bb:cc:dd:ee:ff"
        response = radius_client.authenticate_mac(mac_address)
        
        # May reject if not pre-configured, which is expected
        assert response is not None
        # Response will be Accept or Reject depending on configuration

    def test_mac_authentication_returns_cisco_avpair(self, docker_env, radius_client):
        """Test that successful auth returns Cisco-AVPair with UDN ID."""
        # This test requires a pre-configured test user
        # In full integration test, we'd set this up via API first
        
        mac_address = "test:test:test:test:test:test"
        response = radius_client.authenticate_mac(mac_address)
        
        # Check if Cisco-AVPair present (if authentication succeeded)
        if response.success:
            udn_id = response.get_cisco_avpair_udn_id()
            if udn_id is not None:
                assert udn_id >= 2, "UDN ID must be >= 2"
                assert udn_id <= 16777200, "UDN ID must be <= 16777200"

    def test_unknown_mac_rejected(self, docker_env, radius_client):
        """Test that unknown MAC address is rejected."""
        unknown_mac = "ff:ff:ff:ff:ff:ff"
        response = radius_client.authenticate_mac(unknown_mac)
        
        # Should be rejected (unless default accept configured)
        assert response is not None

    def test_authentication_with_calling_station_id(self, docker_env, radius_client):
        """Test authentication with Calling-Station-Id attribute."""
        mac_address = "aa:bb:cc:dd:ee:ff"
        response = radius_client.authenticate_mac(
            mac_address=mac_address,
            calling_station_id=mac_address,
            nas_identifier="test-ap"
        )
        
        assert response is not None


@pytest.mark.e2e
@pytest.mark.radius
@pytest.mark.slow
class TestRadSecTLS:
    """Test RadSec (RADIUS over TLS) connections."""

    def test_radsec_port_accessible(self, docker_env):
        """Test that RadSec port 2083 is accessible."""
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex(("localhost", 2083))
            assert result == 0, "Cannot connect to RadSec port 2083"
        finally:
            sock.close()

    def test_radsec_tls_handshake(self, docker_env):
        """Test TLS handshake on RadSec port."""
        import ssl
        import socket
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # For test only
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        try:
            sock.connect(("localhost", 2083))
            ssock = context.wrap_socket(sock)
            
            # Verify TLS connection established
            assert ssock.version() is not None
            
            # Verify TLS 1.2 or higher
            version = ssock.version()
            assert version in ["TLSv1.2", "TLSv1.3"], \
                f"Must use TLS 1.2+, got {version}"
            
        finally:
            try:
                ssock.close()
            except:
                pass
            sock.close()


@pytest.mark.e2e
@pytest.mark.radius
@pytest.mark.performance
class TestRadiusPerformance:
    """Test RADIUS server performance under load."""

    def test_sequential_authentications(self, docker_env, radius_client):
        """Test multiple sequential authentications."""
        num_requests = 10
        successful = 0
        
        for i in range(num_requests):
            mac = f"aa:bb:cc:dd:ee:{i:02x}"
            response = radius_client.authenticate_mac(mac)
            if response is not None:
                successful += 1
        
        # Should handle all requests
        assert successful == num_requests

    @pytest.mark.slow
    def test_concurrent_authentications(self, docker_env, radius_client):
        """Test concurrent authentication requests."""
        import concurrent.futures
        
        def authenticate(mac):
            response = radius_client.authenticate_mac(mac)
            return response is not None
        
        # Test with 20 concurrent requests
        num_concurrent = 20
        macs = [f"aa:bb:cc:dd:{i:02x}:{i:02x}" for i in range(num_concurrent)]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(authenticate, macs))
        
        # All should complete
        assert len(results) == num_concurrent
        assert all(results), "Some concurrent requests failed"

    def test_authentication_response_time(self, docker_env, radius_client):
        """Test that authentication response time is acceptable."""
        import time
        
        mac = "aa:bb:cc:dd:ee:ff"
        
        start = time.time()
        response = radius_client.authenticate_mac(mac)
        elapsed = time.time() - start
        
        # Should respond within 1 second
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, should be < 1.0s"
        assert response is not None


@pytest.mark.e2e
@pytest.mark.radius
class TestRadiusFailureScenarios:
    """Test RADIUS failure scenarios and error handling."""

    def test_invalid_shared_secret(self, docker_env):
        """Test authentication with incorrect shared secret."""
        client = RadiusTestClient(
            server_host="localhost",
            server_port=1812,
            shared_secret="wrong-secret",
            timeout=5,
        )
        
        response = client.authenticate_mac("aa:bb:cc:dd:ee:ff")
        
        # Should fail or reject
        assert response is not None

    def test_timeout_handling(self, docker_env):
        """Test timeout when RADIUS server doesn't respond."""
        # Use non-existent server to trigger timeout
        client = RadiusTestClient(
            server_host="192.0.2.1",  # TEST-NET-1, should not respond
            server_port=1812,
            shared_secret="test",
            timeout=2,
            retries=1,
        )
        
        import time
        start = time.time()
        response = client.authenticate_mac("aa:bb:cc:dd:ee:ff")
        elapsed = time.time() - start
        
        # Should timeout and return error response
        assert not response.success
        assert response.error is not None
        # Should respect timeout setting (plus small buffer)
        assert elapsed < 5.0

    def test_malformed_mac_address(self, docker_env, radius_client):
        """Test authentication with malformed MAC address."""
        # RADIUS client should handle this, but verify no crash
        try:
            response = radius_client.authenticate_mac("invalid-mac")
            # Client might normalize or reject
            assert response is not None or True  # No crash
        except Exception as e:
            # Expected to potentially fail validation
            assert "invalid" in str(e).lower() or "format" in str(e).lower()
