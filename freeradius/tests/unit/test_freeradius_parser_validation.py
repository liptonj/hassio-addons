"""FreeRADIUS parser validation tests.

These tests use the actual FreeRADIUS parser (radiusd -XC) to validate
that generated configuration files meet FreeRADIUS format standards.

Per FreeRADIUS documentation:
- radiusd -XC: Tests configuration for syntactical correctness
- Expected output: "Configuration appears to be OK"

References:
- Format Spec: https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/raddb/format.html
- Configuring Modules: https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/configuring_modules.html
"""

import subprocess
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.core.policy_generator import PolicyGenerator
from radius_app.core.psk_config_generator import PskConfigGenerator
from radius_app.db.models import (
    Base,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusMacBypassConfig,
    RadiusPolicy,
)


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
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def policy_generator(temp_config_dir, monkeypatch):
    """Create policy generator with temp directory."""
    monkeypatch.setenv("RADIUS_CONFIG_PATH", str(temp_config_dir))
    generator = PolicyGenerator()
    return generator


@pytest.fixture
def psk_generator(temp_config_dir, monkeypatch):
    """Create PSK config generator with temp directory."""
    monkeypatch.setenv("RADIUS_CONFIG_PATH", str(temp_config_dir))
    generator = PskConfigGenerator()
    return generator


