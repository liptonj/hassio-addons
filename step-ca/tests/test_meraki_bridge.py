"""Check the stateless Meraki bridge and MariaDB attribution boundary."""
import asyncio
import datetime
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import ipsk

directory = Path(__file__).resolve().parents[1] / "custom_components/step_ca_scep"
spec = importlib.util.spec_from_file_location("stepca_meraki_service", directory / "meraki_ipsk.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def client():
    result = MagicMock()
    result.organization_id = "fixture-org"
    result.async_ensure_token_valid = AsyncMock()
    result.dashboard.organizations.getOrganizationNetworks = AsyncMock(return_value=[
        {"id": "N_fixture", "name": "Home", "productTypes": ["wireless"]},
        {"id": "N_other", "name": "Other", "productTypes": ["wireless"]},
        {"id": "N_switch", "name": "Switch", "productTypes": ["switch"]}])
    wireless = result.dashboard.wireless
    wireless.getNetworkWirelessSsids = AsyncMock(return_value=[
        {"number": 0, "name": "Resident Wi-Fi", "enabled": True, "authMode": "ipsk-without-radius"},
        {"number": 1, "name": "Radius", "enabled": True, "authMode": "ipsk-with-radius"},
        {"number": 2, "name": "Off", "enabled": False, "authMode": "ipsk-without-radius"}])
    wireless.getNetworkWirelessSsid = AsyncMock(return_value={
        "number": 0, "name": "Resident Wi-Fi", "enabled": True, "authMode": "ipsk-without-radius"})
    result.dashboard.networks.getNetworkGroupPolicies = AsyncMock(return_value=[
        {"groupPolicyId": "fixture-policy", "name": "Residents"}])
    key = {"id": "remote-key", "name": "TV", "groupPolicyId": "fixture-policy", "passphrase": " spaced-password "}
    wireless.createNetworkWirelessSsidIdentityPsk = AsyncMock(return_value=key)
    wireless.getNetworkWirelessSsidIdentityPsk = AsyncMock(return_value=key)
    wireless.getNetworkWirelessSsidIdentityPsks = AsyncMock(return_value=[key])
    wireless.updateNetworkWirelessSsidIdentityPsk = AsyncMock(return_value={})
    wireless.deleteNetworkWirelessSsidIdentityPsk = AsyncMock(return_value=None)
    return result


class MerakiServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = client()
        self.service = service.MerakiIpsk([self.client])
        self.message = {"network_id": "N_fixture", "ssid_number": 0, "name": "TV",
                        "group_policy_id": "fixture-policy", "duration_hours": 1,
                        "passphrase": " spaced-password "}

    async def test_options_only_include_wireless_networks_and_enabled_identity_ssids(self):
        result = await self.service.options("N_fixture")
        self.assertEqual(len(result["networks"]), 2)
        self.assertEqual(result["ssids"], [{"number": 0, "name": "Resident Wi-Fi", "network_id": "N_fixture"}])
        self.assertEqual(result["group_policies"][0]["network_id"], "N_fixture")
        self.client.async_ensure_token_valid.assert_awaited()

    async def test_network_selection_does_not_load_other_network_ssids(self):
        result = await self.service.options()
        self.assertEqual(result["ssids"], [])
        self.client.dashboard.wireless.getNetworkWirelessSsids.assert_not_awaited()

    async def test_create_preserves_password_and_returns_authoritative_ssid_and_scoped_id(self):
        result = await self.service.create(self.message)
        self.assertEqual(result["id"], "N_fixture:0:remote-key")
        self.assertEqual(result["ssid_name"], "Resident Wi-Fi")
        call = self.client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk.await_args
        self.assertEqual(call.args, ("N_fixture", 0))
        self.assertEqual(call.kwargs["groupPolicyId"], "fixture-policy")
        self.assertEqual(call.kwargs["passphrase"], " spaced-password ")
        expiry = datetime.datetime.fromisoformat(call.kwargs["expiresAt"])
        self.assertGreater(expiry, datetime.datetime.now(datetime.timezone.utc))

    async def test_zero_duration_and_blank_password_use_meraki_generation(self):
        await self.service.create({**self.message, "duration_hours": 0, "passphrase": ""})
        args = self.client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk.await_args.kwargs
        self.assertNotIn("expiresAt", args)
        self.assertNotIn("passphrase", args)

    async def test_invalid_inputs_never_create(self):
        for field, value in (("network_id", "../network"), ("ssid_number", True),
                             ("ssid_number", 15), ("name", ""), ("group_policy_id", ""),
                             ("group_policy_id", "policy-from-another-network"),
                             ("passphrase", "short"), ("duration_hours", -1)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                await self.service.create({**self.message, field: value})
        self.client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk.assert_not_awaited()

    async def test_wrong_auth_mode_never_creates(self):
        self.client.dashboard.wireless.getNetworkWirelessSsid.return_value["authMode"] = "psk"
        with self.assertRaisesRegex(ValueError, "Identity PSK"):
            await self.service.create(self.message)
        self.client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk.assert_not_awaited()

    async def test_duplicate_organization_connections_fail_closed(self):
        duplicate = client()
        with self.assertRaisesRegex(ValueError, "multiple"):
            await service.MerakiIpsk([self.client, duplicate]).options("N_fixture")

    async def test_list_strips_passphrases_and_reports_explicit_expiry(self):
        self.client.dashboard.wireless.getNetworkWirelessSsidIdentityPsks.return_value[0]["expiresAt"] = "2000-01-01T00:00:00Z"
        result = await self.service.list([{"network_id": "N_fixture", "ssid_number": 0}])
        self.assertNotIn("passphrase", result[0])
        self.assertEqual(result[0]["status"], "expired")

    async def test_compound_ids_route_to_their_own_network_not_default(self):
        await self.service.key("get", "N_other:0:remote-key", "N_fixture", 0)
        self.client.dashboard.wireless.getNetworkWirelessSsidIdentityPsk.assert_awaited_once_with("N_other", 0, "remote-key")

    async def test_revoke_expires_key_and_delete_removes_key(self):
        result = await self.service.key("revoke", "N_fixture:0:remote-key")
        self.assertEqual(result["status"], "revoked")
        expiry = self.client.dashboard.wireless.updateNetworkWirelessSsidIdentityPsk.await_args.kwargs["expiresAt"]
        self.assertLess(datetime.datetime.fromisoformat(expiry), datetime.datetime.now(datetime.timezone.utc))
        await self.service.key("delete", "remote-key", "N_fixture", 0)
        self.client.dashboard.wireless.deleteNetworkWirelessSsidIdentityPsk.assert_awaited_once_with("N_fixture", 0, "remote-key")

    async def test_expired_key_cannot_reveal_a_password(self):
        self.client.dashboard.wireless.getNetworkWirelessSsidIdentityPsk.return_value["expiresAt"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "active"):
            await self.service.key("reveal_passphrase", "N_fixture:0:remote-key")

    async def test_malformed_create_response_cleans_remote_key(self):
        self.client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk.return_value["expiresAt"] = "invalid"
        with self.assertRaises(ValueError):
            await self.service.create(self.message)
        self.client.dashboard.wireless.deleteNetworkWirelessSsidIdentityPsk.assert_awaited_once_with("N_fixture", 0, "remote-key")


class AttributionTests(unittest.TestCase):
    def test_key_creation_without_mariadb_fails_before_provisioning(self):
        with patch.dict(os.environ, {"PORTAL_DB_HOST": ""}), patch.object(ipsk, "core_call") as rpc:
            for fn in (ipsk.create_ipsk, ipsk.create_admin_ipsk):
                with self.assertRaisesRegex(RuntimeError, "MariaDB"):
                    fn("TV", "N_fixture", 0, 0)
        rpc.assert_not_called()

    def test_attribution_is_written_to_mariadb_without_password(self):
        conn, cursor = MagicMock(), MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        key = {"id": "N_fixture:0:key", "network_id": "N_fixture", "ssid_number": 0,
               "ssid_name": "Wi-Fi", "passphrase": "fixture-password"}
        with patch.object(ipsk, "db_connect", return_value=conn):
            ipsk._record_key(key, "Unit 1", "Resident")
        conn.commit.assert_called_once()
        self.assertEqual(cursor.execute.call_args.args[1], ("N_fixture:0:key", "N_fixture", 0, "Resident", "Unit 1"))
        self.assertNotIn("passphrase", cursor.execute.call_args.args[0])

    def test_failed_mariadb_write_removes_provisioned_key(self):
        key = {"id": "N_fixture:0:key", "network_id": "N_fixture", "ssid_number": 0,
               "ssid_name": "Wi-Fi", "passphrase": "fixture-password"}
        with patch.object(ipsk, "db_connect", side_effect=RuntimeError("database unavailable")), patch.object(ipsk, "core_call") as rpc:
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                ipsk._record_key(key, "", "")
        self.assertEqual(rpc.call_args.args[0]["type"], "step_ca_scep/ipsk/delete")

    def test_live_keys_merge_scopes_and_attribution_from_stepca_database(self):
        row = {"ipsk_id": "N_other:1:key", "network_id": "N_other", "ssid_number": 1,
               "associated_user": "Resident", "associated_unit": "Unit 1", "status": "revoked"}
        key = {"id": row["ipsk_id"], "status": "expired"}
        with patch.object(ipsk, "_key_records", return_value=[row]), patch.object(ipsk, "_default_scope", return_value={"network_id": "N_fixture", "ssid_number": 0}), patch.object(ipsk, "core_call", return_value=[[key]]) as rpc:
            result = ipsk.list_ipsks()
        self.assertEqual(len(rpc.call_args.args[0]["scopes"]), 2)
        self.assertEqual(result[0]["associated_user"], "Resident")
        self.assertEqual(result[0]["status"], "revoked")

    def test_shipping_sources_have_no_old_database_import(self):
        root = directory.parents[1]
        for name in ("admin/db_setup.py", "run.sh", "config.yaml", "Dockerfile"):
            text = (root / name).read_text().lower()
            self.assertNotIn("sqlite", text)
            self.assertNotIn("wpn_database_name", text)

    def test_docker_context_includes_each_explicit_copy_file(self):
        root = directory.parents[1]
        allow = set((root / ".dockerignore").read_text().splitlines())
        for line in (root / "Dockerfile").read_text().splitlines():
            if line.startswith("COPY "):
                for path in line.split()[1:-1]:
                    if (root / path).is_file():
                        self.assertIn("!" + path, allow)


class WebsocketPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        package_name = "stepca_bridge_fixture"
        package = types.ModuleType(package_name)
        package.__path__ = [str(directory)]
        api = types.ModuleType("homeassistant.components.websocket_api")
        api.async_register_command = MagicMock()
        def command(schema):
            def decorate(fn):
                fn._ws_command = schema["type"]
                return fn
            return decorate
        def response(fn):
            async def wrapped(*args):
                return await fn(*args)
            return wrapped
        api.websocket_command = command
        api.async_response = response
        components = types.ModuleType("homeassistant.components")
        components.websocket_api = api
        const = types.ModuleType("homeassistant.components.hassio.const")
        const.DATA_HASSIO_SUPERVISOR_USER = "fixture_supervisor_user"
        core = types.ModuleType("homeassistant.core")
        core.callback = lambda fn: fn
        modules = {package_name: package, package_name + ".meraki_ipsk": service,
                   "homeassistant": types.ModuleType("homeassistant"),
                   "homeassistant.components": components,
                   "homeassistant.components.websocket_api": api,
                   "homeassistant.components.hassio": types.ModuleType("homeassistant.components.hassio"),
                   "homeassistant.components.hassio.const": const, "homeassistant.core": core}
        spec = importlib.util.spec_from_file_location(package_name + ".ipsk_websocket", directory / "ipsk_websocket.py")
        self.bridge = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.bridge)
        self.api = api
        self.client = client()
        self.hass = types.SimpleNamespace(data={"meraki_ha": {"entry": {"client": self.client}}})
        self.connection = MagicMock()
        self.connection.user = types.SimpleNamespace(id="admin", is_admin=True)
        self.message = {"id": 1, "type": "step_ca_scep/ipsk/options", "network_id": "N_fixture"}

    async def test_ordinary_resident_cannot_read_or_change_keys(self):
        self.connection.user.is_admin = False
        await self.bridge.dispatch(self.hass, self.connection, self.message)
        self.assertEqual(self.connection.send_error.call_args.args[1], "unauthorized")
        self.client.async_ensure_token_valid.assert_not_awaited()

    async def test_authenticated_supervisor_service_user_can_call_bridge(self):
        self.connection.user.is_admin = False
        self.hass.data["fixture_supervisor_user"] = types.SimpleNamespace(id="admin")
        await self.bridge.dispatch(self.hass, self.connection, self.message)
        self.connection.send_result.assert_called_once()

    async def test_unavailable_meraki_is_actionable_and_never_fabricates_keys(self):
        self.hass.data = {}
        await self.bridge.dispatch(self.hass, self.connection, self.message)
        self.assertEqual(self.connection.send_error.call_args.args[1], "provider_unavailable")

    async def test_provider_exception_does_not_disclose_sdk_request_secrets(self):
        self.client.dashboard.organizations.getOrganizationNetworks.side_effect = RuntimeError("sensitive-sdk-token")
        await self.bridge.dispatch(self.hass, self.connection, self.message)
        self.assertEqual(self.connection.send_error.call_args.args[1], "provider_error")
        self.assertNotIn("sensitive", str(self.connection.send_error.call_args))

    async def test_all_handlers_register_once_under_stepca_namespace(self):
        self.bridge.async_register(self.hass)
        self.bridge.async_register(self.hass)
        calls = self.api.async_register_command.call_args_list
        self.assertEqual(len(calls), 7)
        self.assertEqual({c.args[1]._ws_command for c in calls},
                         {"step_ca_scep/ipsk/" + action for action in self.bridge.COMMANDS})


@unittest.skipUnless(importlib.util.find_spec("meraki"), "optional Meraki SDK contract check")
class RealSdkContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_operations_use_verified_wire_contract_on_loopback(self):
        import meraki.aio
        requests = []
        key = {"id": "remote-key", "name": "TV", "groupPolicyId": "fixture-policy", "passphrase": "fixture-password"}
        async def fixture(request):
            payload = await request.json() if request.method in ("POST", "PUT") else None
            requests.append((request.method, request.path, payload))
            if request.path.endswith("/organizations/fixture-org/networks"):
                return web.json_response([{"id": "N_fixture", "name": "Home", "productTypes": ["wireless"]}])
            if request.path.endswith("/groupPolicies"):
                return web.json_response([{"groupPolicyId": "fixture-policy", "name": "Residents"}])
            ssid = {"number": 0, "name": "Resident Wi-Fi", "enabled": True, "authMode": "ipsk-without-radius"}
            if request.path.endswith("/wireless/ssids"):
                return web.json_response([ssid])
            if request.path.endswith("/wireless/ssids/0"):
                return web.json_response(ssid)
            if request.method == "DELETE":
                return web.Response(status=204)
            if request.method in ("POST", "PUT"):
                key.update(payload)
            if request.path.endswith("/identityPsks") and request.method == "GET":
                return web.json_response([key])
            return web.json_response(key)
        server = web.Application()
        server.router.add_route("*", "/api/v1/{path:.*}", fixture)
        runner = web.AppRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with meraki.aio.AsyncDashboardAPI(api_key="fixture-key", base_url=f"http://127.0.0.1:{port}/api/v1",
                    output_log=False, print_console=False, suppress_logging=True,
                    maximum_retries=1, single_request_timeout=3) as dashboard:
                provider = types.SimpleNamespace(organization_id="fixture-org", dashboard=dashboard,
                                                 async_ensure_token_valid=AsyncMock())
                bridge = service.MerakiIpsk([provider])
                options = await bridge.options("N_fixture")
                self.assertEqual(options["group_policies"][0]["id"], "fixture-policy")
                created = await bridge.create({"network_id": "N_fixture", "ssid_number": 0,
                                               "name": "TV", "group_policy_id": "fixture-policy", "duration_hours": 0})
                self.assertEqual(created["passphrase"], "fixture-password")
                self.assertEqual((await bridge.list([{"network_id": "N_fixture", "ssid_number": 0}]))[0]["id"], created["id"])
                self.assertEqual((await bridge.key("get", created["id"]))["ssid_name"], "Resident Wi-Fi")
                self.assertEqual((await bridge.key("reveal_passphrase", created["id"]))["passphrase"], "fixture-password")
                await bridge.key("revoke", created["id"])
                self.assertEqual((await bridge.key("get", created["id"]))["status"], "expired")
                await bridge.key("delete", created["id"])
            post = next(r for r in requests if r[0] == "POST")
            self.assertEqual(post[1], "/api/v1/networks/N_fixture/wireless/ssids/0/identityPsks")
            self.assertEqual(post[2], {"name": "TV", "groupPolicyId": "fixture-policy"})
            self.assertTrue(any(r[0] == "PUT" and "expiresAt" in r[2] for r in requests))
            self.assertTrue(any(r[0] == "DELETE" for r in requests))
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    unittest.main()
