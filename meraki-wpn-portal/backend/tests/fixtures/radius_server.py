"""RADIUS server test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_radius_api_client():
    """Mock RADIUS API client."""
    client = AsyncMock()
    
    # Mock methods
    client.add_client = AsyncMock(return_value={"id": 1, "message": "Client added"})
    client.delete_client = AsyncMock(return_value={"message": "Client deleted"})
    client.list_clients = AsyncMock(return_value={"clients": []})
    client.add_user = AsyncMock(return_value={"id": 1, "message": "User added"})
    client.list_users = AsyncMock(return_value={"users": []})
    client.reload_config = AsyncMock(return_value={"message": "Configuration reloaded"})
    client.health_check = AsyncMock(return_value={"status": "healthy", "radius_running": True})
    
    return client


@pytest.fixture
def radius_client_data():
    """Sample RADIUS client data."""
    return {
        "name": "test-client",
        "ipaddr": "192.168.1.1",
        "secret": "test-secret-123",
        "nas_type": "other",
        "shortname": "test",
        "network_id": "L_test_network",
        "network_name": "Test Network",
    }


@pytest.fixture
def radius_user_data():
    """Sample RADIUS user data."""
    return {
        "username": "aa:bb:cc:dd:ee:ff",
        "password": None,
        "reply_attributes": {
            "Cisco-AVPair": "udn:private-group-id=100"
        }
    }
