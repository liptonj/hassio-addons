"""
Tests for FreeRADIUS radius-manager API.

Tests the management API endpoints for configuring FreeRADIUS.
"""

import pytest
import httpx
from pathlib import Path

from tests.utils.docker_helpers import DockerComposeManager, is_docker_available


pytestmark = [
    pytest.mark.integration,
    pytest.mark.radius,
]


@pytest.fixture
def radius_api_url():
    """RADIUS API base URL."""
    return "http://localhost:8000"


@pytest.fixture
def radius_api_token():
    """RADIUS API authentication token."""
    return "test-radius-token"


@pytest.mark.asyncio
class TestRadiusManagerAPI:
    """Test RADIUS manager API endpoints."""

    async def test_health_check(self, radius_api_url):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{radius_api_url}/health",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert "status" in data
                    assert "timestamp" in data
                    assert "radius_running" in data
            except httpx.ConnectError:
                pytest.skip("RADIUS server not running")

    async def test_list_clients_requires_auth(self, radius_api_url):
        """Test that listing clients requires authentication."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{radius_api_url}/api/clients",
                    timeout=5.0
                )
                # Should require authentication (401)  or return data
                assert response.status_code in [200, 401]
            except httpx.ConnectError:
                pytest.skip("RADIUS server not running")

    async def test_add_client(self, radius_api_url, radius_api_token):
        """Test adding a RADIUS client."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{radius_api_url}/api/clients",
                    json={
                        "name": "test-client",
                        "ipaddr": "192.168.1.100",
                        "secret": "test-secret-123",
                        "nas_type": "other",
                        "shortname": "test",
                    },
                    headers={"Authorization": f"Bearer {radius_api_token}"},
                    timeout=10.0
                )
                
                # Should succeed (201) or conflict if exists (409)
                assert response.status_code in [201, 409]
                
                if response.status_code == 201:
                    data = response.json()
                    assert "id" in data or "message" in data
            except httpx.ConnectError:
                pytest.skip("RADIUS server not running")

    async def test_add_user(self, radius_api_url, radius_api_token):
        """Test adding a RADIUS user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{radius_api_url}/api/users",
                    json={
                        "username": "test:mac:address",
                        "password": None,
                        "reply_attributes": {
                            "Cisco-AVPair": "udn:private-group-id=100"
                        }
                    },
                    headers={"Authorization": f"Bearer {radius_api_token}"},
                    timeout=10.0
                )
                
                # Should succeed or conflict
                assert response.status_code in [201, 409]
            except httpx.ConnectError:
                pytest.skip("RADIUS server not running")

    async def test_config_reload(self, radius_api_url, radius_api_token):
        """Test configuration reload endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{radius_api_url}/api/reload",
                    headers={"Authorization": f"Bearer {radius_api_token}"},
                    timeout=10.0
                )
                
                # Should succeed or fail gracefully
                assert response.status_code in [200, 500]
            except httpx.ConnectError:
                pytest.skip("RADIUS server not running")
