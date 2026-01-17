"""
Unit tests for RadSec certificate manager.

Tests certificate generation, validation, and security compliance per
codeguard-1-crypto-algorithms and codeguard-1-digital-certificates rules.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.radius_certificates import RadSecCertificateManager, CertificateValidationError
from tests.fixtures.certificates import (
    temp_cert_dir,
    valid_ca_cert,
    valid_server_cert,
    expired_cert,
    weak_key_cert,
    cert_files,
)


@pytest.mark.unit
@pytest.mark.certificate
class TestCertificateGeneration:
    """Test certificate generation functionality."""

    def test_generate_ca_certificate(self, temp_cert_dir):
        """Test CA certificate generation with strong crypto."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        cert, key = manager.generate_ca_certificate(
            common_name="Test RADIUS CA",
            organization="Test Org"
        )
        
        # Verify it's a certificate
        assert isinstance(cert, x509.Certificate)
        assert isinstance(key, rsa.RSAPrivateKey)
        
        # Verify key size (MUST be 4096 for security)
        assert key.key_size == 4096, "Key size must be 4096 bits"
        
        # Verify signature algorithm (NO MD5, SHA-1)
        sig_alg_name = cert.signature_algorithm_oid._name
        assert "sha256" in sig_alg_name.lower(), f"Must use SHA-256, got {sig_alg_name}"
        assert "md5" not in sig_alg_name.lower(), "MD5 is banned"
        assert "sha1" not in sig_alg_name.lower(), "SHA-1 is banned"
        
        # Verify it's a CA certificate
        basic_constraints = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.BASIC_CONSTRAINTS
        ).value
        assert basic_constraints.ca is True, "Must be CA certificate"
        
        # Verify validity period (10 years = 3650 days)
        validity_days = (cert.not_valid_after_utc - cert.not_valid_before_utc).days
        assert validity_days == 3650, "Certificate must be valid for 10 years"
        
        # Verify subject
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        assert len(cn_attrs) == 1
        assert cn_attrs[0].value == "Test RADIUS CA"
        
        org_attrs = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        assert len(org_attrs) == 1
        assert org_attrs[0].value == "Test Org"
        
        # Verify it's self-signed
        assert cert.issuer == cert.subject

    def test_generate_server_certificate(self, temp_cert_dir, valid_ca_cert):
        """Test server certificate generation signed by CA."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        ca_cert, ca_key = valid_ca_cert
        
        cert, key = manager.generate_server_certificate(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name="radius.test.local",
            organization="Test Org",
            san_dns=["radius.local", "localhost"],
            san_ips=["127.0.0.1"],
        )
        
        # Verify it's a certificate
        assert isinstance(cert, x509.Certificate)
        assert isinstance(key, rsa.RSAPrivateKey)
        
        # Verify key size
        assert key.key_size == 4096
        
        # Verify signature algorithm
        sig_alg_name = cert.signature_algorithm_oid._name
        assert "sha256" in sig_alg_name.lower()
        
        # Verify it's NOT a CA certificate
        basic_constraints = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.BASIC_CONSTRAINTS
        ).value
        assert basic_constraints.ca is False, "Server cert must not be CA"
        
        # Verify signed by CA
        assert cert.issuer == ca_cert.subject
        
        # Verify Subject Alternative Names
        san_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value
        
        dns_names = [name.value for name in san_ext if isinstance(name, x509.DNSName)]
        assert "radius.test.local" in dns_names
        assert "radius.local" in dns_names
        assert "localhost" in dns_names
        
        ip_addresses = [str(addr.value) for addr in san_ext if isinstance(addr, x509.IPAddress)]
        assert "127.0.0.1" in ip_addresses

    def test_generate_radsec_certificates(self, temp_cert_dir):
        """Test generating complete RadSec certificate set."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        paths = manager.generate_radsec_certificates(
            server_hostname="test-radius.local",
            organization="Test Organization"
        )
        
        # Verify all files were created
        assert paths["ca_cert"].exists()
        assert paths["ca_key"].exists()
        assert paths["server_cert"].exists()
        assert paths["server_key"].exists()
        
        # Verify file permissions
        assert oct(paths["ca_cert"].stat().st_mode)[-3:] == "644"
        assert oct(paths["ca_key"].stat().st_mode)[-3:] == "600"  # Private key protected
        assert oct(paths["server_cert"].stat().st_mode)[-3:] == "644"
        assert oct(paths["server_key"].stat().st_mode)[-3:] == "600"  # Private key protected
        
        # Load and verify certificates
        ca_cert = manager.load_certificate("ca.pem")
        server_cert = manager.load_certificate("server.pem")
        
        # Verify CA signed server cert
        assert server_cert.issuer == ca_cert.subject


