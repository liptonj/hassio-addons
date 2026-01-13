"""Mock Home Assistant client for standalone mode testing."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.core.security import generate_passphrase

logger = logging.getLogger(__name__)


class MockHomeAssistantClient:
    """Mock client for standalone mode that simulates HA/Meraki IPSK operations."""

    def __init__(self):
        """Initialize the mock client."""
        self._connected = True
        self._ipsks: dict[str, dict] = {}
        self._areas = [
            {"area_id": "unit_101", "name": "Unit 101"},
            {"area_id": "unit_102", "name": "Unit 102"},
            {"area_id": "unit_201", "name": "Unit 201"},
            {"area_id": "unit_202", "name": "Unit 202"},
            {"area_id": "unit_301", "name": "Unit 301"},
            {"area_id": "unit_302", "name": "Unit 302"},
        ]
        self._devices = [
            {"id": "dev_1", "name": "Living Room TV", "manufacturer": "Samsung", "area_id": "unit_101"},
            {"id": "dev_2", "name": "Smart Thermostat", "manufacturer": "Ecobee", "area_id": "unit_102"},
        ]
        logger.info("MockHomeAssistantClient initialized (standalone mode)")

    async def connect(self) -> None:
        """Simulate connection to Home Assistant."""
        logger.info("Mock HA client: Connected (standalone mode)")
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        logger.info("Mock HA client: Disconnected")
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    # =========================================================================
    # IPSK Management (mock implementation)
    # =========================================================================

    async def list_ipsks(
        self,
        network_id: str | None = None,
        ssid_number: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List all mock IPSKs."""
        ipsks = list(self._ipsks.values())

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
        settings = get_settings()

        ipsk_id = f"ipsk_{uuid.uuid4().hex[:12]}"

        if not passphrase:
            passphrase = generate_passphrase(settings.passphrase_length)

        ipsk = {
            "id": ipsk_id,
            "name": name,
            "network_id": network_id or "L_mock_network",
            "ssid_number": ssid_number,
            "ssid_name": settings.standalone_ssid_name,
            "passphrase": passphrase,
            "status": "active",
            "group_policy_id": group_policy_id,
            "associated_device_id": associated_device_id,
            "associated_area_id": associated_area_id,
            "associated_user": associated_user,
            "associated_unit": associated_unit,
            "connected_clients": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
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
            # Return a default for testing
            settings = get_settings()
            return {
                "id": ipsk_id,
                "name": "Unknown IPSK",
                "ssid_name": settings.standalone_ssid_name,
                "passphrase": "DemoPass123" if include_passphrase else None,
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
            ipsk = {"id": ipsk_id, "status": "active"}
            self._ipsks[ipsk_id] = ipsk

        if name:
            ipsk["name"] = name
        if group_policy_id:
            ipsk["group_policy_id"] = group_policy_id
        if associated_device_id:
            ipsk["associated_device_id"] = associated_device_id
        if associated_area_id:
            ipsk["associated_area_id"] = associated_area_id

        logger.info(f"Mock IPSK updated: {ipsk_id}")
        return ipsk

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
            return ipsk.get("passphrase", "DemoPass123")
        return "DemoPass123"

    async def get_ipsk_options(self) -> dict:
        """Get available options for IPSK creation."""
        return {
            "networks": [
                {"id": "L_mock_network", "name": "Demo Network"},
            ],
            "ssids": [
                {"number": 0, "name": "Demo-WiFi"},
                {"number": 1, "name": "Guest-WiFi"},
            ],
            "group_policies": [
                {"id": "gp_default", "name": "Default Policy"},
                {"id": "gp_limited", "name": "Limited Access"},
            ],
        }

    # =========================================================================
    # Home Assistant Data (mock implementation)
    # =========================================================================

    async def get_devices(self) -> list[dict]:
        """Get mock devices."""
        return self._devices

    async def get_areas(self) -> list[dict]:
        """Get mock areas."""
        return self._areas

    async def get_entities(self) -> list[dict]:
        """Get mock entities."""
        return []

    async def get_states(self) -> list[dict]:
        """Get mock states."""
        return []
