"""Authenticated bridge from the add-on to Meraki HA's existing SDK session."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.hassio.const import DATA_HASSIO_SUPERVISOR_USER
from homeassistant.core import callback

from .meraki_ipsk import MerakiIpsk

_LOGGER = logging.getLogger(__name__)
PREFIX = "step_ca_scep/ipsk/"
COMMANDS = ("options", "list", "create", "get", "reveal_passphrase", "revoke", "delete",
            "configuration_plan", "configure", "access_manager", "client_key_plan", "assign_client_key")


def command_schema(command):
    """Declare the fields actually sent by the portal for each operation."""
    schema = {"type": PREFIX + command}
    if command == "options":
        schema[vol.Optional("network_id")] = str
    elif command == "list":
        schema[vol.Optional("scopes")] = [{vol.Required("network_id"): str,
                                          vol.Required("ssid_number"): int}]
    elif command == "create":
        schema.update({vol.Required("network_id"): str, vol.Required("ssid_number"): int,
                       vol.Required("name"): str, vol.Optional("group_policy_id"): str,
                       vol.Optional("duration_hours"): int, vol.Optional("passphrase"): str,
                       vol.Optional("associated_user"): str, vol.Optional("associated_unit"): str})
    elif command == "access_manager":
        schema[vol.Required("network_id")] = str
    elif command in ("configuration_plan", "configure"):
        schema.update({vol.Required("network_id"): str, vol.Required("ssid_number"): int,
                       vol.Required("portal_type"): str, vol.Optional("portal_url"): str,
                       vol.Optional("auth_mode"): str, vol.Optional("prepare_wpn"): bool,
                       vol.Optional("vlan_id"): vol.Any(int, None),
                       vol.Optional("walled_garden_ranges"): [str]})
        if command == "configure":
            schema[vol.Required("expected_revision")] = str
    elif command in ("client_key_plan", "assign_client_key"):
        schema.update({vol.Required("network_id"): str, vol.Required("ssid_number"): int,
                       vol.Required("mac"): str, vol.Required("owner"): str,
                       vol.Required("passphrase"): str, vol.Required("group_id"): str})
        if command == "assign_client_key":
            schema[vol.Required("expected_revision")] = str
    else:
        schema.update({vol.Required("ipsk_id"): str, vol.Optional("network_id"): str,
                       vol.Optional("ssid_number"): int})
    return schema


async def dispatch(hass, connection, msg):
    user = connection.user
    supervisor = hass.data.get(DATA_HASSIO_SUPERVISOR_USER)
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
                result["provider"] = "meraki_ha"
            elif action == "list":
                result = await service.list(msg.get("scopes", []))
            elif action == "create":
                result = await service.create(msg)
            elif action == "access_manager":
                result = await service.access_manager(msg["network_id"])
            elif action in ("configuration_plan", "configure", "client_key_plan", "assign_client_key"):
                result = await getattr(service, action)(msg)
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
        # HA's type-only optimization rejects every additional request field.
        # Declare operation fields here; the service validates scope and values.
        handler = websocket_api.websocket_command(command_schema(command))(
            websocket_api.async_response(dispatch))
        websocket_api.async_register_command(hass, handler)
    hass.data[marker] = True
