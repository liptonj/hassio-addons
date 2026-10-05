"""Provider routing, preview safety and documented SSID/NAC wire contracts."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import ipsk
import meraki_provider as provider
import meraki_settings as settings
import resident_access
from test_meraki_bridge import client, service

POLICIES = [{"policyId": "1", "version": "v1", "name": "Residents", "enabled": True,
             "rules": [{"name": "Client keys", "enabled": True, "authorizationProfile": {
                 "result": "PERMIT", "ipsk": {"mode": "clientIpskOnly", "value": "policy-secret"}}}]}]
GROUPS = {"meta": {"filteredCount": 1}, "items": [{"id": "10", "name": "Residents"}]}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_reuses_integration_and_never_sends_api_key_to_core(self):
        core = AsyncMock(return_value=[{"provider": "meraki_ha"}])
        message = {"type": "step_ca_scep/ipsk/delete", "ipsk_id": "N_fixture:0:key"}
        with patch.object(provider, "SETTINGS_OVERRIDE", {"api_key": "private-api-key"}), \
                patch.object(provider, "direct_call", new_callable=AsyncMock) as direct:
            await provider.call(core, (message,), "supervisor")
        self.assertEqual(core.await_count, 2)
        self.assertNotIn("private-api-key", str(core.await_args_list))
        direct.assert_not_awaited()

    async def test_auto_falls_back_only_after_readonly_probe_is_unavailable(self):
        core = AsyncMock(side_effect=provider.ProviderUnavailable("absent"))
        message = {"type": "step_ca_scep/ipsk/create", "name": "TV"}
        with patch.object(provider, "SETTINGS_OVERRIDE", {"api_key": "private-api-key"}), \
                patch.object(provider, "direct_call", new_callable=AsyncMock) as direct:
            await provider.call(core, (message,), "supervisor")
        self.assertEqual(core.await_args.args[0]["type"], "step_ca_scep/ipsk/options")
        direct.assert_awaited_once()

    async def test_provider_error_and_uncertain_write_never_change_transport(self):
        for effects in ([RuntimeError("unauthorized")], [[{}], RuntimeError("uncertain write")],
                        [[{}], provider.ProviderUnavailable("later command unavailable")]):
            with self.subTest(effects=effects), patch.object(provider, "SETTINGS_OVERRIDE", {"api_key": "key"}), \
                    patch.object(provider, "direct_call", new_callable=AsyncMock) as direct:
                with self.assertRaises(RuntimeError):
                    await provider.call(AsyncMock(side_effect=effects), ({"type": "step_ca_scep/ipsk/create"},), "supervisor")
                direct.assert_not_awaited()

    async def test_integration_only_never_falls_back_and_key_only_never_calls_core(self):
        core = AsyncMock(side_effect=provider.ProviderUnavailable("absent"))
        with patch.object(provider, "SETTINGS_OVERRIDE", {"source": "meraki_ha", "api_key": "key"}), \
                patch.object(provider, "direct_call", new_callable=AsyncMock) as direct:
            with self.assertRaises(provider.ProviderUnavailable):
                await provider.call(core, (), "supervisor")
            direct.assert_not_awaited()
        core.reset_mock()
        with patch.object(provider, "SETTINGS_OVERRIDE", {"source": "api_key", "api_key": "key"}), \
                patch.object(provider, "direct_call", new_callable=AsyncMock) as direct:
            await provider.call(core, (), "supervisor")
            direct.assert_awaited_once()
            core.assert_not_awaited()


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = client()
        self.service = service.MerakiIpsk([self.client])
        self.ssid = {"number": 0, "name": "Residents", "enabled": True, "authMode": "psk", "psk": "ssid-secret",
                     "splashPage": "None", "ipAssignmentMode": "NAT mode", "wpaEncryptionMode": "WPA2 only",
                     "dot11r": {"enabled": True}, "walledGardenRanges": ["existing.example.org"]}
        self.splash = {"useSplashUrl": False, "splashUrl": ""}
        wireless = self.client.dashboard.wireless
        wireless.getNetworkWirelessSsid.side_effect = lambda *args: copy.deepcopy(self.ssid)
        wireless.getNetworkWirelessSsidSplashSettings = AsyncMock(side_effect=lambda *args: copy.deepcopy(self.splash))
        async def update_ssid(*args, **fields):
            self.ssid.update(fields)
            self.ssid["dot11r"] = {**self.ssid.get("dot11r", {}), "adaptive": False}
            return copy.deepcopy(self.ssid)
        async def update_splash(*args, **fields):
            self.splash.update(fields)
            return copy.deepcopy(self.splash)
        wireless.updateNetworkWirelessSsid = AsyncMock(side_effect=update_ssid)
        wireless.updateNetworkWirelessSsidSplashSettings = AsyncMock(side_effect=update_splash)
        self.message = {"network_id": "N_fixture", "ssid_number": 0, "portal_type": "external",
                        "portal_url": "https://portal.example.org/join", "auth_mode": "ipsk-without-radius",
                        "prepare_wpn": True, "vlan_id": 100, "walled_garden_ranges": ["api-example.duosecurity.com"]}
        self.clients = []
        async def nac_get(metadata, path, params):
            if path.endswith("/policies"):
                return copy.deepcopy(POLICIES)
            if path.endswith("/groups"):
                return copy.deepcopy(GROUPS)
            return {"items": copy.deepcopy(self.clients), "meta": {"filteredCount": len(self.clients)}}
        self.client.dashboard._session.get = AsyncMock(side_effect=nac_get)
        self.client.dashboard._session.post = AsyncMock(return_value={"ipsk": "never-return-key"})
        self.client.dashboard._session.put = AsyncMock(return_value={"ipsk": "never-return-key"})

    async def test_discovery_lists_all_enabled_ssids_and_keeps_key_issuer_filter(self):
        result = await self.service.options("N_fixture")
        self.assertEqual([s["number"] for s in result["active_ssids"]], [0, 1])
        self.assertEqual([s["number"] for s in result["ssids"]], [0])

    async def test_preview_is_readonly_allowlisted_and_never_invents_wpn_flag(self):
        plan = await self.service.configuration_plan(self.message)
        self.assertNotIn("ssid-secret", json.dumps(plan))
        changes = plan["ssid_changes"]
        self.assertEqual(changes["defaultVlanId"], 100)
        self.assertEqual(changes["walledGardenRanges"], ["existing.example.org", "portal.example.org", "api-example.duosecurity.com"])
        self.assertEqual(changes["dot11r"], {"enabled": False})
        self.assertNotIn("wifiPersonalNetworkEnabled", changes)
        self.assertIn("no WPN enable switch", " ".join(plan["manual_steps"]))
        self.client.dashboard.wireless.updateNetworkWirelessSsid.assert_not_awaited()

    async def test_enterprise_access_manager_ssid_requires_certificate_trust_and_reads_back(self):
        msg = {**self.message, 'portal_type': 'none', 'portal_url': '', 'auth_mode': '8021x-nac', 'prepare_wpn': False}
        plan = await self.service.configuration_plan(msg)
        self.assertEqual(plan['ssid_changes']['authMode'], '8021x-nac')
        self.assertEqual(plan['ssid_changes']['splashPage'], 'None')
        self.assertIn('trusted anchor', ' '.join(plan['manual_steps']))
        self.assertNotIn('psk', plan['ssid_changes'])
        result = await self.service.configure({**msg, 'expected_revision': plan['revision']})
        self.assertTrue(result['complete'])

    async def test_apply_checks_revision_writes_only_selected_scope_and_reads_back(self):
        plan = await self.service.configuration_plan(self.message)
        result = await self.service.configure({**self.message, "expected_revision": plan["revision"]})
        self.assertTrue(result["complete"])
        call = self.client.dashboard.wireless.updateNetworkWirelessSsid.await_args
        self.assertEqual(call.args, ("N_fixture", 0))
        self.assertNotIn("psk", call.kwargs)

    async def test_stale_preview_prevents_all_writes(self):
        plan = await self.service.configuration_plan(self.message)
        self.ssid["splashPage"] = "SMS authentication"
        with self.assertRaisesRegex(ValueError, "changed since"):
            await self.service.configure({**self.message, "expected_revision": plan["revision"]})
        self.client.dashboard.wireless.updateNetworkWirelessSsid.assert_not_awaited()

    async def test_partial_failure_is_reported_without_rollback_or_retries(self):
        plan = await self.service.configuration_plan(self.message)
        self.client.dashboard.wireless.updateNetworkWirelessSsidSplashSettings.side_effect = RuntimeError("sdk-secret")
        result = await self.service.configure({**self.message, "expected_revision": plan["revision"]})
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["applied"]), 1)
        self.assertNotIn("sdk-secret", json.dumps(result))
        self.client.dashboard.wireless.updateNetworkWirelessSsid.assert_awaited_once()
        self.client.dashboard.wireless.updateNetworkWirelessSsidSplashSettings.assert_awaited_once()

    async def test_guest_disables_splash_and_external_url_is_validated(self):
        plan = await self.service.configuration_plan({**self.message, "portal_type": "guest", "portal_url": ""})
        self.assertEqual(plan["ssid_changes"]["splashPage"], "None")
        self.assertEqual(plan["splash_changes"], {"useSplashUrl": False})
        for url in ("http://portal.example.org", "https://user:password@host", "https://host/#fragment", "https://host:99999"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                await self.service.configuration_plan({**self.message, "portal_url": url})

    async def test_wpn_and_resident_reject_access_manager_and_disabled_ssid(self):
        for fields in ({"auth_mode": "ipsk-with-nac"}, {"portal_type": "resident", "auth_mode": "ipsk-with-nac"}, {"vlan_id": 4095}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                await self.service.configuration_plan({**self.message, **fields})
        self.ssid["enabled"] = False
        with self.assertRaises(ValueError):
            await self.service.configuration_plan(self.message)

    async def test_access_manager_preview_strips_policy_and_client_keys(self):
        self.ssid["authMode"] = "ipsk-with-nac"
        info = await self.service.access_manager("N_fixture")
        self.assertNotIn("policy-secret", json.dumps(info))
        msg = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Alice",
               "group_id": "10", "passphrase": "private-client-key"}
        plan = await self.service.client_key_plan(msg)
        self.assertEqual(plan["operation"], "Create client")
        self.assertNotIn(msg["passphrase"], json.dumps(plan))
        result = await self.service.assign_client_key({**msg, "expected_revision": plan["revision"]})
        self.assertNotIn("never-return-key", json.dumps(result))
        args = self.client.dashboard._session.post.await_args.args
        self.assertEqual(args[1], "/organizations/fixture-org/nac/clients")
        self.assertEqual(args[2], {"mac": msg["mac"], "owner": "Alice", "ipsk": msg["passphrase"], "type": "BYOD",
                                   "groups": [{"value": "10", "display": "Residents"}]})

    async def test_access_manager_existing_client_uses_update_and_preserves_other_groups(self):
        self.ssid["authMode"] = "ipsk-with-nac"
        self.clients = [{"id": "11", "mac": "00:11:22:33:44:55", "groups": [{"value": "12"}], "ipskConfigured": True}]
        msg = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Alice", "group_id": "10", "passphrase": "private-client-key"}
        plan = await self.service.client_key_plan(msg)
        await self.service.assign_client_key({**msg, "expected_revision": plan["revision"]})
        args = self.client.dashboard._session.put.await_args.args
        self.assertEqual(args[1], "/organizations/fixture-org/nac/clients/11")
        self.assertEqual(args[2]["groups"], {"addList": [{"value": "10", "display": "Residents"}]})
        self.client.dashboard._session.post.assert_not_awaited()

    async def test_access_manager_requires_enabled_per_client_rule_and_rejects_pagination(self):
        self.ssid["authMode"] = "ipsk-with-nac"
        self.client.dashboard._session.get.side_effect = None
        self.client.dashboard._session.get.return_value = []
        with self.assertRaises(ValueError):
            await self.service.client_key_plan({"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Alice", "group_id": "10", "passphrase": "private-client-key"})
        with self.assertRaisesRegex(ValueError, "more pages"):
            service.MerakiIpsk.nac_items({"meta": {"filteredCount": 1001}, "items": [{}]})

    async def test_changed_access_manager_client_prevents_writes(self):
        self.ssid["authMode"] = "ipsk-with-nac"
        msg = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Alice", "group_id": "10", "passphrase": "private-client-key"}
        plan = await self.service.client_key_plan(msg)
        self.clients = [{"id": "11", "mac": msg["mac"], "owner": "New owner"}]
        with self.assertRaisesRegex(ValueError, "changed since"):
            await self.service.assign_client_key({**msg, "expected_revision": plan["revision"]})
        self.client.dashboard._session.post.assert_not_awaited()
        self.client.dashboard._session.put.assert_not_awaited()


class AdminWorkflowTests(unittest.TestCase):
    def setUp(self):
        settings.PENDING.clear()
        self.provider_patch = patch.object(provider, "SETTINGS_OVERRIDE", {})
        self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def handler(self, route, fields=None, owner="admin"):
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/settings/meraki/" + route
        handler.headers = {"X-Remote-User-Id": owner, "X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        if fields is not None:
            body = urlencode({"csrf": app.CSRF_TOKEN, **fields}).encode()
            handler.headers["Content-Length"] = str(len(body))
            handler.rfile = io.BytesIO(body)
        return handler

    def test_connection_save_retains_blank_key_never_embeds_secret_and_supports_clear(self):
        saved = {"meraki": {"api_key": "private-api-key", "source": "auto"}}
        for extra, expected in (({}, "private-api-key"), ({"clear_key": "1"}, "")):
            handler = self.handler("connection/save", {"source": "auto", "api_key": "", "organization_id": "123", **extra})
            with patch.object(app, "saved_options", return_value=copy.deepcopy(saved)), patch.object(app, "supervisor") as write:
                handler.handle_post()
            self.assertEqual(write.call_args.args[2]["options"]["meraki"]["api_key"], expected)
            self.assertNotIn("private-api-key", handler.send.call_args.args[1])

    def test_new_endpoints_require_csrf_before_provider_requests(self):
        for route in ("connection/save", "connection/test", "ssids/preview", "ssids/apply", "access-manager/preview", "access-manager/apply"):
            with self.subTest(route=route), patch.object(ipsk, "core_call") as call:
                handler = self.handler(route, {"csrf": "invalid"})
                handler.handle_post()
                self.assertEqual(handler.send.call_args.args[0], 403)
                call.assert_not_called()

    def test_ssid_zero_is_a_valid_option_and_api_key_summary_is_redacted(self):
        self.assertIn('value="0" selected', settings.options("ssid", [(0, "Residents")], 0))
        self.assertEqual(settings.esc(0), "0")
        import settings_menu
        summary = settings_menu.option_rows("meraki", {"source": "auto", "api_key": "private-api-key"})
        self.assertIn("Saved", summary)
        self.assertNotIn("private-api-key", summary)

    def test_preview_is_owner_bound_single_use_and_connection_bound(self):
        token = settings.remember("admin", "ssids", {"ssid_number": 0}, {"revision": "revision"})
        with self.assertRaises(ValueError):
            settings.take("other", token)
        self.assertEqual(settings.take("admin", token)["revision"], "revision")
        with self.assertRaises(ValueError):
            settings.take("admin", token)
        token = settings.remember("admin", "ssids", {}, {"revision": "revision"})
        provider.SETTINGS_OVERRIDE = {"source": "api_key", "api_key": "new-key"}
        with self.assertRaisesRegex(ValueError, "connection changed"):
            settings.take("admin", token)

    def test_expired_preview_cannot_apply(self):
        token = settings.remember("admin", "ssids", {}, {"revision": "revision"})
        with patch.object(settings.time, "monotonic", return_value=10**15), self.assertRaises(ValueError):
            settings.take("admin", token)

    def test_resident_portal_rejects_other_scopes_and_wrong_public_path(self):
        handler = self.handler("ssids")
        config = {"enabled": True, "network_id": "N_fixture", "ssid_number": 0}
        msg = {"portal_type": "resident", "network_id": "N_fixture", "ssid_number": 0, "portal_url": "https://ha.example.org/api/step_ca_scep/portal"}
        with patch.object(resident_access, "settings", return_value=config):
            handler.meraki_resident_scope(msg)
            for changes in ({"network_id": "N_other"}, {"ssid_number": 1}, {"portal_url": "https://ha.example.org/wrong"}):
                with self.assertRaises(ValueError):
                    handler.meraki_resident_scope({**msg, **changes})

    def test_access_manager_preview_holds_key_on_server_only_and_apply_ignores_injected_fields(self):
        fields = {"network_id": "N_fixture", "ssid_number": "0", "mac": "00:11:22:33:44:55", "owner": "Alice", "group_id": "10", "passphrase": "private-client-key"}
        plan = {"revision": "r1", "organization_id": "123", "network_id": "N_fixture", "ssid_name": "Residents",
                "operation": "Create client", "mac": fields["mac"], "owner": "Alice", "group": {"name": "Residents"}}
        handler = self.handler("access-manager/preview", fields)
        with patch.object(ipsk, "core_call", return_value=[plan]):
            handler.handle_post()
        self.assertNotIn("private-client-key", handler.send.call_args.args[1])
        token = next(iter(settings.PENDING))
        handler = self.handler("access-manager/apply", {"preview_token": token, "network_id": "N_injected"})
        handler.meraki_page = MagicMock()
        with patch.object(ipsk, "core_call", return_value=[{"message": "Accepted"}]) as call:
            handler.handle_post()
        self.assertEqual(call.call_args.args[0]["network_id"], "N_fixture")
        self.assertEqual(call.call_args.args[0]["passphrase"], "private-client-key")


@unittest.skipUnless(__import__("importlib.util").util.find_spec("meraki"), "Meraki SDK optional")
class SdkConfigurationContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_fallback_ssid_and_beta_nac_requests_use_real_sdk(self):
        import meraki.aio
        requests = []
        feature_disabled = False
        ssid = {"number": 0, "name": "Residents", "enabled": True, "authMode": "psk", "splashPage": "None", "psk": "ssid-secret"}
        splash = {"useSplashUrl": False, "splashUrl": ""}
        async def fixture(request):
            body = await request.json() if request.method in ("POST", "PUT") else None
            requests.append((request.method, request.path, body, request.headers.get("Authorization")))
            if request.path.endswith("/organizations"):
                return web.json_response([{"id": "123"}])
            if request.path.endswith("/networks"):
                return web.json_response([{"id": "N_fixture", "name": "Home", "productTypes": ["wireless"]}])
            if request.path.endswith("/groupPolicies"):
                return web.json_response([])
            if request.path.endswith("/wireless/ssids"):
                return web.json_response([ssid])
            if request.path.endswith("/wireless/ssids/0"):
                if body:
                    ssid.update(body)
                return web.json_response(ssid)
            if request.path.endswith("/splash/settings"):
                if body:
                    splash.update(body)
                return web.json_response(splash)
            if request.path.endswith("/policies"):
                return web.json_response(POLICIES)
            if request.path.endswith("/groups"):
                return web.json_response(GROUPS)
            if request.path.endswith("/nac/clients"):
                if request.method == "POST" and feature_disabled:
                    return web.json_response({"errors": ["Feature unavailable: private-client-key"]}, status=403)
                return web.json_response({"items": [], "meta": {"filteredCount": 0}} if request.method == "GET" else {"id": "1", "ipsk": "never-return-key"})
            return web.json_response({"error": "unexpected request"}, status=404)
        server = web.Application()
        server.router.add_route("*", "/api/v1/{path:.*}", fixture)
        runner = web.AppRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        constructor = meraki.aio.AsyncDashboardAPI
        def sdk(**kw):
            return constructor(**kw, base_url=f"http://127.0.0.1:{port}/api/v1")
        try:
            with patch.object(meraki.aio, "AsyncDashboardAPI", side_effect=sdk):
                config = {"source": "api_key", "api_key": "fixture-api-key"}
                opts = (await provider.direct_call(config, [{"type": "step_ca_scep/ipsk/options", "network_id": "N_fixture"}]))[0]
                self.assertEqual(opts["active_ssids"][0]["auth_mode"], "psk")
                enterprise = {"network_id": "N_fixture", "ssid_number": 0, "portal_type": "none", "auth_mode": "8021x-nac", "portal_url": ""}
                enterprise_plan = (await provider.direct_call(config, [{**enterprise, "type": "step_ca_scep/ipsk/configuration_plan"}]))[0]
                self.assertFalse(any(r[0] != "GET" for r in requests))
                enterprise_result = (await provider.direct_call(config, [{**enterprise, "type": "step_ca_scep/ipsk/configure", "expected_revision": enterprise_plan["revision"]}]))[0]
                self.assertTrue(enterprise_result["complete"])
                self.assertEqual(ssid["authMode"], "8021x-nac")
                self.assertEqual(ssid["splashPage"], "None")
                self.assertFalse(splash["useSplashUrl"])
                msg = {"network_id": "N_fixture", "ssid_number": 0, "portal_type": "external", "auth_mode": "ipsk-with-nac", "portal_url": "https://portal.example.org"}
                plan = (await provider.direct_call(config, [{**msg, "type": "step_ca_scep/ipsk/configuration_plan"}]))[0]
                self.assertEqual(len([r for r in requests if r[0] != "GET"]), 2)
                result = (await provider.direct_call(config, [{**msg, "type": "step_ca_scep/ipsk/configure", "expected_revision": plan["revision"]}]))[0]
                self.assertTrue(result["complete"])
                client_msg = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Alice", "passphrase": "private-client-key", "group_id": "10"}
                plan = (await provider.direct_call(config, [{**client_msg, "type": "step_ca_scep/ipsk/client_key_plan"}]))[0]
                result = (await provider.direct_call(config, [{**client_msg, "type": "step_ca_scep/ipsk/assign_client_key", "expected_revision": plan["revision"]}]))[0]
                self.assertNotIn("never-return-key", json.dumps(result))
                feature_disabled = True
                with self.assertRaises(RuntimeError) as rejected:
                    await provider.direct_call(config, [{**client_msg, "type": "step_ca_scep/ipsk/assign_client_key", "expected_revision": plan["revision"]}])
                self.assertNotIn("private-client-key", str(rejected.exception))
            writes = [r for r in requests if r[0] != "GET"]
            # One POST for each of two explicit apply calls; the rejected write
            # is never automatically repeated by the direct SDK transport.
            self.assertEqual([r[0] for r in writes], ["PUT", "PUT", "PUT", "PUT", "POST", "POST"])
            self.assertEqual(writes[-1][1], "/api/v1/organizations/123/nac/clients")
            self.assertEqual(writes[-1][2]["ipsk"], "private-client-key")
            self.assertNotIn("psk", writes[0][2])
            self.assertTrue(all(r[3] == "Bearer fixture-api-key" for r in requests))
        finally:
            await runner.cleanup()
