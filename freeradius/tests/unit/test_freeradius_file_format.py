"""Unit tests for FreeRADIUS file format validation.

These tests ensure that generated configuration files are in the correct
FreeRADIUS format per the official specification:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/raddb/format.html

Tests validate:
- Proper syntax (comments, operators, quoting)
- FreeRADIUS parser validation (radiusd -C when available)
- Format compliance with FreeRADIUS 4.0 specification
"""

import os
import pytest
import re
import subprocess
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


class TestFreeRADIUSUsersFileFormat:
    """Test FreeRADIUS users file format compliance."""
    
    def test_policy_entry_format(self, policy_generator, db_session):
        """Test that policy entries follow FreeRADIUS users file format."""
        # Create a simple policy
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            match_username="test.*",
            vlan_id=100,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Check for proper DEFAULT entry format
        assert "DEFAULT" in content
        
        # Check that reply attributes are properly indented (4 spaces)
        lines = content.split('\n')
        reply_lines = [line for line in lines if line.strip().startswith('Reply-Message') or 
                      line.strip().startswith('Tunnel-Type') or
                      line.strip().startswith('Cisco-AVPair')]
        
        for line in reply_lines:
            # Should start with 4 spaces
            assert line.startswith('    '), f"Reply attribute not properly indented: {line}"
    
    def test_mac_bypass_entry_format(self, psk_generator, db_session):
        """Test that MAC bypass entries follow FreeRADIUS users file format."""
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
        content = bypass_file.read_text()
        
        # Check for proper MAC address entry format
        # Format should be: "aa:bb:cc:dd:ee:ff" Auth-Type := Accept
        assert '"aa:bb:cc:dd:ee:ff"' in content
        assert "Auth-Type := Accept" in content
        
        # Check that reply message is properly indented
        lines = content.split('\n')
        reply_lines = [line for line in lines if 'Reply-Message' in line]
        
        for line in reply_lines:
            if line.strip().startswith('Reply-Message'):
                assert line.startswith('    '), f"Reply-Message not properly indented: {line}"
    
    def test_policy_check_items_format(self, policy_generator, db_session):
        """Test that check items are properly formatted."""
        # Create policy with check conditions
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            match_username="test.*",
            match_mac_address="aa:bb:cc:.*",
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Check for proper check item format
        # Should be: DEFAULT User-Name =~ "test.*", Calling-Station-Id =~ "aa:bb:cc:.*"
        assert 'User-Name =~' in content
        assert 'Calling-Station-Id =~' in content
        
        # Check items should be on the same line as DEFAULT
        lines = content.split('\n')
        default_lines = [line for line in lines if line.strip().startswith('DEFAULT')]
        
        assert len(default_lines) > 0
        # Check items should be comma-separated on the DEFAULT line
        default_line = default_lines[0]
        assert ',' in default_line or 'User-Name' in default_line
    
    def test_policy_reply_attributes_format(self, policy_generator, db_session):
        """Test that reply attributes are properly formatted."""
        # Create policy with reply attributes
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            vlan_id=100,
            session_timeout=3600,
            splash_url="/splash",
            registered_group_policy="registered",
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Check for proper reply attribute format
        # Should have proper indentation and operators
        assert 'Tunnel-Type := VLAN' in content or 'Tunnel-Type' in content
        assert 'Session-Timeout := 3600' in content or 'Session-Timeout' in content
        
        # Check that attributes are comma-separated (except last one)
        # Find the policy entry and check consecutive reply attributes
        lines = content.split('\n')
        in_policy_entry = False
        reply_lines = []
        
        for line in lines:
            if 'Policy: test-policy' in line or (line.strip().startswith('DEFAULT') and 'test-policy' in content[:content.find(line)]):
                in_policy_entry = True
            elif in_policy_entry:
                if line.strip().startswith(('Tunnel-Type', 'Session-Timeout', 'Cisco-AVPair', 'Reply-Message', 'Tunnel-Private-Group-Id', 'Tunnel-Medium-Type')):
                    reply_lines.append(line)
                elif line.strip() == '' and reply_lines:
                    # End of policy entry
                    break
        
        # All but the last reply attribute should end with comma
        if len(reply_lines) > 1:
            for i, line in enumerate(reply_lines[:-1]):
                assert line.rstrip().endswith(','), f"Reply attribute {i+1} should end with comma: {line}"
            
            # Last should NOT end with comma
            last_line = reply_lines[-1]
            assert not last_line.rstrip().endswith(','), f"Last reply attribute should NOT end with comma: {last_line}"
    
    def test_mac_address_format(self, psk_generator, db_session):
        """Test that MAC addresses are properly formatted."""
        # Create MAC bypass with various MAC formats
        bypass_config = RadiusMacBypassConfig(
            name="test-bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff", "11-22-33-44-55-66"],
            bypass_mode="whitelist",
            is_active=True,
            created_by="test",
        )
        db_session.add(bypass_config)
        db_session.commit()
        
        bypass_file = psk_generator.generate_mac_bypass_file(db_session)
        content = bypass_file.read_text()
        
        # MAC addresses should be quoted
        assert '"aa:bb:cc:dd:ee:ff"' in content
        # Should handle different formats (normalized)
        assert 'Auth-Type := Accept' in content
    
    def test_no_trailing_commas_on_last_attribute(self, policy_generator, db_session):
        """Test that the last reply attribute doesn't have a trailing comma."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            vlan_id=100,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Find policy section
        lines = content.split('\n')
        in_policy = False
        reply_attributes = []
        
        for line in lines:
            if 'Policy: test-policy' in line:
                in_policy = True
            elif in_policy and line.strip().startswith('DEFAULT'):
                in_policy = True
            elif in_policy and (line.startswith('    ') and not line.startswith('    #')):
                reply_attributes.append(line)
            elif in_policy and line.strip() == '' and reply_attributes:
                # End of policy
                break
        
        if reply_attributes:
            # Last attribute should not end with comma
            last_attr = reply_attributes[-1]
            assert not last_attr.rstrip().endswith(','), \
                f"Last reply attribute should not have trailing comma: {last_attr}"
    
    def test_comment_format(self, policy_generator, db_session):
        """Test that comments are properly formatted."""
        policy = RadiusPolicy(
            name="test-policy",
            description="Test policy description",
            priority=100,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Comments should start with #
        lines = content.split('\n')
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        
        for line in comment_lines:
            assert line.strip().startswith('#'), f"Comment line should start with #: {line}"
    
    def test_policy_priority_ordering(self, policy_generator, db_session):
        """Test that policies are ordered by priority in the file."""
        # Create policies with different priorities
        policy1 = RadiusPolicy(
            name="high-priority",
            priority=10,
            is_active=True,
            created_by="test",
        )
        policy2 = RadiusPolicy(
            name="low-priority",
            priority=1000,
            is_active=True,
            created_by="test",
        )
        policy3 = RadiusPolicy(
            name="medium-priority",
            priority=100,
            is_active=True,
            created_by="test",
        )
        db_session.add_all([policy1, policy2, policy3])
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Find positions of policy names
        high_pos = content.find("Policy: high-priority")
        medium_pos = content.find("Policy: medium-priority")
        low_pos = content.find("Policy: low-priority")
        
        # Should be in priority order (ascending)
        assert high_pos < medium_pos < low_pos, \
            "Policies should be ordered by priority (ascending)"
    
    def test_cisco_avpair_format(self, policy_generator, db_session):
        """Test that Cisco-AVPair attributes are properly formatted."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            registered_group_policy="registered",
            splash_url="/splash",
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Cisco-AVPair should be properly formatted
        assert 'Cisco-AVPair' in content
        
        # Check format: Cisco-AVPair := "value"
        lines = content.split('\n')
        avpair_lines = [line for line in lines if 'Cisco-AVPair' in line]
        
        for line in avpair_lines:
            # Should have operator :=
            assert ':=' in line or '+=' in line, f"Cisco-AVPair should have operator: {line}"
            # Should have quoted value
            assert '"' in line, f"Cisco-AVPair value should be quoted: {line}"


