"""Import/register the real companion with an installed Home Assistant package.

Run with Python 3.14 and Home Assistant 2026.9.4 installed. No HA modules are
stubbed and no deployed system or provider credentials are accessed.
"""
import asyncio
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hassio.const import DATA_HASSIO_SUPERVISOR_USER
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant


async def main():
    source = Path(__file__).resolve().parents[1] / 'custom_components/step_ca_scep'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        package = root / 'custom_components'
        package.mkdir()
        (package / '__init__.py').write_text('')
        shutil.copytree(source, package / 'step_ca_scep')
        sys.path.insert(0, str(root))
        integration = importlib.import_module('custom_components.step_ca_scep')
        flow = importlib.import_module('custom_components.step_ca_scep.config_flow')
        bridge = importlib.import_module('custom_components.step_ca_scep.ipsk_websocket')
        assert integration.DOMAIN == 'step_ca_scep'
        assert flow is not None
        hass = HomeAssistant(str(root))
        bridge.async_register(hass)
        bridge.async_register(hass)
        handlers = hass.data['websocket_api']
        assert len(handlers) == len(bridge.COMMANDS)
        connection = MagicMock()
        connection.user = SimpleNamespace(id='fixture-supervisor', name='Fixture', is_admin=False)
        hass.data[DATA_HASSIO_SUPERVISOR_USER] = SimpleNamespace(id='fixture-supervisor')
        hass.data['meraki_ha'] = {'entry': {'client': SimpleNamespace(dashboard=object())}}
        service = MagicMock()
        service.options = AsyncMock(return_value={'networks': []})
        service.list = AsyncMock(return_value=[])
        service.create = AsyncMock(return_value={})
        service.key = AsyncMock(return_value={})
        for name in ('configuration_plan', 'configure', 'access_manager', 'client_key_plan', 'assign_client_key'):
            setattr(service, name, AsyncMock(return_value={}))
        with patch.object(bridge, 'MerakiIpsk', return_value=service):
            outbound = []
            def send_message(message):
                outbound.append(message if isinstance(message, dict) else json.loads(message))
            actual = ActiveConnection(MagicMock(), hass, send_message,
                                      connection.user, None, None)
            # Reproduce the exact reported failure through HA's request path.
            command = bridge.PREFIX + 'options'
            original = handlers[command]
            handlers[command] = (original[0], False)
            actual.async_handle({'id': 1, 'type': command, 'network_id': ''})
            assert not outbound[-1]['success']
            service.options.assert_not_awaited()
            handlers[command] = original
            payloads = {
                'options': {'network_id': ''},
                'list': {'scopes': [{'network_id': 'N_fixture', 'ssid_number': 0}]},
                'create': {'network_id': 'N_fixture', 'ssid_number': 0, 'name': 'TV',
                           'group_policy_id': 'fixture-policy', 'duration_hours': 1,
                           'passphrase': 'fixture-password', 'associated_user': 'Resident',
                           'associated_unit': 'Unit 1'},
            }
            ssid_fields = {'network_id': 'N_fixture', 'ssid_number': 0, 'portal_type': 'none',
                           'portal_url': '', 'auth_mode': '8021x-nac',
                           'prepare_wpn': False, 'vlan_id': None, 'walled_garden_ranges': []}
            client_fields = {'network_id': 'N_fixture', 'ssid_number': 0, 'mac': '00:11:22:33:44:55',
                             'owner': 'Alice', 'group_id': '10', 'passphrase': 'fixture-password'}
            payloads.update(configuration_plan=ssid_fields, configure={**ssid_fields, 'expected_revision': 'r1'},
                            access_manager={'network_id': 'N_fixture'}, client_key_plan=client_fields,
                            assign_client_key={**client_fields, 'expected_revision': 'r1'})
            for ident, action in enumerate(bridge.COMMANDS, 2):
                fields = payloads.get(action, {'ipsk_id': 'N_fixture:0:key',
                                               'network_id': 'N_fixture', 'ssid_number': 0})
                actual.async_handle({'id': ident, 'type': bridge.PREFIX + action, **fields})
                await asyncio.sleep(0)
                result = outbound[-1]
                assert result['id'] == ident and result['success'], result
            service.options.assert_awaited_once_with('')
            service.list.assert_awaited_once_with(payloads['list']['scopes'])
            service.create.assert_awaited_once()
            assert service.key.await_count == 4
            actual.async_handle({'id': 20, 'type': bridge.PREFIX + 'options',
                                 'network_id': '', 'unexpected': True})
            assert not outbound[-1]['success']
            service.options.reset_mock()
            await bridge.dispatch(hass, connection, {'id': 1, 'type': bridge.PREFIX + 'options'})
            connection.send_result.assert_called_once()
            connection.user.id = 'fixture-resident'
            await bridge.dispatch(hass, connection, {'id': 2, 'type': bridge.PREFIX + 'options'})
            connection.send_error.assert_called_once_with(2, 'unauthorized', 'Administrator access is required.')
            service.options.assert_awaited_once()
        print(json.dumps({'status': 'passed', 'homeassistant': __version__,
              'checks': ['real companion and config flow imports', 'original options request failure reproduced',
                         'all twelve commands dispatched through real ActiveConnection with full portal payloads',
                         'unknown request fields rejected before dispatch',
                         'idempotent registration', 'real Supervisor data key authorization', 'ordinary resident denied']}))


if __name__ == '__main__':
    asyncio.run(main())
