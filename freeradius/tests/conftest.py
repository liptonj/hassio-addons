"""Pytest fixtures for FreeRADIUS tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["API_AUTH_TOKEN"] = "test-token"
os.environ["RUN_MODE"] = "standalone"
os.environ["LOG_LEVEL"] = "DEBUG"
# Use temp directory for config paths to avoid writing to /config
import tempfile
_test_config_dir = tempfile.mkdtemp(prefix="radius_test_")
os.environ["RADIUS_CONFIG_PATH"] = _test_config_dir
os.environ["RADIUS_CLIENTS_PATH"] = os.path.join(_test_config_dir, "clients")
os.environ["RADIUS_CERTS_PATH"] = os.path.join(_test_config_dir, "certs")

# Import after setting env vars
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "rootfs/usr/bin"))

from radius_app.db.models import (
    Base,
    RadiusClient,
    UdnAssignment,
    RadiusMacBypassConfig,
    RadiusPolicy,
    RadiusEapConfig,
    RadiusEapMethod,
)


# Create test database engine with StaticPool so all connections share the same in-memory database
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Critical: shares the same connection for in-memory SQLite
    echo=False
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db() -> Session:
    """Create a fresh database for each test."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def sample_radius_client(db: Session) -> RadiusClient:
    """Create sample RADIUS client in DB."""
    client = RadiusClient(
        name="test-client",
        ipaddr="192.168.1.100",
        secret="test-secret-123",
        nas_type="other",
        network_name="Test Network",
        require_message_authenticator=True,
        is_active=True
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@pytest.fixture
def sample_udn_assignment(db: Session) -> UdnAssignment:
    """Create sample UDN assignment in DB."""
    assignment = UdnAssignment(
        user_id=1,  # Required - UDN assigned to user
        mac_address="aa:bb:cc:dd:ee:ff",  # Optional
        udn_id=100,
        user_email="test@example.com",
        unit="101",
        is_active=True
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@pytest.fixture
def sample_mac_bypass_config(db: Session) -> RadiusMacBypassConfig:
    """Create sample MAC bypass configuration."""
    config = RadiusMacBypassConfig(
        name="test-bypass",
        description="Test MAC bypass",
        mac_addresses=["aa:bb:cc:dd:ee:ff"],
        bypass_mode="whitelist",
        require_registration=False,
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@pytest.fixture
def sample_policy(db: Session) -> RadiusPolicy:
    """Create sample authorization policy."""
    policy = RadiusPolicy(
        name="test-policy",
        description="Test policy",
        priority=100,
        psk_validation_required=True,
        mac_matching_enabled=True,
        include_udn=True,
        splash_url="https://example.com/splash",
        registered_group_policy="registered-users",
        unregistered_group_policy="unregistered-users",
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@pytest.fixture
def client(db: Session):
    """Create FastAPI test client with database dependency override.
    
    This ensures the test client uses the same database session as the test fixtures.
    """
    from fastapi.testclient import TestClient
    from radius_app.main import app
    from radius_app.db.database import get_db
    
    def get_db_override():
        """Override database dependency to use test database."""
        try:
            yield db
        finally:
            pass  # Don't close - managed by db fixture
    
    # Override the database dependency
    app.dependency_overrides[get_db] = get_db_override
    
    try:
        yield TestClient(app)
    finally:
        # Clean up the override
        app.dependency_overrides.clear()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    clients_dir = config_dir / "clients"
    clients_dir.mkdir()
    return config_dir