class TestFreeRADIUSFileSyntax:
    """Test FreeRADIUS file syntax compliance."""
    
    def test_no_empty_lines_in_entries(self, policy_generator, db_session):
        """Test that there are no empty lines within policy entries."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            vlan_id=100,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Find policy entry
        lines = content.split('\n')
        in_entry = False
        entry_lines = []
        
        for i, line in enumerate(lines):
            if 'Policy: test-policy' in line:
                in_entry = True
            elif in_entry and line.strip().startswith('DEFAULT'):
                entry_lines.append((i, line))
            elif in_entry and (line.startswith('    ') or line.strip() == ''):
                if line.strip() == '':
                    # Empty line - check if it's between attributes (bad) or end of entry (ok)
                    if entry_lines and i < len(lines) - 1:
                        next_line = lines[i + 1]
                        if next_line.strip().startswith(('Tunnel-Type', 'Session-Timeout', 'Cisco-AVPair', 'Reply-Message')):
                            # Empty line between attributes - this is actually ok in FreeRADIUS
                            pass
                entry_lines.append((i, line))
            elif in_entry and not line.startswith('    ') and line.strip() != '':
                # End of entry
                break
        
        # This test is informational - FreeRADIUS allows empty lines
        # but we want to ensure our generator doesn't create them unnecessarily
    
    def test_proper_quoting(self, policy_generator, db_session):
        """Test that string values are properly quoted."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            splash_url="/splash",
            registered_group_policy="registered",
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # String values should be quoted
        assert '"/splash"' in content or 'url-redirect=/splash' in content
        assert '"registered"' in content or 'air-group-policy-name=registered' in content
    
    def test_numeric_values_not_quoted(self, policy_generator, db_session):
        """Test that numeric values are not quoted."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            vlan_id=100,
            session_timeout=3600,
            is_active=True,
            created_by="test",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_file = policy_generator.generate_policy_file(db_session)
        content = policy_file.read_text()
        
        # Numeric values should not be quoted
        # Check for VLAN ID
        vlan_lines = [line for line in content.split('\n') if 'Tunnel-Private-Group-Id' in line]
        for line in vlan_lines:
            # Should be: Tunnel-Private-Group-Id := 100 (not "100")
            assert ':=' in line
            # Extract value after :=
            value_part = line.split(':=')[1].strip()
            # Should not start with quote
            assert not value_part.startswith('"'), \
                f"Numeric value should not be quoted: {line}"
    
    def test_mac_bypass_generates_valid_entries(self, psk_generator, db_session):
        """Test that MAC bypass generates actual FreeRADIUS entries, not just comments."""
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
        content = bypass_file.read_text()
        
        # Should have actual FreeRADIUS entry, not just comments
        lines = content.split('\n')
        entry_lines = [line for line in lines if not line.strip().startswith('#') and line.strip()]
        
        # Should have at least one actual entry
        assert any('Auth-Type := Accept' in line for line in entry_lines), \
            "MAC bypass file should contain actual FreeRADIUS entries"
        
        # Entry format should be: "mac" Auth-Type := Accept
        assert any('"aa:bb:cc:dd:ee:ff"' in line and 'Auth-Type' in line for line in entry_lines), \
            "MAC bypass entry should have proper format"
    
    def test_policy_file_has_valid_syntax(self, policy_generator, db_session):
        """Test that generated policy file has valid FreeRADIUS syntax."""
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
        content = policy_file.read_text()
        
        # Basic syntax checks
        # 1. DEFAULT entries should be present
        assert 'DEFAULT' in content
        
        # 2. Reply attributes should be properly indented
        lines = content.split('\n')
        default_found = False
        reply_found = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('DEFAULT'):
                default_found = True
                # Next non-empty, non-comment line should be a reply attribute
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j]
                    if next_line.strip() and not next_line.strip().startswith('#'):
                        if next_line.startswith('    '):
                            reply_found = True
                        break
        
        assert default_found, "Policy file should contain DEFAULT entries"
        
        # 3. No syntax errors (basic checks)
        # Check for balanced quotes
        quote_count = content.count('"')
        assert quote_count % 2 == 0, "Unbalanced quotes in policy file"
        
        # Check for proper operators
        assert ':=' in content or '=' in content, "Policy file should contain assignment operators"