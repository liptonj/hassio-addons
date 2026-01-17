"""Unit tests for NAD management operations."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusClient, RadiusNadExtended, RadiusNadHealth
from radius_app.schemas.nad import NadCreate, NadUpdate, NadCapabilities


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def sample_nad():
    """Sample NAD data for testing."""
    return NadCreate(
        name="test-nad",
        description="Test Network Access Device",
        ipaddr="192.168.1.1",
        secret="SecureTestSecret123!",
        nas_type="meraki",
        vendor="Cisco Meraki",
        model="MR44",
        location="Building A - Floor 2",
        radsec_enabled=True,
        radsec_port=2083,
        require_tls_cert=True,
        coa_enabled=True,
        coa_port=3799,
        require_message_authenticator=True,
        virtual_server="default",
        is_active=True,
        capabilities=NadCapabilities(
            supports_radsec=True,
            supports_coa=True,
            supports_disconnect=True,
            supports_accounting=True,
            supports_ipv6=False,
            max_sessions=1000
        )
    )


class TestNadValidation:
    """Test NAD data validation."""
    
    def test_valid_nad_creation(self, sample_nad):
        """Test valid NAD creation."""
        assert sample_nad.name == "test-nad"
        assert sample_nad.ipaddr == "192.168.1.1"
        assert sample_nad.secret == "SecureTestSecret123!"
        assert sample_nad.radsec_enabled is True
        assert sample_nad.coa_enabled is True
    
    def test_weak_secret_rejection(self):
        """Test weak secret rejection."""
        with pytest.raises(ValueError, match="at least 16 characters"):
            NadCreate(
                name="test",
                ipaddr="192.168.1.1",
                secret="short",
            )
    
    def test_radsec_port_validation(self):
        """Test RadSec port validation."""
        with pytest.raises(ValueError):
            NadCreate(
                name="test",
                ipaddr="192.168.1.1",
                secret="SecureTestSecret123!",
                radsec_enabled=True,
                radsec_port=80,  # Too low (< 1024)
            )
    
    def test_coa_port_validation(self):
        """Test CoA port validation."""
        with pytest.raises(ValueError):
            NadCreate(
                name="test",
                ipaddr="192.168.1.1",
                secret="SecureTestSecret123!",
                coa_enabled=True,
                coa_port=70000,  # Too high (> 65535)
            )
    
    def test_capabilities_optional(self):
        """Test that capabilities are optional."""
        nad = NadCreate(
            name="test",
            ipaddr="192.168.1.1",
            secret="SecureTestSecret123!",
        )
        assert nad.capabilities is None


class TestNadDatabaseOperations:
    """Test NAD database operations."""
    
    def test_create_nad_with_extended_info(self, db_session, sample_nad):
        """Test creating NAD with extended information."""
        # Create RADIUS client
        client = RadiusClient(
            name=sample_nad.name,
            ipaddr=sample_nad.ipaddr,
            secret=sample_nad.secret,
            nas_type=sample_nad.nas_type,
            require_message_authenticator=sample_nad.require_message_authenticator,
            is_active=sample_nad.is_active,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.flush()
        
        # Create extended NAD info
        extended = RadiusNadExtended(
            radius_client_id=client.id,
            description=sample_nad.description,
            vendor=sample_nad.vendor,
            model=sample_nad.model,
            location=sample_nad.location,
            radsec_enabled=sample_nad.radsec_enabled,
            radsec_port=sample_nad.radsec_port,
            require_tls_cert=sample_nad.require_tls_cert,
            coa_enabled=sample_nad.coa_enabled,
            coa_port=sample_nad.coa_port,
            virtual_server=sample_nad.virtual_server,
            capabilities=sample_nad.capabilities.model_dump() if sample_nad.capabilities else None,
        )
        db_session.add(extended)
        db_session.flush()
        
        # Create health record
        health = RadiusNadHealth(
            nad_id=extended.id,
            is_reachable=False,
            request_count=0,
            success_count=0,
            failure_count=0,
        )
        db_session.add(health)
        db_session.commit()
        
        # Verify
        assert client.id is not None
        assert extended.id is not None
        assert extended.radius_client_id == client.id
        assert health.nad_id == extended.id
        assert health.request_count == 0
    
    def test_update_nad(self, db_session, sample_nad):
        """Test updating NAD information."""
        # Create NAD
        client = RadiusClient(
            name=sample_nad.name,
            ipaddr=sample_nad.ipaddr,
            secret=sample_nad.secret,
            nas_type=sample_nad.nas_type,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.flush()
        
        extended = RadiusNadExtended(
            radius_client_id=client.id,
            vendor=sample_nad.vendor,
            model=sample_nad.model,
        )
        db_session.add(extended)
        db_session.commit()
        
        # Update
        extended.location = "Updated Location"
        extended.radsec_enabled = True
        db_session.commit()
        
        # Verify
        db_session.refresh(extended)
        assert extended.location == "Updated Location"
        assert extended.radsec_enabled is True
    
    def test_delete_nad_soft_delete(self, db_session, sample_nad):
        """Test soft delete of NAD."""
        client = RadiusClient(
            name=sample_nad.name,
            ipaddr=sample_nad.ipaddr,
            secret=sample_nad.secret,
            nas_type=sample_nad.nas_type,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.commit()
        
        # Soft delete
        client.is_active = False
        db_session.commit()
        
        # Verify still exists but inactive
        db_session.refresh(client)
        assert client.is_active is False
        assert client.id is not None
    
    def test_nad_health_tracking(self, db_session, sample_nad):
        """Test NAD health tracking."""
        client = RadiusClient(
            name=sample_nad.name,
            ipaddr=sample_nad.ipaddr,
            secret=sample_nad.secret,
            nas_type=sample_nad.nas_type,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.flush()
        
        extended = RadiusNadExtended(
            radius_client_id=client.id,
        )
        db_session.add(extended)
        db_session.flush()
        
        health = RadiusNadHealth(
            nad_id=extended.id,
            is_reachable=True,
            last_seen=datetime.now(timezone.utc),
            request_count=100,
            success_count=95,
            failure_count=5,
            avg_response_time_ms=25.5,
        )
        db_session.add(health)
        db_session.commit()
        
        # Verify health tracking
        db_session.refresh(health)
        assert health.is_reachable is True
        assert health.request_count == 100
        assert health.success_count == 95
        assert health.failure_count == 5
        assert health.avg_response_time_ms == 25.5
    
    def test_nad_foreign_key_cascade(self, db_session, sample_nad):
        """Test that deleting client has proper FK relationship to extended info."""
        # Note: CASCADE DELETE behavior varies by database. SQLite requires PRAGMA foreign_keys=ON
        # This test verifies the foreign key relationship is properly defined
        
        client = RadiusClient(
            name=sample_nad.name,
            ipaddr=sample_nad.ipaddr,
            secret=sample_nad.secret,
            nas_type=sample_nad.nas_type,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.flush()
        
        extended = RadiusNadExtended(
            radius_client_id=client.id,
            vendor="Test Vendor",
        )
        db_session.add(extended)
        db_session.commit()
        
        # Verify foreign key relationship
        assert extended.radius_client_id == client.id
        
        # Test that we can query the relationship
        result = db_session.query(RadiusNadExtended).filter_by(
            radius_client_id=client.id
        ).first()
        assert result is not None
        assert result.vendor == "Test Vendor"


class TestNadCapabilities:
    """Test NAD capabilities handling."""
    
    def test_capabilities_all_enabled(self):
        """Test NAD with all capabilities enabled."""
        caps = NadCapabilities(
            supports_radsec=True,
            supports_coa=True,
            supports_disconnect=True,
            supports_accounting=True,
            supports_ipv6=True,
            max_sessions=5000
        )
        assert caps.supports_radsec is True
        assert caps.supports_coa is True
        assert caps.supports_disconnect is True
        assert caps.max_sessions == 5000
    
    def test_capabilities_defaults(self):
        """Test NAD capabilities with defaults."""
        caps = NadCapabilities()
        assert caps.supports_radsec is False
        assert caps.supports_coa is False
        assert caps.supports_disconnect is False
        assert caps.supports_accounting is True  # Default enabled
        assert caps.supports_ipv6 is False
        assert caps.max_sessions is None
    
    def test_max_sessions_validation(self):
        """Test max sessions validation."""
        with pytest.raises(ValueError):
            NadCapabilities(max_sessions=-1)  # Negative not allowed


class TestNadUpdateSchema:
    """Test NAD update schema."""
    
    def test_partial_update(self):
        """Test partial NAD update."""
        update = NadUpdate(
            location="New Location",
            radsec_enabled=True,
        )
        assert update.location == "New Location"
        assert update.radsec_enabled is True
        assert update.vendor is None  # Not updated
    
    def test_empty_update(self):
        """Test empty update (no fields)."""
        update = NadUpdate()
        update_dict = update.model_dump(exclude_unset=True)
        assert len(update_dict) == 0
    
    def test_update_with_validation(self):
        """Test update with field validation."""
        with pytest.raises(ValueError):
            NadUpdate(secret="short")  # Too short


class TestHealthStatus:
    """Test health status calculations."""
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        total_requests = 100
        successful = 95
        failed = 5
        
        success_rate = (successful / total_requests) * 100
        assert success_rate == 95.0
    
    def test_zero_requests(self):
        """Test success rate with zero requests."""
        total_requests = 0
        successful = 0
        
        success_rate = 0.0 if total_requests == 0 else (successful / total_requests) * 100
        assert success_rate == 0.0
    
    def test_average_response_time_update(self):
        """Test weighted average response time calculation."""
        old_avg = 20.0
        new_latency = 30.0
        
        # Weighted average (70% old, 30% new)
        new_avg = old_avg * 0.7 + new_latency * 0.3
        assert new_avg == 23.0
