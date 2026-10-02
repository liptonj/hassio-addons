"""Authenticated bridge from the add-on to Meraki HA's existing SDK session."""
import asyncio
import logging

from homeassistant.components import websocket_api
from homeassistant.components.http.const import DATA_SUPERVISOR_USER
from homeassistant.core import callback

from .meraki_ipsk import MerakiIpsk

_LOGGER = logging.getLogger(__name__)
PREFIX = "step_ca_scep/ipsk/"
COMMANDS = ("options", "list", "create", "get", "reveal_passphrase", "revoke", "delete")


async def dispatch(hass, connection, msg):
    user = connection.user
    supervisor = hass.data.get(DATA_SUPERVISOR_USER)
    if user is None or not (user.is_admin or supervisor is not None and user.id == supervisor.id):
        connection.send_error(msg["id"], "unauthorized", "Administrator access is required.")
        return
    clients = []
    for entry in hass.data.get("meraki_ha", {}).values():
        if isinstance(entry, dict) and (client := entry.get("client")) is not None and client.dashboard is not None:
            clients.append(client)
    if not clients:
        connection.send_error(msg["id"], "provider_unavailable", "Set up Meraki HA in Home Assistant before managing Wi-Fi keys.")
        return
    service = MerakiIpsk(clients)
    action = msg["type"].removeprefix(PREFIX)
    try:
        async with asyncio.timeout(45):
            if action == "options":
                result = await service.options(msg.get("network_id", ""))
            elif action == "list":
                result = await service.list(msg.get("scopes", []))
            elif action == "create":
                result = await service.create(msg)
            else:
                result = await service.key(action, msg.get("ipsk_id"), msg.get("network_id", ""), msg.get("ssid_number", 0))
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_request", str(err))
    except TimeoutError:
        connection.send_error(msg["id"], "provider_timeout", "Meraki did not respond in time. Check Dashboard before retrying key creation.")
    except Exception:
        # SDK exceptions can include request bodies or credentials. Do not send
        # them to the browser or persist them in the Home Assistant log.
        _LOGGER.warning("Meraki iPSK %s failed", action)
        connection.send_error(msg["id"], "provider_error", "Meraki rejected the Wi-Fi request. Check the network, group policy and API permissions.")


@callback
def async_register(hass):
    marker = "step_ca_scep_ipsk_registered"
    if hass.data.get(marker):
        return
    for command in COMMANDS:
        # A type-only schema also works across HA's schema-library versions.
        # All operation fields are checked by the stateless service.
        handler = websocket_api.websocket_command({"type": PREFIX + command})(
            websocket_api.async_response(dispatch))
        websocket_api.async_register_command(hass, handler)
    hass.data[marker] = True
