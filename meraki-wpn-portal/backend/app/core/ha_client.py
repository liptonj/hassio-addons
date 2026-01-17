"""Home Assistant WebSocket API client for IPSK management."""

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class HomeAssistantClientError(Exception):
    """Exception raised for Home Assistant client errors."""


class HomeAssistantClient:
    """Client for Home Assistant WebSocket API."""

    def __init__(self, url: str, token: str):
        """Initialize the Home Assistant client.

        Args:
            url: Home Assistant URL (e.g., http://homeassistant.local:8123)
            token: Long-lived access token or supervisor token
        """
        self.url = url.rstrip("/")
        self.ws_url = f"{self.url.replace('http', 'ws')}/api/websocket"
        self.token = token
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._msg_id = 0
        self._connected = False
        self._pending_responses: dict[int, asyncio.Future] = {}
        self._receive_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Connect to Home Assistant WebSocket API."""
        if self._connected:
            logger.debug("Already connected to Home Assistant")
            return

        logger.info(f"Connecting to Home Assistant at {self.ws_url}")

        self._session = aiohttp.ClientSession()

        try:
            self._ws = await self._session.ws_connect(
                self.ws_url,
                heartbeat=30,
            )

            # Wait for auth required message
            msg = await self._ws.receive_json()
            if msg.get("type") != "auth_required":
                raise HomeAssistantClientError(f"Unexpected message: {msg}")

            # Send authentication
            await self._ws.send_json({
                "type": "auth",
                "access_token": self.token,
            })

            # Wait for auth response
            msg = await self._ws.receive_json()
            if msg.get("type") != "auth_ok":
                raise HomeAssistantClientError(
                    f"Authentication failed: {msg.get('message', 'Unknown error')}"
                )

            self._connected = True
            logger.info("Successfully authenticated with Home Assistant")

            # Start background receiver
            self._receive_task = asyncio.create_task(self._receive_loop())

        except ConnectionError as e:
            logger.error(f"Connection error to Home Assistant: {e}")
            await self.disconnect()
            raise ConnectionError(f"Failed to connect to HA: {e}") from e
        except TimeoutError as e:
            logger.error(f"Timeout connecting to Home Assistant: {e}")
            await self.disconnect()
            raise TimeoutError(f"HA connection timeout: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error connecting to Home Assistant: {e}")
            await self.disconnect()
            raise HomeAssistantClientError(f"Connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Home Assistant."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("Disconnected from Home Assistant")

    async def _receive_loop(self) -> None:
        """Background task to receive messages."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    msg_id = data.get("id")
                    if msg_id and msg_id in self._pending_responses:
                        self._pending_responses[msg_id].set_result(data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket closed")
                    break
        except asyncio.CancelledError:
            pass
        except ConnectionError as e:
            logger.error(f"Connection lost in receive loop: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in receive loop: {e}")

        self._connected = False

    async def _send_command(
        self,
        command: dict[str, Any],
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send a command and wait for response.

        Args:
            command: Command dictionary to send
            timeout: Timeout in seconds

        Returns:
            Response dictionary from Home Assistant
        """
        if not self._connected or not self._ws:
            await self.connect()

        if not self._ws:
            raise HomeAssistantClientError("Not connected to Home Assistant")

        self._msg_id += 1
        msg_id = self._msg_id

        command["id"] = msg_id

        # Create future for response
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_responses[msg_id] = future

        try:
            await self._ws.send_json(command)
            result = await asyncio.wait_for(future, timeout=timeout)

            if not result.get("success", True):
                error = result.get("error", {})
                raise HomeAssistantClientError(
                    f"Command failed: {error.get('message', 'Unknown error')}"
                )

            return result.get("result", result)

        except asyncio.TimeoutError as e:
            raise HomeAssistantClientError(
                f"Command timed out after {timeout}s"
            ) from e
        finally:
            self._pending_responses.pop(msg_id, None)

    # =========================================================================
    # IPSK Management (calls meraki_ha integration)
    # =========================================================================

    async def list_ipsks(
        self,
        network_id: str | None = None,
        ssid_number: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List all IPSKs.

        Args:
            network_id: Optional filter by network ID
            ssid_number: Optional filter by SSID number
            status: Optional filter by status (active, expired, revoked)

        Returns:
            List of IPSK dictionaries
        """
        command = {"type": "meraki_ha/ipsk/list"}
        if network_id:
            command["network_id"] = network_id
        if ssid_number is not None:
            command["ssid_number"] = ssid_number
        if status:
            command["status"] = status

        return await self._send_command(command)

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
        """Create a new IPSK.

        Args:
            name: Name for the IPSK
            network_id: Meraki network ID
            ssid_number: SSID number (0-14)
            passphrase: Optional custom passphrase (auto-generated if not provided)
            duration_hours: Optional duration in hours (0 = permanent)
            group_policy_id: Optional group policy ID
            associated_device_id: Optional HA device ID to associate
            associated_area_id: Optional HA area ID to associate
            associated_user: Optional user name to associate
            associated_unit: Optional unit/room identifier

        Returns:
            Created IPSK dictionary with passphrase
        """
        command = {
            "type": "meraki_ha/ipsk/create",
            "name": name,
            "network_id": network_id,
            "ssid_number": ssid_number,
        }

        if passphrase:
            command["passphrase"] = passphrase
        if duration_hours is not None:
            command["duration_hours"] = duration_hours
        if group_policy_id:
            command["group_policy_id"] = group_policy_id
        if associated_device_id:
            command["associated_device_id"] = associated_device_id
        if associated_area_id:
            command["associated_area_id"] = associated_area_id
        if associated_user:
            command["associated_user"] = associated_user
        if associated_unit:
            command["associated_unit"] = associated_unit

        return await self._send_command(command)

    async def get_ipsk(
        self,
        ipsk_id: str,
        include_passphrase: bool = False,
    ) -> dict:
        """Get IPSK details.

        Args:
            ipsk_id: IPSK identifier
            include_passphrase: Whether to include the passphrase in response

        Returns:
            IPSK dictionary
        """
        return await self._send_command({
            "type": "meraki_ha/ipsk/get",
            "ipsk_id": ipsk_id,
            "include_passphrase": include_passphrase,
        })

    async def update_ipsk(
        self,
        ipsk_id: str,
        name: str | None = None,
        group_policy_id: str | None = None,
        associated_device_id: str | None = None,
        associated_area_id: str | None = None,
    ) -> dict:
        """Update an existing IPSK.

        Args:
            ipsk_id: IPSK identifier
            name: Optional new name
            group_policy_id: Optional new group policy ID
            associated_device_id: Optional new HA device ID
            associated_area_id: Optional new HA area ID

        Returns:
            Updated IPSK dictionary
        """
        command = {
            "type": "meraki_ha/ipsk/update",
            "ipsk_id": ipsk_id,
        }

        if name:
            command["name"] = name
        if group_policy_id:
            command["group_policy_id"] = group_policy_id
        if associated_device_id:
            command["associated_device_id"] = associated_device_id
        if associated_area_id:
            command["associated_area_id"] = associated_area_id

        return await self._send_command(command)

    async def revoke_ipsk(self, ipsk_id: str) -> None:
        """Revoke an IPSK (mark as inactive).

        Args:
            ipsk_id: IPSK identifier
        """
        await self._send_command({
            "type": "meraki_ha/ipsk/revoke",
            "ipsk_id": ipsk_id,
        })

    async def delete_ipsk(self, ipsk_id: str) -> None:
        """Delete an IPSK.

        Args:
            ipsk_id: IPSK identifier
        """
        await self._send_command({
            "type": "meraki_ha/ipsk/delete",
            "ipsk_id": ipsk_id,
        })

    async def reveal_passphrase(self, ipsk_id: str) -> str:
        """Reveal the passphrase for an IPSK.

        Args:
            ipsk_id: IPSK identifier

        Returns:
            The IPSK passphrase
        """
        result = await self._send_command({
            "type": "meraki_ha/ipsk/reveal_passphrase",
            "ipsk_id": ipsk_id,
        })
        return result.get("passphrase", "")

    async def get_ipsk_options(self) -> dict:
        """Get available networks, SSIDs, group policies, and areas.

        Returns:
            Dictionary with available options for IPSK creation
        """
        return await self._send_command({
            "type": "meraki_ha/ipsk/options",
        })

    # =========================================================================
    # Home Assistant Data
    # =========================================================================

    async def get_devices(self) -> list[dict]:
        """Get all Home Assistant devices.

        Returns:
            List of device dictionaries
        """
        return await self._send_command({
            "type": "config/device_registry/list",
        })

    async def get_areas(self) -> list[dict]:
        """Get all Home Assistant areas.

        Returns:
            List of area dictionaries
        """
        return await self._send_command({
            "type": "config/area_registry/list",
        })

    async def get_entities(self) -> list[dict]:
        """Get all Home Assistant entities.

        Returns:
            List of entity dictionaries
        """
        return await self._send_command({
            "type": "config/entity_registry/list",
        })

    async def get_states(self) -> list[dict]:
        """Get all entity states.

        Returns:
            List of state dictionaries
        """
        return await self._send_command({
            "type": "get_states",
        })

    @property
    def is_connected(self) -> bool:
        """Check if connected to Home Assistant."""
        return self._connected
