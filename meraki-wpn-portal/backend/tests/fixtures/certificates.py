"""Certificate test fixtures."""

import pytest
from pathlib import Path
import tempfile

from tests.utils.certificate_helpers import (
    generate_test_certificate,
    generate_expired_certificate,
    generate_weak_key_certificate,
    save_certificate_to_file,
    save_private_key_to_file,
)


@pytest.fixture
def temp_cert_dir():
    """Create temporary directory for certificates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_ca_cert():
    """Generate valid CA certificate for testing."""
    cert, key = generate_test_certificate(
        common_name="Test CA",
        key_size=4096,
        is_ca=True,
        valid_days=365,
    )
    return cert, key


@pytest.fixture
def valid_server_cert(valid_ca_cert):
    """Generate valid server certificate signed by CA."""
    ca_cert, ca_key = valid_ca_cert
    
    cert, key = generate_test_certificate(
        common_name="test-server.local",
        issuer_cert=ca_cert,
        issuer_key=ca_key,
        key_size=4096,
        valid_days=365,
    )
    return cert, key


@pytest.fixture
def expired_cert():
    """Generate expired certificate for testing."""
    return generate_expired_certificate(expired_days_ago=30)


@pytest.fixture
def weak_key_cert():
    """Generate certificate with weak key for testing."""
    return generate_weak_key_certificate(key_size=1024)


@pytest.fixture
def cert_files(temp_cert_dir, valid_ca_cert, valid_server_cert):
    """Create certificate files on disk."""
    ca_cert, ca_key = valid_ca_cert
    server_cert, server_key = valid_server_cert
    
    # Save certificates and keys
    ca_cert_path = temp_cert_dir / "ca.pem"
    ca_key_path = temp_cert_dir / "ca-key.pem"
    server_cert_path = temp_cert_dir / "server.pem"
    server_key_path = temp_cert_dir / "server-key.pem"
    
    save_certificate_to_file(ca_cert, ca_cert_path)
    save_private_key_to_file(ca_key, ca_key_path)
    save_certificate_to_file(server_cert, server_cert_path)
    save_private_key_to_file(server_key, server_key_path)
    
    return {
        "ca_cert": ca_cert_path,
        "ca_key": ca_key_path,
        "server_cert": server_cert_path,
        "server_key": server_key_path,
        "dir": temp_cert_dir,
    }
