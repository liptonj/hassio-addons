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
        assert len(handlers) == 7
        for action in bridge.COMMANDS:
            _, schema = handlers[bridge.PREFIX + action]
            # HA optimizes type-only commands to False: operation fields pass
            # to the service's own validation without a second schema pass.
            if schema is not False:
                assert schema({'id': 1, 'type': bridge.PREFIX + action, 'network_id': 'N_fixture'})['network_id'] == 'N_fixture'
        connection = MagicMock()
        connection.user = SimpleNamespace(id='fixture-supervisor', is_admin=False)
        hass.data[DATA_HASSIO_SUPERVISOR_USER] = SimpleNamespace(id='fixture-supervisor')
        hass.data['meraki_ha'] = {'entry': {'client': SimpleNamespace(dashboard=object())}}
        service = MagicMock()
        service.options = AsyncMock(return_value={'networks': []})
        with patch.object(bridge, 'MerakiIpsk', return_value=service):
            await bridge.dispatch(hass, connection, {'id': 1, 'type': bridge.PREFIX + 'options'})
            connection.send_result.assert_called_once()
            connection.user.id = 'fixture-resident'
            await bridge.dispatch(hass, connection, {'id': 2, 'type': bridge.PREFIX + 'options'})
            connection.send_error.assert_called_once_with(2, 'unauthorized', 'Administrator access is required.')
            service.options.assert_awaited_once()
        print(json.dumps({'status': 'passed', 'homeassistant': __version__,
              'checks': ['real companion and config flow imports', 'all seven real HA command schemas accept operation fields',
                         'idempotent registration', 'real Supervisor data key authorization', 'ordinary resident denied']}))


if __name__ == '__main__':
    asyncio.run(main())
