"""Unit tests for RadSec management operations."""

import pytest
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusRadSecConfig, RadiusRadSecClient, RadiusClient
from radius_app.schemas.radsec import (
    RadSecConfigCreate,
    RadSecConfigUpdate,
    RadSecClientCreate,
    CertificateGenerateRequest,
)
from radius_app.utils.certificates import CertificateManager, CertificateError


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
def temp_cert_dir(tmp_path):
    """Create temporary certificate directory."""
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    return cert_dir


@pytest.fixture
def sample_radsec_config():
    """Sample RadSec configuration for testing."""
    return RadSecConfigCreate(
        name="test-radsec",
        description="Test RadSec Configuration",
        listen_address="0.0.0.0",
        listen_port=2083,
        tls_min_version="1.2",
        tls_max_version="1.3",
        cipher_list="ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384",
        certificate_file="/etc/raddb/certs/server.pem",
        private_key_file="/etc/raddb/certs/server-key.pem",
        ca_certificate_file="/etc/raddb/certs/ca.pem",
        require_client_cert=True,
        verify_client_cert=True,
        verify_depth=2,
        max_connections=100,
        connection_timeout=30,
        is_active=True,
    )


class TestRadSecConfigValidation:
    """Test RadSec configuration validation."""
    
    def test_valid_radsec_config(self, sample_radsec_config):
        """Test valid RadSec configuration."""
        assert sample_radsec_config.name == "test-radsec"
        assert sample_radsec_config.listen_port == 2083
        assert sample_radsec_config.tls_min_version == "1.2"
        assert sample_radsec_config.require_client_cert is True
    
    def test_port_validation(self):
        """Test port validation."""
        with pytest.raises(ValueError):
            RadSecConfigCreate(
                name="test",
                certificate_file="/test/cert.pem",
                private_key_file="/test/key.pem",
                ca_certificate_file="/test/ca.pem",
                listen_port=80,  # Too low (< 1024)
            )
    
    def test_max_connections_validation(self):
        """Test max connections validation."""
        with pytest.raises(ValueError):
            RadSecConfigCreate(
                name="test",
                certificate_file="/test/cert.pem",
                private_key_file="/test/key.pem",
                ca_certificate_file="/test/ca.pem",
                max_connections=1001,  # Too high (> 1000)
            )


class TestRadSecDatabase:
    """Test RadSec database operations."""
    
    def test_create_radsec_config(self, db_session, sample_radsec_config):
        """Test creating RadSec configuration in database."""
        config = RadiusRadSecConfig(
            **sample_radsec_config.model_dump(exclude={"created_by"}),
            created_by="test-user",
        )
        db_session.add(config)
        db_session.commit()
        
        assert config.id is not None
        assert config.name == "test-radsec"
        assert config.listen_port == 2083
    
    def test_update_radsec_config(self, db_session, sample_radsec_config):
        """Test updating RadSec configuration."""
        config = RadiusRadSecConfig(
            **sample_radsec_config.model_dump(exclude={"created_by"}),
            created_by="test-user",
        )
        db_session.add(config)
        db_session.commit()
        
        # Update
        config.listen_port = 2084
        config.max_connections = 200
        db_session.commit()
        
        # Verify
        db_session.refresh(config)
        assert config.listen_port == 2084
        assert config.max_connections == 200
    
    def test_delete_radsec_config(self, db_session, sample_radsec_config):
        """Test deleting RadSec configuration."""
        config = RadiusRadSecConfig(
            **sample_radsec_config.model_dump(exclude={"created_by"}),
            created_by="test-user",
        )
        db_session.add(config)
        db_session.commit()
        
        config_id = config.id
        
        # Delete
        db_session.delete(config)
        db_session.commit()
        
        # Verify
        result = db_session.query(RadiusRadSecConfig).filter_by(id=config_id).first()
        assert result is None


