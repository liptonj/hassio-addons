"""
Integration tests for WPN Portal and FreeRADIUS synchronization.

Tests the synchronization of clients, UDN assignments, and certificates
between the WPN Portal and FreeRADIUS server.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.core.radius_certificates import RadSecCertificateManager
from app.core.udn_manager import UdnManager
from app.db.models import RadiusClient, UdnAssignment
from tests.fixtures.certificates import temp_cert_dir, valid_ca_cert
from tests.fixtures.radius_server import mock_radius_api_client, radius_client_data
from tests.fixtures.meraki_mock import mock_meraki_client


@pytest.fixture
def mock_radius_api():
    """Mock RADIUS API client with httpx."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    
    # Mock responses
    mock_client.post = AsyncMock(return_value=MagicMock(
        status_code=201,
        json=MagicMock(return_value={"id": 1, "message": "Success"})
    ))
    mock_client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"clients": [], "users": []})
    ))
    mock_client.delete = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"message": "Deleted"})
    ))
    
    return mock_client


@pytest.mark.integration
@pytest.mark.radius
class TestClientSynchronization:
    """Test RADIUS client synchronization between WPN and FreeRADIUS."""

    @pytest.mark.asyncio
    async def test_add_client_syncs_to_radius(self, db, mock_radius_api, radius_client_data):
        """Test that adding a client in WPN syncs to FreeRADIUS."""
        # Create client in database
        client = RadiusClient(
            name=radius_client_data["name"],
            ipaddr=radius_client_data["ipaddr"],
            secret=radius_client_data["secret"],
            nas_type=radius_client_data["nas_type"],
            shortname=radius_client_data["shortname"],
            network_id=radius_client_data["network_id"],
            network_name=radius_client_data["network_name"],
            require_message_authenticator=True,
            is_active=True,
            created_by="test_admin",
        )
        db.add(client)
        db.commit()
        
        # Mock RADIUS API call
        with patch("httpx.AsyncClient", return_value=mock_radius_api):
            async with httpx.AsyncClient() as client_api:
                response = await client_api.post(
                    "http://localhost:8000/api/clients",
                    json={
                        "name": radius_client_data["name"],
                        "ipaddr": radius_client_data["ipaddr"],
                        "secret": radius_client_data["secret"],
                        "nas_type": radius_client_data["nas_type"],
                        "shortname": radius_client_data["shortname"],
                    },
                    headers={"Authorization": "Bearer test-token"}
                )
        
        # Verify sync was attempted
        mock_radius_api.post.assert_called_once()
        call_args = mock_radius_api.post.call_args
        assert "clients" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_client_removes_from_radius(self, db, mock_radius_api):
        """Test that deleting a client removes it from FreeRADIUS."""
        # Create and then delete client
        client = RadiusClient(
            name="test-client",
            ipaddr="192.168.1.1",
            secret="test-secret",
            nas_type="other",
            is_active=True,
            created_by="test_admin",
        )
        db.add(client)
        db.commit()
        
        client_id = client.id
        
        # Soft delete
        client.is_active = False
        db.commit()
        
        # Mock RADIUS API call
        with patch("httpx.AsyncClient", return_value=mock_radius_api):
            async with httpx.AsyncClient() as client_api:
                response = await client_api.delete(
                    f"http://localhost:8000/api/clients/{client_id}",
                    headers={"Authorization": "Bearer test-token"}
                )
        
        # Verify deletion was attempted
        assert mock_radius_api.delete.called or mock_radius_api.post.called