@pytest.mark.unit
@pytest.mark.certificate
class TestCertificateValidation:
    """Test certificate validation per security requirements."""

    def test_validate_valid_certificate(self, valid_server_cert, temp_cert_dir):
        """Test validation of a valid certificate."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, _ = valid_server_cert
        
        issues = manager.validate_certificate(cert)
        
        # Should only report that it's self-signed (informational)
        # Filter out INFO messages for this test
        critical_issues = [i for i in issues if "INFO" not in i]
        assert len(critical_issues) == 0, f"Should have no critical issues: {critical_issues}"

    def test_validate_expired_certificate(self, expired_cert, temp_cert_dir):
        """Test detection of expired certificate (CRITICAL per codeguard-1)."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, _ = expired_cert
        
        issues = manager.validate_certificate(cert)
        
        # MUST detect expiration as CRITICAL VULNERABILITY
        critical_found = any("CRITICAL VULNERABILITY" in issue for issue in issues)
        assert critical_found, "Must detect expired certificate as CRITICAL"
        
        expired_found = any("expired" in issue.lower() for issue in issues)
        assert expired_found, "Must mention certificate is expired"

    def test_validate_weak_key_certificate(self, weak_key_cert, temp_cert_dir):
        """Test detection of weak RSA key (< 2048 bits)."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, key = weak_key_cert
        
        # Verify test cert actually has weak key
        assert key.key_size == 1024, "Test cert should have 1024-bit key"
        
        issues = manager.validate_certificate(cert)
        
        # MUST detect weak key
        weak_key_found = any("weak" in issue.lower() and "key" in issue.lower() for issue in issues)
        assert weak_key_found, "Must detect weak key"
        
        # Should be high-priority warning
        high_priority_found = any("High-Priority" in issue for issue in issues)
        assert high_priority_found, "Weak key should be High-Priority warning"

    def test_validate_weak_hash_algorithm(self, temp_cert_dir):
        """Test detection of weak hash algorithms (MD5, SHA-1).
        
        Note: Modern cryptography libraries refuse to create SHA-1 signatures,
        which is itself a security feature. This test verifies that our
        validation code would catch SHA-1 if encountered.
        """
        from tests.utils.certificate_helpers import generate_weak_hash_certificate
        
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        try:
            cert, _ = generate_weak_hash_certificate()
            issues = manager.validate_certificate(cert)
            
            # MUST detect weak hash algorithm if certificate was created
            weak_hash_found = any(
                ("sha1" in issue.lower() or "insecure" in issue.lower()) 
                for issue in issues
            )
            assert weak_hash_found, "Must detect SHA-1 as insecure"
        except Exception as e:
            # If cryptography library refuses to create SHA-1 signature,
            # that's actually a good security feature - test passes
            if "sha1" in str(e).lower() or "not supported" in str(e).lower():
                pytest.skip(f"Cryptography library blocks SHA-1 signatures (good!): {e}")
            else:
                raise

    def test_validate_self_signed_certificate(self, valid_ca_cert, temp_cert_dir):
        """Test identification of self-signed certificates."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, _ = valid_ca_cert
        
        issues = manager.validate_certificate(cert)
        
        # Should identify self-signed (informational)
        self_signed_found = any("self-signed" in issue.lower() for issue in issues)
        assert self_signed_found, "Must identify self-signed certificates"
        
        # Should be INFO level
        info_found = any("INFO" in issue for issue in issues if "self-signed" in issue.lower())
        assert info_found, "Self-signed should be INFO level"

    def test_validate_not_yet_valid_certificate(self, temp_cert_dir):
        """Test detection of not-yet-valid certificates."""
        from tests.utils.certificate_helpers import generate_test_rsa_key
        
        key = generate_test_rsa_key(4096)
        
        # Create cert valid in the future
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "future.test.com"),
        ])
        
        not_before = datetime.now(timezone.utc) + timedelta(days=30)
        not_after = not_before + timedelta(days=365)
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(not_before)
            .not_valid_after(not_after)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        
        manager = RadSecCertificateManager(str(temp_cert_dir))
        issues = manager.validate_certificate(cert)
        
        # Should detect not-yet-valid
        not_yet_valid_found = any("not yet valid" in issue.lower() for issue in issues)
        assert not_yet_valid_found, "Must detect not-yet-valid certificates"