class TestRadSecClient:
    """Test RadSec client operations."""
    
    def test_create_radsec_client(self, db_session):
        """Test creating RadSec client."""
        client = RadiusRadSecClient(
            name="test-client",
            description="Test client",
            certificate_subject="CN=test-client",
            certificate_fingerprint="aa:bb:cc:dd:ee:ff",
            is_active=True,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.commit()
        
        assert client.id is not None
        assert client.name == "test-client"
        assert client.certificate_subject == "CN=test-client"
    
    def test_radsec_client_with_radius_client(self, db_session):
        """Test RadSec client linked to RADIUS client."""
        # Create RADIUS client
        radius_client = RadiusClient(
            name="radius-client",
            ipaddr="192.168.1.1",
            secret="SecureTestSecret123!",
            nas_type="other",
            is_active=True,
            created_by="test-user",
        )
        db_session.add(radius_client)
        db_session.flush()
        
        # Create RadSec client linked to RADIUS client
        radsec_client = RadiusRadSecClient(
            name="radsec-client",
            certificate_subject="CN=radsec-client",
            radius_client_id=radius_client.id,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(radsec_client)
        db_session.commit()
        
        # Verify link
        assert radsec_client.radius_client_id == radius_client.id


class TestCertificateManager:
    """Test certificate management."""
    
    def test_certificate_manager_initialization(self, temp_cert_dir):
        """Test certificate manager initialization."""
        cert_manager = CertificateManager(temp_cert_dir)
        assert cert_manager.cert_dir == temp_cert_dir
        assert temp_cert_dir.exists()
    
    def test_generate_ca_certificate(self, temp_cert_dir):
        """Test CA certificate generation."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        cert_path, key_path = cert_manager.generate_ca_certificate(
            common_name="Test CA",
            organization="Test Org",
            country="US",
            validity_days=365,
            key_size=2048,
        )
        
        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.name == "ca.pem"
        assert key_path.name == "ca-key.pem"
    
    def test_generate_server_certificate(self, temp_cert_dir):
        """Test server certificate generation."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate CA first
        cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        
        # Generate server certificate
        cert_path, key_path = cert_manager.generate_server_certificate(
            common_name="test-server.example.com",
            organization="Test Org",
            country="US",
            validity_days=397,
            key_size=2048,
        )
        
        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.name == "server.pem"
        assert key_path.name == "server-key.pem"
    
    def test_parse_certificate(self, temp_cert_dir):
        """Test certificate parsing."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate certificate
        cert_path, _ = cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        
        # Parse certificate
        cert_info = cert_manager.parse_certificate(cert_path)
        
        assert "subject" in cert_info
        assert "issuer" in cert_info
        assert "valid_from" in cert_info
        assert "valid_until" in cert_info
        assert "is_expired" in cert_info
        assert "fingerprint_sha256" in cert_info
        assert cert_info["is_expired"] is False
    
    def test_certificate_expiry_detection(self, temp_cert_dir):
        """Test certificate expiry detection."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate certificate with short validity
        cert_path, _ = cert_manager.generate_ca_certificate(
            common_name="Test CA",
            validity_days=1,
            key_size=2048,
        )
        
        cert_info = cert_manager.parse_certificate(cert_path)
        
        # Should not be expired yet
        assert cert_info["is_expired"] is False
        assert cert_info["days_until_expiry"] >= 0
    
    def test_weak_key_detection(self, temp_cert_dir):
        """Test detection of weak RSA keys."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate with minimum key size
        cert_path, _ = cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        
        cert_info = cert_manager.parse_certificate(cert_path)
        
        # 2048 is acceptable, no warning
        assert cert_info["key_size"] == 2048
        weak_warnings = [w for w in cert_info.get("warnings", []) if "WEAK KEY" in w]
        assert len(weak_warnings) == 0
    
    def test_certificate_validation_error_on_weak_key(self, temp_cert_dir):
        """Test that key size < 2048 raises error."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        with pytest.raises(CertificateError, match="at least 2048 bits"):
            cert_manager.generate_ca_certificate(
                common_name="Test CA",
                key_size=1024,  # Too weak
            )
    
    def test_certificate_validity_limit(self, temp_cert_dir):
        """Test certificate validity limit enforcement."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate CA
        cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        
        # Try to generate server cert with excessive validity
        with pytest.raises(CertificateError, match="must not exceed 825 days"):
            cert_manager.generate_server_certificate(
                common_name="test-server",
                validity_days=826,  # Too long
                key_size=2048,
            )
    
    def test_verify_certificate_chain(self, temp_cert_dir):
        """Test certificate chain verification."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate CA
        ca_cert_path, _ = cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        
        # Generate server certificate
        server_cert_path, _ = cert_manager.generate_server_certificate(
            common_name="test-server",
            key_size=2048,
        )
        
        # Verify chain
        is_valid, error = cert_manager.verify_certificate_chain(
            server_cert_path,
            ca_cert_path,
        )
        
        assert is_valid is True
        assert error is None
    
    def test_list_certificates(self, temp_cert_dir):
        """Test listing certificates."""
        cert_manager = CertificateManager(temp_cert_dir)
        
        # Generate some certificates
        cert_manager.generate_ca_certificate(
            common_name="Test CA",
            key_size=2048,
        )
        cert_manager.generate_server_certificate(
            common_name="test-server",
            key_size=2048,
        )
        
        # List certificates
        certs = cert_manager.list_certificates()
        
        # Should have 2 certificates (CA and server)
        assert len(certs) == 2
        assert all("file_name" in cert for cert in certs)
        assert all("subject" in cert for cert in certs)


class TestCertificateGenerateRequest:
    """Test certificate generation request validation."""
    
    def test_valid_certificate_request(self):
        """Test valid certificate generation request."""
        request = CertificateGenerateRequest(
            common_name="test.example.com",
            organization="Test Org",
            country="US",
            validity_days=397,
            key_size=4096,
        )
        assert request.common_name == "test.example.com"
        assert request.validity_days == 397
        assert request.key_size == 4096
    
    def test_validity_days_validation(self):
        """Test validity days validation."""
        with pytest.raises(ValueError):
            CertificateGenerateRequest(
                common_name="test",
                validity_days=826,  # > 825
            )
    
    def test_default_values(self):
        """Test default values."""
        request = CertificateGenerateRequest(
            common_name="test",
        )
        assert request.organization == "FreeRADIUS"
        assert request.country == "US"
        assert request.validity_days == 397
        assert request.key_size == 4096