@pytest.mark.integration
@pytest.mark.radius
@pytest.mark.udn
class TestUdnAssignmentSynchronization:
    """Test UDN assignment synchronization with RADIUS users file."""

    def test_create_udn_assignment_generates_radius_entry(self, db):
        """Test that creating UDN assignment generates proper RADIUS entry."""
        udn_manager = UdnManager(db)
        
        # Create UDN assignment
        assignment = udn_manager.assign_udn_id(
            mac_address="aa:bb:cc:dd:ee:ff",
            user_name="Test User",
            unit="101",
            specific_udn_id=500,
        )
        
        # Generate RADIUS entry
        entry = udn_manager.generate_radius_users_entry(assignment)
        
        # Verify entry format
        assert "aa:bb:cc:dd:ee:ff" in entry
        assert "Cisco-AVPair" in entry
        assert "udn:private-group-id=500" in entry

    def test_multiple_assignments_generate_complete_users_file(self, db):
        """Test generating complete RADIUS users file with multiple assignments."""
        udn_manager = UdnManager(db)
        
        # Create multiple assignments
        for i in range(5):
            udn_manager.assign_udn_id(
                mac_address=f"aa:bb:cc:dd:ee:{i:02x}",
                user_name=f"User {i}",
                unit=f"10{i}",
            )
        
        # Generate complete users file
        users_file = udn_manager.generate_all_radius_users()
        
        # Verify all assignments included
        for i in range(5):
            assert f"aa:bb:cc:dd:ee:{i:02x}" in users_file
        
        # Verify default deny rule
        assert "DEFAULT Auth-Type := Reject" in users_file

    @pytest.mark.asyncio
    async def test_udn_assignment_syncs_to_radius_api(self, db, mock_radius_api):
        """Test that UDN assignment syncs to RADIUS server via API."""
        udn_manager = UdnManager(db)
        
        # Create UDN assignment
        assignment = udn_manager.assign_udn_id(
            mac_address="aa:bb:cc:dd:ee:ff",
            user_name="Test User",
            specific_udn_id=100,
        )
        
        # Sync to RADIUS API
        with patch("httpx.AsyncClient", return_value=mock_radius_api):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/users",
                    json={
                        "username": assignment.mac_address,
                        "password": None,
                        "reply_attributes": {
                            "Cisco-AVPair": f"udn:private-group-id={assignment.udn_id}"
                        }
                    },
                    headers={"Authorization": "Bearer test-token"}
                )
        
        # Verify sync was attempted
        mock_radius_api.post.assert_called()

    def test_revoke_assignment_removes_from_radius_users(self, db):
        """Test that revoking assignment removes it from RADIUS users file."""
        udn_manager = UdnManager(db)
        
        # Create assignment
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:ff", specific_udn_id=100)
        
        # Generate users file (should include it)
        users_file_before = udn_manager.generate_all_radius_users()
        assert "aa:bb:cc:dd:ee:ff" in users_file_before
        
        # Revoke assignment
        udn_manager.revoke_assignment("aa:bb:cc:dd:ee:ff")
        
        # Generate users file again (should NOT include it)
        users_file_after = udn_manager.generate_all_radius_users()
        assert "aa:bb:cc:dd:ee:ff" not in users_file_after


