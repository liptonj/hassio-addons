"""Pytest fixtures for Meraki WPN Portal tests."""

import os
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["HA_URL"] = "http://test-ha:8123"
os.environ["HA_TOKEN"] = "test-token"
os.environ["APP_SIGNING_KEY"] = "test-secret-key-for-testing-only"

from app.db.database import get_db
from app.db.models import Base
from app.main import app


# Create test database engine
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    # Mock the HA client
    mock_ha_client = AsyncMock()
    mock_ha_client.is_connected = True
    mock_ha_client.list_ipsks = AsyncMock(return_value=[])
    mock_ha_client.create_ipsk = AsyncMock(return_value={
        "id": "test-ipsk-id",
        "name": "Test-IPSK",
        "ssid_name": "Test-WiFi",
        "passphrase": "TestPass123",
        "status": "active",
    })
    mock_ha_client.get_ipsk = AsyncMock(return_value={
        "id": "test-ipsk-id",
        "name": "Test-IPSK",
        "ssid_name": "Test-WiFi",
        "status": "active",
    })
    mock_ha_client.get_areas = AsyncMock(return_value=[
        {"area_id": "unit_101", "name": "Unit 101"},
        {"area_id": "unit_102", "name": "Unit 102"},
    ])
    
    app.state.ha_client = mock_ha_client
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ha_client() -> AsyncMock:
    """Create a mock Home Assistant client."""
    client = AsyncMock()
    client.is_connected = True
    client.list_ipsks = AsyncMock(return_value=[])
    client.create_ipsk = AsyncMock(return_value={
        "id": "test-ipsk-id",
        "name": "Test-IPSK",
        "ssid_name": "Test-WiFi",
        "passphrase": "TestPass123",
        "status": "active",
    })
    client.get_ipsk = AsyncMock(return_value={
        "id": "test-ipsk-id",
        "name": "Test-IPSK",
        "status": "active",
    })
    return client


@pytest.fixture
def sample_registration_data() -> dict:
    """Sample registration request data."""
    return {
        "name": "John Smith",
        "email": "john@example.com",
        "unit": "201",
        "invite_code": None,
    }


@pytest.fixture
def sample_ipsk_data() -> dict:
    """Sample IPSK creation data."""
    return {
        "name": "Unit-201-John",
        "passphrase": "SecurePass123",
        "duration_hours": 0,
        "associated_unit": "201",
        "associated_user": "John Smith",
    }