@pytest.mark.unit
@pytest.mark.certificate
class TestCertificateOperations:
    """Test certificate file operations."""

    def test_save_and_load_certificate(self, temp_cert_dir, valid_ca_cert):
        """Test saving and loading certificates."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, _ = valid_ca_cert
        
        # Save certificate
        cert_path = manager.save_certificate(cert, "test-cert.pem")
        assert cert_path.exists()
        
        # Load certificate
        loaded_cert = manager.load_certificate("test-cert.pem")
        
        # Verify they're the same
        assert loaded_cert.public_bytes(encoding=serialization.Encoding.PEM) == \
               cert.public_bytes(encoding=serialization.Encoding.PEM)

    def test_save_and_load_private_key(self, temp_cert_dir, valid_ca_cert):
        """Test saving and loading private keys."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        _, key = valid_ca_cert
        
        # Save key without password
        key_path = manager.save_private_key(key, "test-key.pem")
        assert key_path.exists()
        
        # Verify permission is 0600
        assert oct(key_path.stat().st_mode)[-3:] == "600"
        
        # Load key
        loaded_key = manager.load_private_key("test-key.pem")
        
        # Verify they're the same (compare key sizes and public keys)
        assert loaded_key.key_size == key.key_size
        assert loaded_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ) == key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def test_get_certificate_info(self, valid_server_cert, temp_cert_dir):
        """Test extracting certificate information."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        cert, _ = valid_server_cert
        
        info = manager.get_certificate_info(cert)
        
        # Verify required fields
        assert "common_name" in info
        assert "issuer" in info
        assert "serial_number" in info
        assert "valid_from" in info
        assert "valid_until" in info
        assert "key_type" in info
        assert "signature_algorithm" in info
        assert "is_self_signed" in info
        
        # Verify key type shows RSA 4096
        assert "RSA" in info["key_type"]
        assert "4096" in info["key_type"]
        
        # Verify signature algorithm
        assert "sha256" in info["signature_algorithm"].lower()


@pytest.mark.unit
@pytest.mark.certificate
class TestSecurityCompliance:
    """Test compliance with security requirements."""

    def test_no_weak_keys_generated(self, temp_cert_dir):
        """Verify generated keys meet minimum 2048-bit requirement."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        paths = manager.generate_radsec_certificates()
        
        # Load keys
        ca_key = manager.load_private_key("ca-key.pem")
        server_key = manager.load_private_key("server-key.pem")
        
        # Verify both meet minimum requirements
        assert ca_key.key_size >= 2048, "CA key must be at least 2048 bits"
        assert server_key.key_size >= 2048, "Server key must be at least 2048 bits"
        
        # Verify they actually use 4096 (our standard)
        assert ca_key.key_size == 4096, "CA key should be 4096 bits"
        assert server_key.key_size == 4096, "Server key should be 4096 bits"

    def test_no_weak_hash_algorithms_used(self, temp_cert_dir):
        """Verify no MD5 or SHA-1 used in generated certificates."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        manager.generate_radsec_certificates()
        
        # Load certificates
        ca_cert = manager.load_certificate("ca.pem")
        server_cert = manager.load_certificate("server.pem")
        
        # Verify hash algorithms
        ca_sig_alg = ca_cert.signature_algorithm_oid._name.lower()
        server_sig_alg = server_cert.signature_algorithm_oid._name.lower()
        
        # MUST NOT use MD5 or SHA-1
        assert "md5" not in ca_sig_alg, "CA cert must not use MD5"
        assert "sha1" not in ca_sig_alg, "CA cert must not use SHA-1"
        assert "md5" not in server_sig_alg, "Server cert must not use MD5"
        assert "sha1" not in server_sig_alg, "Server cert must not use SHA-1"
        
        # SHOULD use SHA-256 or stronger
        assert "sha256" in ca_sig_alg or "sha384" in ca_sig_alg or "sha512" in ca_sig_alg
        assert "sha256" in server_sig_alg or "sha384" in server_sig_alg or "sha512" in server_sig_alg

    def test_certificate_validity_period(self, temp_cert_dir):
        """Verify certificates have appropriate validity period."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        manager.generate_radsec_certificates()
        
        # Load certificates
        ca_cert = manager.load_certificate("ca.pem")
        server_cert = manager.load_certificate("server.pem")
        
        # Check validity periods
        ca_validity = (ca_cert.not_valid_after_utc - ca_cert.not_valid_before_utc).days
        server_validity = (server_cert.not_valid_after_utc - server_cert.not_valid_before_utc).days
        
        # Should be 10 years (3650 days)
        assert ca_validity == 3650, f"CA cert should be valid for 10 years, got {ca_validity} days"
        assert server_validity == 3650, f"Server cert should be valid for 10 years, got {server_validity} days"
        
        # Should not be expired
        now = datetime.now(timezone.utc)
        assert ca_cert.not_valid_after_utc > now, "CA cert should not be expired"
        assert server_cert.not_valid_after_utc > now, "Server cert should not be expired"
        
        # Should be currently valid
        assert ca_cert.not_valid_before_utc <= now, "CA cert should be currently valid"
        assert server_cert.not_valid_before_utc <= now, "Server cert should be currently valid"