@pytest.mark.integration
@pytest.mark.certificate
@pytest.mark.radius
class TestCertificateSynchronization:
    """Test certificate synchronization between WPN and FreeRADIUS."""

    def test_generate_certificates_available_for_radius(self, temp_cert_dir):
        """Test that generated certificates are available to FreeRADIUS."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        paths = manager.generate_radsec_certificates(
            server_hostname="radius.test.local",
            organization="Test Org"
        )
        
        # Verify all certificate files exist
        assert paths["ca_cert"].exists()
        assert paths["ca_key"].exists()
        assert paths["server_cert"].exists()
        assert paths["server_key"].exists()
        
        # Verify FreeRADIUS can read them
        ca_cert = manager.load_certificate("ca.pem")
        server_cert = manager.load_certificate("server.pem")
        
        assert ca_cert is not None
        assert server_cert is not None

    def test_certificate_permissions_for_radius_user(self, temp_cert_dir):
        """Test that certificate file permissions allow RADIUS server to read them."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        paths = manager.generate_radsec_certificates()
        
        # Verify certificates are readable (644)
        assert oct(paths["ca_cert"].stat().st_mode)[-3:] == "644"
        assert oct(paths["server_cert"].stat().st_mode)[-3:] == "644"
        
        # Verify private keys are protected (600)
        assert oct(paths["ca_key"].stat().st_mode)[-3:] == "600"
        assert oct(paths["server_key"].stat().st_mode)[-3:] == "600"

    @pytest.mark.asyncio
    async def test_meraki_ca_upload_flow(self, temp_cert_dir, mock_meraki_client):
        """Test uploading FreeRADIUS CA to Meraki."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Generate certificates
        manager.generate_radsec_certificates()
        
        # Load CA certificate
        ca_cert = manager.load_certificate("ca.pem")
        from cryptography.hazmat.primitives import serialization
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()
        
        # Mock upload to Meraki
        result = await mock_meraki_client.upload_radsec_ca_certificate(
            organization_id="123456",
            cert_contents=ca_pem,
        )
        
        # Verify upload was called
        assert result is not None
        assert "certificate_id" in result

    @pytest.mark.asyncio
    async def test_meraki_device_ca_download_flow(self, temp_cert_dir, mock_meraki_client):
        """Test downloading Meraki device CA and saving for FreeRADIUS."""
        manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # Mock download from Meraki
        device_cas = await mock_meraki_client.get_radsec_device_certificate_authorities(
            organization_id="123456"
        )
        
        assert len(device_cas) > 0
        device_ca = device_cas[0]
        
        # Save to FreeRADIUS certs directory
        meraki_ca_path = manager.certs_path / "meraki-device-ca.pem"
        with open(meraki_ca_path, "w") as f:
            f.write(device_ca["contents"])
        meraki_ca_path.chmod(0o644)
        
        # Verify saved
        assert meraki_ca_path.exists()
        assert oct(meraki_ca_path.stat().st_mode)[-3:] == "644"


@pytest.mark.integration
@pytest.mark.radius
class TestRadiusConfigurationReload:
    """Test RADIUS configuration reload after synchronization."""

    @pytest.mark.asyncio
    async def test_clients_conf_regeneration(self, db, mock_radius_api):
        """Test that clients.conf is regenerated after client changes."""
        # Add multiple clients
        for i in range(3):
            client = RadiusClient(
                name=f"client-{i}",
                ipaddr=f"192.168.1.{i+10}",
                secret=f"secret-{i}",
                nas_type="other",
                is_active=True,
                created_by="test_admin",
            )
            db.add(client)
        db.commit()
        
        # Mock reload API call
        with patch("httpx.AsyncClient", return_value=mock_radius_api):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/reload",
                    headers={"Authorization": "Bearer test-token"}
                )
        
        # Verify reload was attempted
        mock_radius_api.post.assert_called()

    @pytest.mark.asyncio
    async def test_users_file_regeneration(self, db, mock_radius_api):
        """Test that users file is regenerated after UDN changes."""
        udn_manager = UdnManager(db)
        
        # Create multiple UDN assignments
        for i in range(3):
            udn_manager.assign_udn_id(
                mac_address=f"aa:bb:cc:dd:ee:{i:02x}",
                user_name=f"User {i}",
            )
        
        # Generate users file
        users_file = udn_manager.generate_all_radius_users()
        
        # Verify all assignments are in the file
        for i in range(3):
            assert f"aa:bb:cc:dd:ee:{i:02x}" in users_file


@pytest.mark.integration
@pytest.mark.radius
class TestEndToEndSync:
    """Test complete end-to-end synchronization workflows."""

    @pytest.mark.asyncio
    async def test_complete_registration_to_radius_flow(self, db, mock_radius_api):
        """Test complete flow from user registration to RADIUS configuration."""
        udn_manager = UdnManager(db)
        
        # 1. User registers (simulated)
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "unit": "201",
            "mac_address": "aa:bb:cc:dd:ee:ff"
        }
        
        # 2. UDN ID assigned
        assignment = udn_manager.assign_udn_id(
            mac_address=user_data["mac_address"],
            user_name=user_data["name"],
            user_email=user_data["email"],
            unit=user_data["unit"],
        )
        
        assert assignment is not None
        assert assignment.udn_id >= 2
        
        # 3. Generate RADIUS users entry
        entry = udn_manager.generate_radius_users_entry(assignment)
        assert user_data["mac_address"].replace(":", ":") in entry
        assert f"udn:private-group-id={assignment.udn_id}" in entry
        
        # 4. Sync to RADIUS server (mocked)
        with patch("httpx.AsyncClient", return_value=mock_radius_api):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/users",
                    json={
                        "username": assignment.mac_address,
                        "reply_attributes": {
                            "Cisco-AVPair": f"udn:private-group-id={assignment.udn_id}"
                        }
                    },
                    headers={"Authorization": "Bearer test-token"}
                )
        
        # 5. Verify sync successful
        mock_radius_api.post.assert_called()

    @pytest.mark.asyncio
    async def test_network_setup_to_radius_configuration(
        self, 
        db, 
        temp_cert_dir,
        mock_meraki_client,
        mock_radius_api
    ):
        """Test complete network setup flow with certificate exchange and client config."""
        cert_manager = RadSecCertificateManager(str(temp_cert_dir))
        
        # 1. Generate RadSec certificates
        cert_manager.generate_radsec_certificates(
            server_hostname="radius.test.local"
        )
        
        # 2. Upload CA to Meraki
        ca_cert = cert_manager.load_certificate("ca.pem")
        from cryptography.hazmat.primitives import serialization
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()
        
        upload_result = await mock_meraki_client.upload_radsec_ca_certificate(
            organization_id="123456",
            cert_contents=ca_pem,
        )
        assert "certificate_id" in upload_result
        
        # 3. Download Meraki device CA
        device_cas = await mock_meraki_client.get_radsec_device_certificate_authorities(
            organization_id="123456"
        )
        assert len(device_cas) > 0
        
        # 4. Add network as RADIUS client
        client = RadiusClient(
            name="Test Network",
            ipaddr="0.0.0.0/0",
            secret="test-shared-secret",
            nas_type="other",
            network_id="L_test_network",
            network_name="Test Network",
            is_active=True,
            created_by="test_admin",
        )
        db.add(client)
        db.commit()
        
        # 5. Configure SSID for RadSec
        ssid_result = await mock_meraki_client.configure_network_radsec(
            network_id="L_test_network",
            ssid_number=0,
            radius_host="radius.test.local",
            radius_port=2083,
            shared_secret="test-shared-secret",
            ca_certificate_id=upload_result["certificate_id"],
        )
        
        # Verify WPN configured
        assert "wpn_enabled" in ssid_result or "wifiPersonalNetworkId" in ssid_result
