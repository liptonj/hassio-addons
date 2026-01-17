"""Mock Meraki Dashboard client for testing.

This provides a complete mock implementation of MerakiDashboardClient
that can be used in tests without requiring real Meraki API access.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class MockMerakiDashboardClient:
    """Mock Meraki Dashboard client for testing without API access."""

    def __init__(self, api_key: str = "test-api-key"):
        """Initialize the mock client.
        
        Args:
            api_key: Mock API key (not used, but kept for compatibility)
        """
        self.api_key = api_key
        self._connected = False
        self._ipsks: dict[str, dict] = {}
        self._organizations = [
            {"id": "123456", "name": "Test Organization"}
        ]
        self._networks = [
            {
                "id": "L_test_network",
                "name": "Test Network",
                "organizationId": "123456",
                "productTypes": ["wireless"],
            }
        ]
        self._ssids = [
            {
                "number": 0,
                "name": "Test-WiFi",
                "enabled": True,
                "authMode": "ipsk-without-radius",
                "wifiPersonalNetworkEnabled": True,
            },
            {
                "number": 1,
                "name": "Guest-WiFi",
                "enabled": True,
                "authMode": "psk",
            }
        ]
        self._group_policies = [
            {"id": "gp_default", "name": "Default Policy"},
            {"id": "gp_limited", "name": "Limited Access"},
        ]
        logger.info("MockMerakiDashboardClient initialized")

    async def connect(self) -> None:
        """Simulate connection."""
        self._connected = True
        logger.info("Mock Meraki client: Connected")

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("Mock Meraki client: Disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    # =========================================================================
    # Organization & Network
    # =========================================================================

    async def get_organizations(self) -> list[dict]:
        """Get mock organizations."""
        return self._organizations.copy()

    async def get_networks(self, organization_id: str) -> list[dict]:
        """Get mock networks."""
        return [
            n for n in self._networks
            if n.get("organizationId") == organization_id
        ]

    async def get_network(self, network_id: str) -> dict:
        """Get mock network details."""
        for network in self._networks:
            if network["id"] == network_id:
                return network.copy()
        return {
            "id": network_id,
            "name": "Unknown Network",
            "organizationId": "123456",
        }

    async def get_network_devices(self, network_id: str) -> list[dict]:
        """Get mock network devices."""
        return [
            {
                "serial": "Q2XX-XXXX-XXXX",
                "name": "Test AP",
                "model": "MR46",
                "lanIp": "192.168.1.10",
                "mac": "00:11:22:33:44:55",
                "networkId": network_id,
            }
        ]

    # =========================================================================
    # SSID Management
    # =========================================================================

    async def get_ssids(self, network_id: str) -> list[dict]:
        """Get mock SSIDs."""
        return self._ssids.copy()

    async def get_ssid(self, network_id: str, ssid_number: int) -> dict:
        """Get mock SSID details."""
        for ssid in self._ssids:
            if ssid["number"] == ssid_number:
                return ssid.copy()
        return {
            "number": ssid_number,
            "name": f"SSID-{ssid_number}",
            "enabled": False,
            "authMode": "psk",
        }

    async def get_ssid_wpn_status(self, network_id: str, ssid_number: int) -> dict:
        """Get mock SSID WPN status."""
        ssid = await self.get_ssid(network_id, ssid_number)
        is_enabled = ssid.get("enabled", False)
        auth_mode = ssid.get("authMode", "")
        wpn_enabled = ssid.get("wifiPersonalNetworkEnabled", False)
        is_ipsk = auth_mode == "ipsk-without-radius"
        
        return {
            "name": ssid.get("name", f"SSID-{ssid_number}"),
            "number": ssid_number,
            "enabled": is_enabled,
            "auth_mode": auth_mode,
            "is_ipsk_configured": is_ipsk,
            "wpn_enabled": wpn_enabled,
            "configuration_complete": is_enabled and is_ipsk,
            "ready_for_wpn": is_enabled and is_ipsk and wpn_enabled,
            "issues": [],
            "warnings": [],
            "raw_config": ssid,
        }

    async def configure_ssid_for_wpn(
        self,
        network_id: str,
        ssid_number: int,
        ssid_name: str | None = None,
        group_policy_name: str = "WPN-Users",
        splash_url: str | None = None,
    ) -> dict:
        """Mock SSID configuration for WPN."""
        # Update mock SSID
        for ssid in self._ssids:
            if ssid["number"] == ssid_number:
                ssid["name"] = ssid_name or ssid["name"]
                ssid["enabled"] = True
                ssid["authMode"] = "ipsk-without-radius"
                break
        
        return {
            "network_id": network_id,
            "ssid_number": ssid_number,
            "ssid_name": ssid_name or f"SSID-{ssid_number}",
            "configured": True,
        }

    # =========================================================================
    # IPSK Management
    # =========================================================================

    async def list_ipsks(
        self,
        network_id: str | None = None,
        ssid_number: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List mock IPSKs."""
        ipsks = list(self._ipsks.values())
        
        if network_id:
            ipsks = [i for i in ipsks if i.get("network_id") == network_id]
        if ssid_number is not None:
            ipsks = [i for i in ipsks if i.get("ssid_number") == ssid_number]
        if status:
            ipsks = [i for i in ipsks if i.get("status") == status]
        
        return ipsks

    async def create_ipsk(
        self,
        name: str,
        network_id: str,
        ssid_number: int,
        passphrase: str | None = None,
        duration_hours: int | None = None,
        group_policy_id: str | None = None,
        associated_device_id: str | None = None,
        associated_area_id: str | None = None,
        associated_user: str | None = None,
        associated_unit: str | None = None,
    ) -> dict:
        """Create a mock IPSK."""
        ipsk_id = f"ipsk_{uuid.uuid4().hex[:12]}"
        
        if not passphrase:
            passphrase = "TestPass123"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now(timezone.utc).replace(
                microsecond=0
            ).isoformat()
        
        ipsk = {
            "id": ipsk_id,
            "name": name,
            "network_id": network_id,
            "ssid_number": ssid_number,
            "ssid_name": self._ssids[0]["name"] if self._ssids else "Test-WiFi",
            "passphrase": passphrase,
            "status": "active",
            "group_policy_id": group_policy_id,
            "associated_device_id": associated_device_id,
            "associated_area_id": associated_area_id,
            "associated_user": associated_user,
            "associated_unit": associated_unit,
            "connected_clients": 0,
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "expires_at": expires_at,
        }
        
        self._ipsks[ipsk_id] = ipsk
        logger.info(f"Mock IPSK created: {name} (ID: {ipsk_id})")
        
        return ipsk

    async def get_ipsk(
        self,
        ipsk_id: str,
        include_passphrase: bool = False,
    ) -> dict:
        """Get mock IPSK details."""
        ipsk = self._ipsks.get(ipsk_id)
        if not ipsk:
            return {
                "id": ipsk_id,
                "name": "Unknown IPSK",
                "status": "active",
                "connected_clients": 0,
            }
        
        result = ipsk.copy()
        if not include_passphrase:
            result.pop("passphrase", None)
        
        return result

    async def update_ipsk(
        self,
        ipsk_id: str,
        name: str | None = None,
        group_policy_id: str | None = None,
        associated_device_id: str | None = None,
        associated_area_id: str | None = None,
    ) -> dict:
        """Update a mock IPSK."""
        ipsk = self._ipsks.get(ipsk_id)
        if not ipsk:
            raise ValueError(f"IPSK {ipsk_id} not found")
        
        if name:
            ipsk["name"] = name
        if group_policy_id:
            ipsk["group_policy_id"] = group_policy_id
        if associated_device_id:
            ipsk["associated_device_id"] = associated_device_id
        if associated_area_id:
            ipsk["associated_area_id"] = associated_area_id
        
        logger.info(f"Mock IPSK updated: {ipsk_id}")
        return ipsk.copy()

    async def revoke_ipsk(self, ipsk_id: str) -> None:
        """Revoke a mock IPSK."""
        if ipsk_id in self._ipsks:
            self._ipsks[ipsk_id]["status"] = "revoked"
            logger.info(f"Mock IPSK revoked: {ipsk_id}")

    async def delete_ipsk(self, ipsk_id: str) -> None:
        """Delete a mock IPSK."""
        if ipsk_id in self._ipsks:
            del self._ipsks[ipsk_id]
            logger.info(f"Mock IPSK deleted: {ipsk_id}")

    async def reveal_passphrase(self, ipsk_id: str) -> str:
        """Reveal mock passphrase."""
        ipsk = self._ipsks.get(ipsk_id)
        if ipsk:
            return ipsk.get("passphrase", "TestPass123")
        return "TestPass123"

    async def get_ipsk_options(self) -> dict:
        """Get available options for IPSK creation."""
        return {
            "networks": self._networks.copy(),
            "ssids": self._ssids.copy(),
            "group_policies": self._group_policies.copy(),
        }

    # =========================================================================
    # Group Policies
    # =========================================================================

    async def get_group_policies(self, network_id: str) -> list[dict]:
        """Get mock group policies."""
        return self._group_policies.copy()

    # =========================================================================
    # RadSec & Certificates (mock implementations)
    # =========================================================================

    async def upload_radsec_ca_certificate(
        self,
        network_id: str,
        certificate: str,
    ) -> dict:
        """Mock certificate upload."""
        return {
            "certificate_id": f"cert_{uuid.uuid4().hex[:8]}",
            "contents": certificate,
        }

    async def get_radsec_device_certificate_authorities(
        self,
        network_id: str,
    ) -> list[dict]:
        """Get mock certificate authorities."""
        return [
            {
                "id": "ca_123",
                "certificate_authority_id": "ca_123",
                "contents": "-----BEGIN CERTIFICATE-----\nMOCK CERT\n-----END CERTIFICATE-----",
                "status": "trusted",
                "ready": True,
            }
        ]

    async def get_radsec_device_certificate_authority(
        self,
        network_id: str,
        certificate_authority_id: str,
    ) -> dict:
        """Get mock certificate authority."""
        return {
            "id": certificate_authority_id,
            "certificate_authority_id": certificate_authority_id,
            "contents": "-----BEGIN CERTIFICATE-----\nMOCK CERT\n-----END CERTIFICATE-----",
            "status": "trusted",
            "ready": True,
        }

    async def create_radsec_device_certificate_authority(
        self,
        network_id: str,
        certificate: str,
    ) -> dict:
        """Mock certificate authority creation."""
        return {
            "certificate_authority_id": f"ca_{uuid.uuid4().hex[:8]}",
            "contents": certificate,
            "status": "pending",
            "ready": False,
        }

    async def trust_radsec_device_certificate_authority(
        self,
        network_id: str,
        certificate_authority_id: str,
    ) -> dict:
        """Mock certificate authority trust."""
        return {
            "id": certificate_authority_id,
            "status": "trusted",
            "contents": "-----BEGIN CERTIFICATE-----\nMOCK CERT\n-----END CERTIFICATE-----",
        }

    async def configure_network_radsec(
        self,
        network_id: str,
        ssid_number: int,
        radius_server_host: str,
        radius_server_port: int = 2083,
        ca_certificate_id: str | None = None,
    ) -> dict:
        """Mock RadSec configuration."""
        return {
            "ssid_number": ssid_number,
            "authMode": "8021x-radius",
            "radiusServers": [{"host": radius_server_host, "port": radius_server_port}],
            "wpn_enabled": True,
            "wifiPersonalNetworkId": f"wpn_{uuid.uuid4().hex[:8]}",
        }

    # =========================================================================
    # Splash Page
    # =========================================================================

    async def configure_splash_page(
        self,
        network_id: str,
        ssid_number: int,
        splash_url: str,
        splash_timeout: int = 1440,
    ) -> dict:
        """Mock splash page configuration."""
        return {
            "splashUrl": splash_url,
            "useSplashUrl": True,
            "splashTimeout": splash_timeout,
        }

    async def get_splash_settings(
        self,
        network_id: str,
        ssid_number: int,
    ) -> dict:
        """Get mock splash settings."""
        return {
            "splashUrl": "https://portal.local/register",
            "useSplashUrl": True,
            "splashTimeout": 1440,
        }
