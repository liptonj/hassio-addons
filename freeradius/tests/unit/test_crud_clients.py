"""Unit tests for RADIUS client CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusClient
from radius_app.schemas.clients import ClientCreate, ClientUpdate


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
def sample_client():
    """Sample client data for testing."""
    return ClientCreate(
        name="test-client",
        ipaddr="192.168.1.1",
        secret="V3ryS3cur3P@ssw0rd!",
        nas_type="meraki",
        shortname="test",
        network_id="L_123456789",
        network_name="Test Network",
        require_message_authenticator=True,
        is_active=True,
    )


class TestClientValidation:
    """Test client data validation."""
    
    def test_valid_ipv4_address(self):
        """Test valid IPv4 address validation."""
        client = ClientCreate(
            name="test",
            ipaddr="192.168.1.1",
            secret="V3ryS3cur3P@ssw0rd!",
        )
        assert client.ipaddr == "192.168.1.1"
    
    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR notation."""
        client = ClientCreate(
            name="test",
            ipaddr="10.0.0.0/24",
            secret="V3ryS3cur3P@ssw0rd!",
        )
        assert client.ipaddr == "10.0.0.0/24"
    
    def test_invalid_ip_address(self):
        """Test invalid IP address rejection."""
        with pytest.raises(ValueError, match="Invalid IP address"):
            ClientCreate(
                name="test",
                ipaddr="invalid-ip",
                secret="V3ryS3cur3P@ssw0rd!",
            )
    
    def test_weak_secret_rejection(self):
        """Test weak secret rejection."""
        with pytest.raises(ValueError, match="at least 16 characters"):
            ClientCreate(
                name="test",
                ipaddr="192.168.1.1",
                secret="short",
            )
    
    def test_weak_pattern_rejection(self):
        """Test rejection of secrets with weak patterns."""
        with pytest.raises(ValueError, match="weak pattern"):
            ClientCreate(
                name="test",
                ipaddr="192.168.1.1",
                secret="password12345678",  # Contains 'password'
            )


class TestClientCRUD:
    """Test CRUD operations for RADIUS clients."""
    
    def test_create_client(self, db_session, sample_client):
        """Test creating a client in the database."""
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client = RadiusClient(**data)
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)
        
        assert client.id is not None
        assert client.name == "test-client"
        assert client.ipaddr == "192.168.1.1"
        assert client.is_active is True
    
    def test_read_client(self, db_session, sample_client):
        """Test reading a client from the database."""
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client = RadiusClient(**data)
        db_session.add(client)
        db_session.commit()
        
        retrieved = db_session.get(RadiusClient, client.id)
        assert retrieved is not None
        assert retrieved.name == "test-client"
    
    def test_update_client(self, db_session, sample_client):
        """Test updating a client."""
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client = RadiusClient(**data)
        db_session.add(client)
        db_session.commit()
        
        # Update client
        client.ipaddr = "192.168.2.1"
        client.nas_type = "cisco"
        db_session.commit()
        
        # Verify update
        retrieved = db_session.get(RadiusClient, client.id)
        assert retrieved.ipaddr == "192.168.2.1"
        assert retrieved.nas_type == "cisco"
    
    def test_soft_delete_client(self, db_session, sample_client):
        """Test soft deleting a client."""
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client = RadiusClient(**data)
        db_session.add(client)
        db_session.commit()
        
        # Soft delete
        client.is_active = False
        db_session.commit()
        
        # Verify still exists but inactive
        retrieved = db_session.get(RadiusClient, client.id)
        assert retrieved is not None
        assert retrieved.is_active is False
    
    def test_hard_delete_client(self, db_session, sample_client):
        """Test permanently deleting a client."""
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client = RadiusClient(**data)
        db_session.add(client)
        db_session.commit()
        client_id = client.id
        
        # Hard delete
        db_session.delete(client)
        db_session.commit()
        
        # Verify deleted
        retrieved = db_session.get(RadiusClient, client_id)
        assert retrieved is None
    
    def test_unique_name_constraint(self, db_session, sample_client):
        """Test that client names must be unique."""
        # Create first client
        data = sample_client.model_dump(exclude_unset=True)
        data["created_by"] = "admin"
        client1 = RadiusClient(**data)
        db_session.add(client1)
        db_session.commit()
        
        # Try to create second client with same name
        data2 = sample_client.model_dump(exclude_unset=True)
        data2["created_by"] = "admin"
        client2 = RadiusClient(**data2)
        db_session.add(client2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestClientUpdate:
    """Test client update schema."""
    
    def test_partial_update(self):
        """Test partial update with ClientUpdate schema."""
        update_data = ClientUpdate(
            ipaddr="10.0.0.1",
            # Other fields not provided
        )
        
        # Only ipaddr should be set
        dump = update_data.model_dump(exclude_unset=True)
        assert "ipaddr" in dump
        assert "name" not in dump
        assert "secret" not in dump
    
    def test_update_validation(self):
        """Test that update schema validates fields."""
        with pytest.raises(ValueError, match="Invalid IP address"):
            ClientUpdate(ipaddr="invalid")
        
        with pytest.raises(ValueError, match="at least 16 characters"):
            ClientUpdate(secret="short")
