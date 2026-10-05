"""Resident lifecycle ownership, one-time secrets and uncertain writes."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import ipsk
import app
import meraki_provider
import resident_access
import test_meraki_configuration as fixtures
import test_resident_access as devices
from test_meraki_configuration import POLICIES
from test_resident_access import CONFIG, IDENTITY, MAC


TOKEN = "a" * 32
KEY = "nac:fixture-org:001122334455:10:" + TOKEN
CONFIG_AM = {**CONFIG, "key_backend": "access_manager", "access_manager_group_id": "10", "duration_hours": 0}


class ResidentServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures.ConfigurationTests.setUp(self)
        self.ssid["authMode"] = "ipsk-with-nac"
        self.message = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55",
                        "owner": "Resident", "passphrase": "one-time-resident-password", "group_id": "10", "registration_id": TOKEN}
        async def write(metadata, path, body):
            if not self.clients:
                self.clients.append({"id": "11", "mac": body["mac"]})
            row = self.clients[0]
            if "description" in body:
                row["description"] = body["description"]
            if "owner" in body:
                row["owner"] = body["owner"]
            row["ipsk"] = "configured" if body["ipsk"] else ""
            groups = body["groups"]
            row["groups"] = {"items": copy.deepcopy(groups if isinstance(groups, list) else groups.get("addList", []))}
            return {"ipsk": "response-secret-never-forwarded"}
        self.client.dashboard._session.post = AsyncMock(side_effect=write)
        self.client.dashboard._session.put = AsyncMock(side_effect=write)

    async def create(self):
        plan = await self.service.resident_key_plan(self.message)
        return await self.service.resident_create({**self.message, "expected_revision": plan["revision"]})

    async def test_create_confirms_hardware_mac_group_and_one_time_password(self):
        result = await self.create()
        self.assertEqual(result["id"], KEY)
        self.assertEqual(result["passphrase"], self.message["passphrase"])
        self.assertNotIn("response-secret", str(result))
        call = self.client.dashboard._session.post.await_args
        self.assertEqual(call.args[1], "/organizations/fixture-org/nac/clients")
        self.assertEqual(call.args[2]["description"], "Step CA resident " + TOKEN)
        self.assertEqual(call.args[2]["groups"], [{"value": "10", "display": "Residents"}])
        key = await self.service.key("get", KEY, "N_fixture", 0)
        self.assertEqual(key["status"], "active")
        self.assertNotIn("passphrase", key)
        with self.assertRaisesRegex(ValueError, "shown once"):
            await self.service.key("reveal_passphrase", KEY, "N_fixture", 0)

    async def test_existing_access_manager_client_never_gets_replaced(self):
        for fields in ({"ipsk": "configured"}, {"ipsk": ""}, {"ipsk": "masked"}, {"ipskConfigured": True}):
            self.clients[:] = [{"id": "11", "mac": self.message["mac"], "description": "Existing client", **fields}]
            with self.assertRaisesRegex(ValueError, "already exists"):
                await self.create()
        self.client.dashboard._session.post.assert_not_awaited()
        self.client.dashboard._session.put.assert_not_awaited()

    async def test_stale_snapshot_blocks_write(self):
        plan = await self.service.resident_key_plan(self.message)
        self.ssid["name"] = "Changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            await self.service.resident_create({**self.message, "expected_revision": plan["revision"]})
        self.client.dashboard._session.post.assert_not_awaited()

    async def test_fallback_rule_cannot_bypass_resident_revocation(self):
        rules = copy.deepcopy(POLICIES)
        rules[0]["rules"][0]["authorizationProfile"]["ipsk"]["mode"] = "clientIpskWithDefaultFallback"
        old_get = self.client.dashboard._session.get.side_effect
        async def read(metadata, path, params):
            return rules if path.endswith("/policies") else await old_get(metadata, path, params)
        self.client.dashboard._session.get.side_effect = read
        with self.assertRaisesRegex(ValueError, "clientIpskOnly"):
            await self.create()
        self.client.dashboard._session.post.assert_not_awaited()

    async def test_revocation_clears_only_owned_key_and_selected_group_keeps_client(self):
        await self.create()
        self.clients[0]["groups"]["items"].append({"value": "20", "display": "Other"})
        result = await self.service.key("revoke", KEY, "N_fixture", 0)
        self.assertEqual(result["status"], "revoked")
        self.assertEqual(len(self.clients), 1)
        body = self.client.dashboard._session.put.await_args.args[2]
        self.assertEqual(body, {"mac": self.message["mac"], "ipsk": "", "groups": {"removeList": [{"value": "10"}]}})
        self.assertNotIn("owner", body)

    async def test_changed_ownership_and_wrong_org_block_mutation(self):
        await self.create()
        self.clients[0]["description"] = "Managed in Dashboard"
        row = await self.service.key("get", KEY, "N_fixture", 0)
        self.assertEqual(row["status"], "review_required")
        with self.assertRaisesRegex(ValueError, "outside"):
            await self.service.key("delete", KEY, "N_fixture", 0)
        with self.assertRaisesRegex(ValueError, "different"):
            await self.service.key("revoke", KEY.replace("fixture-org", "other-org"), "N_fixture", 0)
        self.client.dashboard._session.put.assert_not_awaited()

    async def test_revocation_must_read_back_cleared_key(self):
        await self.create()
        self.client.dashboard._session.put.side_effect = None
        self.client.dashboard._session.put.return_value = {}
        with self.assertRaisesRegex(ValueError, "did not confirm"):
            await self.service.key("revoke", KEY, "N_fixture", 0)

    async def test_resident_owned_revoked_client_can_register_again(self):
        await self.create()
        await self.service.key("revoke", KEY, "N_fixture", 0)
        self.message["registration_id"] = "b" * 32
        result = await self.create()
        self.assertNotEqual(result["id"], KEY)
        self.assertEqual(len(self.clients), 1)
        self.assertEqual(self.client.dashboard._session.post.await_count, 1)
        self.assertEqual(self.client.dashboard._session.put.await_count, 2)

    async def test_inventory_is_batched_attributed_and_secret_free(self):
        await self.create()
        self.client.dashboard._session.get.reset_mock()
        rows = await self.service.resident_list({"keys": [{"ipsk_id": KEY, "network_id": "N_fixture", "ssid_number": 0}]})
        self.assertEqual(rows[0]["status"], "active")
        self.assertNotIn(self.message["passphrase"], str(rows))
        self.assertEqual(self.client.dashboard._session.get.await_count, 1)
        self.clients[0]["description"] = "external"
        rows = await self.service.resident_list({"keys": [{"ipsk_id": KEY, "network_id": "N_fixture", "ssid_number": 0}]})
        self.assertEqual(rows[0]["status"], "review_required")

    async def test_resident_portal_accepts_access_manager_without_wpn_switch(self):
        plan = await self.service.configuration_plan({"network_id": "N_fixture", "ssid_number": 0,
                    "portal_type": "resident", "portal_url": "https://ha.example.org/api/step_ca_scep/portal",
                    "auth_mode": "preserve"})
        self.assertEqual(plan["ssid_changes"]["splashPage"], "Click-through splash page")

    async def test_setup_portal_keeps_existing_psk_authentication(self):
        self.ssid["authMode"] = "psk"
        plan = await self.service.configuration_plan({"network_id": "N_fixture", "ssid_number": 0,
                    "portal_type": "resident", "portal_url": "https://ha.example.org/api/step_ca_scep/portal",
                    "auth_mode": "preserve"})
        self.assertNotIn("authMode", plan["ssid_changes"])
        self.assertNotIn("psk", plan["ssid_changes"])
        self.assertEqual(plan["splash_changes"]["useSplashUrl"], True)

    async def test_malformed_or_incomplete_inventory_cannot_release_access(self):
        for response in ({}, {"items": [], "meta": {"filteredCount": 2}}, {"items": [{"id": "11"}]}):
            self.client.dashboard._session.get.return_value = response
            self.client.dashboard._session.get.side_effect = None
            with self.assertRaises(ValueError):
                await self.service.resident_list({"keys": [{"ipsk_id": KEY, "network_id": "N_fixture", "ssid_number": 0}]})


class ResidentEngineTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.cur = MagicMock(), MagicMock()
        self.conn.__enter__.return_value = self.conn
        self.conn.cursor.return_value.__enter__.return_value = self.cur
        self.plan = {"id": KEY, "revision": "r1"}
        self.created = {"id": KEY, "ssid_name": "Residents", "passphrase": "private-password"}

    def test_pending_attribution_is_committed_before_remote_write_without_password(self):
        events = []
        def rpc(msg):
            events.append(msg["type"].rsplit("/", 1)[1])
            return [self.plan if events[-1] == "resident_key_plan" else self.created]
        self.conn.commit.side_effect = lambda: events.append("commit")
        with patch.dict(ipsk.os.environ, {"PORTAL_DB_HOST": "fixture"}), patch.object(ipsk, "db_connect", return_value=self.conn), patch.object(ipsk, "core_call", side_effect=rpc):
            ipsk.create_resident_key(CONFIG_AM, "TV", MAC, "101", "Resident")
        self.assertEqual(events, ["resident_key_plan", "commit", "resident_create", "commit"])
        self.assertNotIn("private-password", str(self.cur.execute.call_args_list))
        self.assertIn("'pending'", self.cur.execute.call_args_list[0].args[0])

    def test_uncertain_write_retains_pending_record_and_never_retries_or_deletes(self):
        with patch.dict(ipsk.os.environ, {"PORTAL_DB_HOST": "fixture"}), patch.object(ipsk, "db_connect", return_value=self.conn), \
                patch.object(ipsk, "core_call", side_effect=[[self.plan], RuntimeError("uncertain")]) as rpc, patch.object(ipsk, "set_ipsk_status") as cleanup:
            with self.assertRaises(RuntimeError):
                ipsk.create_resident_key(CONFIG_AM, "TV", MAC, "", "Resident")
        self.assertEqual(rpc.call_count, 2)
        self.conn.commit.assert_called_once()
        cleanup.assert_not_called()

    def test_expiry_rejected_before_remote_calls(self):
        with patch.dict(ipsk.os.environ, {"PORTAL_DB_HOST": "fixture"}), patch.object(ipsk, "core_call") as rpc:
            with self.assertRaisesRegex(ValueError, "expiry"):
                ipsk.create_resident_key({**CONFIG_AM, "duration_hours": 24}, "TV", MAC, "", "Resident")
        rpc.assert_not_called()

    def test_access_manager_scope_comes_from_record_not_current_configuration(self):
        self.cur.fetchone.return_value = {"network_id": "N_old", "ssid_number": 3}
        with patch.object(ipsk, "db_connect", return_value=self.conn):
            command = ipsk._key_command("revoke", KEY)
        self.assertEqual(command["network_id"], "N_old")
        self.assertEqual(command["ssid_number"], 3)

    def test_pending_keys_do_not_release_device_slots(self):
        record = {"ipsk_id": KEY, "network_id": "N_fixture", "ssid_number": 0,
                  "associated_user": "Resident", "associated_unit": "", "status": "pending"}
        with patch.object(ipsk, "_key_records", return_value=[record]), patch.object(resident_access, "settings", return_value=CONFIG_AM), \
                patch.object(ipsk, "core_call", return_value=[[{"id": KEY, "status": "revoked"}]]):
            keys = ipsk.list_ipsks()
        self.assertEqual(keys[0]["status"], "pending")
        self.assertEqual(ipsk.inactive_ipsk_ids(keys), [])

    def test_duo_device_flow_uses_access_manager_and_compensates_failed_local_commit(self):
        conn, cur = devices.DevicePersistence.connection(self, [{}, {"count": 0}, {"count": 0}, None])
        conn.commit.side_effect = RuntimeError("commit failed")
        with patch.object(ipsk, "db_connect", return_value=conn), patch.object(ipsk, "inactive_ipsk_ids", return_value=[]), \
                patch.object(ipsk, "create_resident_key", return_value=self.created) as create, patch.object(ipsk, "create_ipsk") as legacy, \
                patch.object(ipsk, "set_ipsk_status") as cleanup:
            with self.assertRaises(RuntimeError):
                resident_access.create_device(ipsk, {**CONFIG_AM, "invite_required": False}, IDENTITY, "TV", MAC, "101", "", "192.0.2.1")
        legacy.assert_not_called()
        create.assert_called_once_with({**CONFIG_AM, "invite_required": False}, "TV", MAC, "101", IDENTITY["name"])
        cleanup.assert_called_once_with(KEY, "delete")

    def test_backend_changes_invalidate_existing_duo_sessions(self):
        self.assertNotEqual(resident_access.policy_stamp(CONFIG), resident_access.policy_stamp(CONFIG_AM))
        self.assertNotEqual(resident_access.policy_stamp(CONFIG_AM), resident_access.policy_stamp({**CONFIG_AM, "access_manager_group_id": "20"}))

    def test_settings_save_uses_nac_ssid_and_group_preserves_duo(self):
        handler = app.Handler.__new__(app.Handler)
        handler.ipsk_network_page = MagicMock()
        options = {"database": "mariadb", "resident_onboarding": CONFIG}
        form = {"key_backend": ["access_manager"], "access_manager_group_id": ["10"], "network_id": ["N_fixture"],
                "ssid_number": ["0"], "duration_hours": ["0"], "enabled": ["1"], "invite_required": ["1"]}
        choices = {"networks": [{"id": "N_fixture"}], "ssids": [], "active_ssids": [{"number": 0, "auth_mode": "ipsk-with-nac"}]}
        with patch.object(app, "saved_options", return_value=options), patch.object(ipsk, "get_options", return_value=choices), \
                patch.object(ipsk, "core_call", return_value=[{"groups": [{"id": "10"}]}]), patch.object(app, "supervisor") as save:
            handler.ipsk_network_save(form)
        config = save.call_args.args[2]["options"]["resident_onboarding"]
        self.assertEqual(config["key_backend"], "access_manager")
        self.assertEqual(config["access_manager_group_id"], "10")
        self.assertEqual(config["duo_group_id"], CONFIG["duo_group_id"])
        self.assertTrue(config["sign_in_required"])

    def test_settings_reject_wrong_ssid_group_or_expiry_without_saving(self):
        for changed in ({"duration_hours": ["24"]}, {"access_manager_group_id": ["other"]}, {"ssid_number": ["1"]}):
            handler = app.Handler.__new__(app.Handler)
            handler.ipsk_network_page = MagicMock()
            form = {"key_backend": ["access_manager"], "access_manager_group_id": ["10"], "network_id": ["N_fixture"],
                    "ssid_number": ["0"], "duration_hours": ["0"], "enabled": ["1"], **changed}
            choices = {"networks": [{"id": "N_fixture"}], "active_ssids": [{"number": 0, "auth_mode": "ipsk-with-nac"},
                                                                                 {"number": 1, "auth_mode": "8021x-nac"}]}
            with patch.object(app, "saved_options", return_value={"database": "mariadb", "resident_onboarding": CONFIG}), \
                    patch.object(ipsk, "get_options", return_value=choices), patch.object(ipsk, "core_call", return_value=[{"groups": [{"id": "10"}]}]), \
                    patch.object(app, "supervisor") as save:
                handler.ipsk_network_save(form)
            save.assert_not_called()
            self.assertIn("error", handler.ipsk_network_page.call_args.kwargs)

    def test_portal_assignment_requires_configured_separate_setup_ssid(self):
        config = {**CONFIG_AM, "enabled": True, "setup_ssid": "Setup"}
        message = {"portal_type": "resident", "network_id": "N_fixture", "ssid_number": 1,
                   "auth_mode": "preserve", "portal_url": "https://ha.example.org/api/step_ca_scep/portal"}
        options = {"active_ssids": [{"number": 0, "name": "Residents", "auth_mode": "ipsk-with-nac"},
                                   {"number": 1, "name": "Setup", "auth_mode": "psk"}]}
        handler = app.Handler.__new__(app.Handler)
        with patch.object(resident_access, "settings", return_value=config), patch.object(ipsk, "get_options", return_value=options):
            handler.meraki_resident_scope(message)
            for changed in ({"ssid_number": 0}, {"network_id": "N_other"}, {"auth_mode": "ipsk-with-nac"},
                            {"portal_url": "https://ha.example.org/wrong"}):
                with self.assertRaises(ValueError):
                    handler.meraki_resident_scope({**message, **changed})


class ResidentSdkContract(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_creates_lists_and_revokes_without_deleting_client(self):
        import meraki.aio
        rows, writes, sessions = [], [], []
        reject_write = False
        async def endpoint(request):
            path = request.path
            if request.method != "GET":
                body = await request.json()
                writes.append((request.method, path, body))
                if reject_write:
                    return web.json_response({"errors": ["uncertain provider-secret"]}, status=500)
                if not rows:
                    rows.append({"id": "11", "mac": body["mac"], "description": body["description"], "owner": body["owner"]})
                rows[0]["ipsk"] = "configured" if body["ipsk"] else ""
                rows[0]["groups"] = {"items": body["groups"] if isinstance(body["groups"], list) else []}
                return web.json_response({"items": copy.deepcopy(rows)})
            if path.endswith("/networks"):
                return web.json_response([{"id": "N_fixture", "name": "Fixture", "productTypes": ["wireless"]}])
            if path.endswith("/ssids/0"):
                return web.json_response({"number": 0, "name": "Residents", "enabled": True, "authMode": "ipsk-with-nac"})
            if path.endswith("/policies"):
                return web.json_response(POLICIES)
            if path.endswith("/groups"):
                return web.json_response(fixtures.GROUPS)
            return web.json_response({"items": copy.deepcopy(rows), "meta": {"filteredCount": len(rows)}})
        http = web.Application()
        http.router.add_route("*", "/{path:.*}", endpoint)
        runner = web.AppRunner(http)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        constructor = meraki.aio.AsyncDashboardAPI
        def sdk(**kwargs):
            kwargs["maximum_retries"] = 3
            result = constructor(**kwargs, base_url=f"http://127.0.0.1:{port}/api/v1")
            sessions.append(result)
            return result
        config = {"source": "api_key", "api_key": "fixture-api-key", "organization_id": "123"}
        message = {"network_id": "N_fixture", "ssid_number": 0, "mac": "00:11:22:33:44:55", "owner": "Resident",
                   "group_id": "10", "registration_id": TOKEN, "passphrase": "one-time-password"}
        try:
            with patch.object(meraki.aio, "AsyncDashboardAPI", side_effect=sdk):
                plan = (await meraki_provider.direct_call(config, [{**message, "type": "step_ca_scep/ipsk/resident_key_plan"}]))[0]
                key = (await meraki_provider.direct_call(config, [{**message, "type": "step_ca_scep/ipsk/resident_create", "expected_revision": plan["revision"]}]))[0]
                self.assertEqual(key["passphrase"], "one-time-password")
                payload = {"ipsk_id": key["id"], "network_id": "N_fixture", "ssid_number": 0}
                listed = (await meraki_provider.direct_call(config, [{"type": "step_ca_scep/ipsk/resident_list", "keys": [payload]}]))[0]
                self.assertEqual(listed[0]["status"], "active")
                self.assertNotIn("one-time-password", str(listed))
                revoked = (await meraki_provider.direct_call(config, [{**payload, "type": "step_ca_scep/ipsk/revoke"}]))[0]
                self.assertEqual(revoked["status"], "revoked")
                self.assertEqual(len(rows), 1)
                self.assertEqual([w[0] for w in writes], ["POST", "PUT"])
                # Meraki HA's shared session retries three times. A NAC facade
                # must attempt the uncertain mutation only once, without
                # changing the shared session's retry policy.
                rows.clear()
                reject_write = True
                plan = (await meraki_provider.direct_call(config, [{**message, "type": "step_ca_scep/ipsk/resident_key_plan"}]))[0]
                with self.assertRaises(RuntimeError) as err:
                    await meraki_provider.direct_call(config, [{**message, "type": "step_ca_scep/ipsk/resident_create", "expected_revision": plan["revision"]}])
                self.assertNotIn("provider-secret", str(err.exception))
                self.assertTrue(all(s._session._maximum_retries == 3 for s in sessions))
            self.assertEqual([w[0] for w in writes], ["POST", "PUT", "POST"])
            self.assertEqual(writes[1][1], "/api/v1/organizations/123/nac/clients/11")
            self.assertEqual(writes[1][2]["ipsk"], "")
        finally:
            await runner.cleanup()