@pytest.fixture
def radiusd_available():
    """Check if radiusd is available for validation."""
    try:
        result = subprocess.run(
            ["radiusd", "-v"],
            capture_output=True,
            timeout=5,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def create_minimal_radiusd_conf(config_dir: Path, include_file: Path) -> Path:
    """Create minimal radiusd.conf for testing.
    
    Args:
        config_dir: Directory for radiusd.conf
        include_file: File to include in users file
        
    Returns:
        Path to created radiusd.conf
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    
    radiusd_conf = config_dir / "radiusd.conf"
    radiusd_conf.write_text(f"""
prefix = /usr
exec_prefix = /usr
sysconfdir = /etc
localstatedir = /var
logdir = {config_dir}/log
raddbdir = {config_dir}

modules {{
}}

server default {{
    listen {{
        type = auth
        ipaddr = 127.0.0.1
        port = 0
    }}
    
    authorize {{
        files
    }}
}}
""")
    
    # Create users file that includes our generated file
    users_file = config_dir / "users"
    users_file.write_text(f"""
# Include generated configuration
$INCLUDE {include_file}
""")
    
    return radiusd_conf


class TestFreeRADIUSParserValidation:
    """Test that generated files can be parsed by FreeRADIUS parser.
    
    Uses radiusd -XC to validate configuration files per FreeRADIUS documentation.
    Reference: https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/configuring_modules.html
    """
    
    def test_policy_file_parses_with_radiusd(
        self, policy_generator, db_session, radiusd_available, tmp_path
    ):
        """Test that generated policy file can be parsed by radiusd -XC."""
        if not radiusd_available:
            pytest.skip("FreeRADIUS not installed - cannot validate with parser")
        
        # Create a simple policy
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            match_username="test.*",
            vlan_id=100,
            session_timeout=3600,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        
        # Create minimal radiusd.conf for testing
        config_dir = tmp_path / "raddb"
        create_minimal_radiusd_conf(config_dir, policy_file)
        
        # Test with radiusd -XC (config check mode with debug)
        # Per FreeRADIUS docs: https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/configuring_modules.html
        # This validates syntax without starting the server
        result = subprocess.run(
            ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(config_dir)
        )
        
        # radiusd -XC returns 0 if config is valid
        # Expected output: "Configuration appears to be OK"
        success_message = "Configuration appears to be OK"
        if result.returncode != 0 or success_message not in result.stdout:
            pytest.fail(
                f"FreeRADIUS parser validation failed:\n"
                f"Expected: '{success_message}'\n"
                f"Return code: {result.returncode}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}\n"
                f"Policy file content:\n{policy_file.read_text()}"
            )
    
    def test_mac_bypass_file_parses_with_radiusd(
        self, psk_generator, db_session, radiusd_available, tmp_path
    ):
        """Test that generated MAC bypass file can be parsed by radiusd -XC."""
        if not radiusd_available:
            pytest.skip("FreeRADIUS not installed - cannot validate with parser")
        
        # Create MAC bypass config
        bypass_config = RadiusMacBypassConfig(
            name="test-bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
            created_by="test",
        )
        db_session.add(bypass_config)
        db_session.commit()
        
        bypass_file = psk_generator.generate_mac_bypass_file(db_session)
        
        # Create minimal radiusd.conf for testing
        config_dir = tmp_path / "raddb"
        create_minimal_radiusd_conf(config_dir, bypass_file)
        
        # Test with radiusd -XC (recommended by FreeRADIUS docs)
        result = subprocess.run(
            ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(config_dir)
        )
        
        # Check for success message per FreeRADIUS docs
        success_message = "Configuration appears to be OK"
        if result.returncode != 0 or success_message not in result.stdout:
            pytest.fail(
                f"FreeRADIUS parser validation failed:\n"
                f"Expected: '{success_message}'\n"
                f"Return code: {result.returncode}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}\n"
                f"Bypass file content:\n{bypass_file.read_text()}"
            )
    
    def test_complex_policy_parses_with_radiusd(
        self, policy_generator, db_session, radiusd_available, tmp_path
    ):
        """Test that complex policy with all attributes parses correctly."""
        if not radiusd_available:
            pytest.skip("FreeRADIUS not installed - cannot validate with parser")
        
        # Create complex policy with all attribute types
        policy = RadiusPolicy(
            name="complex-policy",
            priority=50,
            match_username=".*",
            match_mac_address="aa:bb:cc:.*",
            vlan_id=200,
            vlan_name="Guest_VLAN",
            session_timeout=7200,
            idle_timeout=300,
            bandwidth_limit_up=10000,
            bandwidth_limit_down=50000,
            splash_url="/splash",
            registered_group_policy="registered",
            unregistered_group_policy="unregistered",
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        
        # Create minimal radiusd.conf for testing
        config_dir = tmp_path / "raddb"
        create_minimal_radiusd_conf(config_dir, policy_file)
        
        # Test with radiusd -XC (recommended by FreeRADIUS docs)
        result = subprocess.run(
            ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(config_dir)
        )
        
        # Check for success message per FreeRADIUS docs
        success_message = "Configuration appears to be OK"
        if result.returncode != 0 or success_message not in result.stdout:
            pytest.fail(
                f"FreeRADIUS parser validation failed for complex policy:\n"
                f"Expected: '{success_message}'\n"
                f"Return code: {result.returncode}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}\n"
                f"Policy file content:\n{policy_file.read_text()}"
            )
    
    def test_multiple_policies_parse_with_radiusd(
        self, policy_generator, db_session, radiusd_available, tmp_path
    ):
        """Test that multiple policies parse correctly."""
        if not radiusd_available:
            pytest.skip("FreeRADIUS not installed - cannot validate with parser")
        
        # Create multiple policies with different priorities
        policies = [
            RadiusPolicy(
                name=f"policy-{i}",
                priority=i * 10,
                vlan_id=100 + i,
                is_active=True,
                created_by="test",
            )
            for i in range(1, 6)
        ]
        for policy in policies:
            db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        
        # Create minimal radiusd.conf for testing
        config_dir = tmp_path / "raddb"
        create_minimal_radiusd_conf(config_dir, policy_file)
        
        # Test with radiusd -XC (recommended by FreeRADIUS docs)
        result = subprocess.run(
            ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(config_dir)
        )
        
        # Check for success message per FreeRADIUS docs
        success_message = "Configuration appears to be OK"
        if result.returncode != 0 or success_message not in result.stdout:
            pytest.fail(
                f"FreeRADIUS parser validation failed for multiple policies:\n"
                f"Expected: '{success_message}'\n"
                f"Return code: {result.returncode}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}\n"
                f"Policy file content:\n{policy_file.read_text()}"
            )
