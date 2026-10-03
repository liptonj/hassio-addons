"""Regression coverage for the full Step CA audit; uses local fixtures only."""
import io
import json
import re
import shutil
import subprocess
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'admin'))
import app
import db_setup
import ipsk
import resident_access
import ui


class AuditRegression(unittest.TestCase):
    def setUp(self):
        remote = patch.object(ipsk, "inactive_ipsk_ids", return_value=[])
        remote.start()
        self.addCleanup(remote.stop)

    @unittest.skipUnless(shutil.which("jq"), "jq is required by the add-on runtime")
    def test_false_boolean_options_are_preserved_by_startup(self):
        source = (Path(__file__).resolve().parents[1] / "run.sh").read_text()
        for variable in ("install_integration", "resident_invite_required"):
            line = next(line for line in source.splitlines() if line.startswith(variable + "="))
            expression = re.search(r"option '([^']+)'", line)[1]
            for value, expected in ((False,"false"),(True,"true"),(None,"true")):
                options = {"install_integration":value,"resident_onboarding":{"invite_required":value}}
                result = subprocess.run(["jq","-r",expression],input=json.dumps(options),text=True,capture_output=True,check=True)
                self.assertEqual(result.stdout.strip(),expected)

    def test_invalid_admin_request_size_fails_without_reading_body(self):
        for value in ('-1', 'invalid'):
            handler = app.Handler.__new__(app.Handler)
            handler.path = '/residents/invite'
            handler.headers = {'Content-Length': value}
            handler.rfile = MagicMock()
            handler.send = MagicMock()
            handler.handle_post()
            handler.send.assert_called_once_with(400, 'Invalid request size', 'text/plain')
            handler.rfile.read.assert_not_called()

    def test_invalid_public_enrollment_size_fails_before_link_or_body_read(self):
        for value in ('-1', 'invalid', '4097'):
            handler = app.EnrollHandler.__new__(app.EnrollHandler)
            handler.path = '/enroll/' + 'a' * 43
            handler.headers = {'Content-Length': value}
            handler.allowed = lambda: True
            handler.rfile = MagicMock()
            handler.send = MagicMock()
            with patch.object(app.LINKS, 'get') as lookup:
                handler.do_POST()
            self.assertIn(handler.send.call_args.args[0], (400, 413))
            handler.rfile.read.assert_not_called()
            lookup.assert_not_called()

    def test_duplicate_admin_form_field_cannot_reach_action(self):
        handler = app.Handler.__new__(app.Handler)
        data = ('csrf=' + app.CSRF_TOKEN + '&invite_id=1&invite_id=2').encode()
        handler.path = '/residents/invite/revoke'
        handler.headers = {'Content-Length': str(len(data))}
        handler.rfile = io.BytesIO(data)
        handler.send = MagicMock()
        with patch.object(ipsk, 'revoke_invite') as revoke:
            handler.handle_post()
        self.assertEqual(handler.send.call_args.args[0], 400)
        revoke.assert_not_called()

    def test_device_lock_is_bounded_database_scoped_and_released(self):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.return_value = {'acquired': 1}
        with patch.dict(os.environ, {'DB_NAME': 'fixture'}):
            name = ipsk.lock_device(conn, '00:11:22:33:44:55')
        self.assertLessEqual(len(name), 64)
        self.assertIn('GET_LOCK(%s, 15)', cur.execute.call_args.args[0])
        ipsk.unlock_device(conn, name)
        cur.execute.assert_called_with('SELECT RELEASE_LOCK(%s)', (name,))

    def test_busy_device_lock_does_not_create_a_key(self):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.return_value = {'acquired': 0}
        with patch.object(ipsk, 'db_connect', return_value=conn), patch.object(ipsk, 'create_ipsk') as create:
            with self.assertRaisesRegex(ValueError, 'being registered'):
                resident_access.create_device(ipsk, {'invite_required': False},
                    {'owner': 'fixture', 'name': 'Fixture', 'email': 'fixture@example.org'},
                    'TV', '00:11:22:33:44:55', '', '', '192.0.2.1')
        create.assert_not_called()
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_legacy_registration_missing_ssid_rolls_back_and_removes_key(self):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.side_effect = [{'acquired': 1}, None, None]
        with patch.dict(os.environ, {'RESIDENT_SETTINGS_JSON': '{"network_id":"N_fixture"}'}), \
                patch.object(ipsk, 'INVITE_REQUIRED', False), patch.object(ipsk, 'db_connect', return_value=conn), \
                patch.object(ipsk, 'create_ipsk', return_value={'id':'fixture-key','passphrase':'fixture-password'}), \
                patch.object(ipsk, 'set_ipsk_status') as cleanup:
            with self.assertRaises(ValueError):
                ipsk.register_resident('Fixture Resident','fixture@example.org','','','192.0.2.1','00:11:22:33:44:55')
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        cleanup.assert_called_once_with('fixture-key', 'delete')
        self.assertTrue(any('RELEASE_LOCK' in c.args[0] for c in cur.execute.call_args_list))

    def test_legacy_cleanup_logs_no_provider_exception_body(self):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.side_effect = [{'acquired': 1}, None, None]
        with patch.dict(os.environ, {'RESIDENT_SETTINGS_JSON': '{"network_id":"N_fixture"}'}), \
                patch.object(ipsk, 'INVITE_REQUIRED', False), patch.object(ipsk, 'db_connect', return_value=conn), \
                patch.object(ipsk, 'create_ipsk', return_value={'id': 'fixture-key', 'passphrase': 'fixture-password'}), \
                patch.object(ipsk, 'set_ipsk_status', side_effect=RuntimeError('fixture-reflected-secret')), \
                patch('builtins.print') as output:
            with self.assertRaises(ValueError):
                ipsk.register_resident('Fixture Resident', 'fixture@example.org', '', '', '192.0.2.1', '00:11:22:33:44:55')
        output.assert_called_once()
        self.assertNotIn('fixture-reflected-secret', str(output.call_args))
        self.assertIn('fixture-key', output.call_args.args[0])

    def test_legacy_registration_errors_do_not_log_provider_body(self):
        handler = ipsk.PublicPortalHandler.__new__(ipsk.PublicPortalHandler)
        handler.path = '/portal'
        handler.client_address = ('127.0.0.1', 1)
        form = 'csrf=fixture-context&name=Fixture&email=fixture%40example.org'
        handler.headers = {'Content-Length': str(len(form)), 'Cookie': 'portal_csrf=fixture-context'}
        handler.rfile = io.BytesIO(form.encode())
        handler._allowed = lambda: True
        with patch.object(ipsk, 'PORTAL_ENABLED', True), patch.object(ipsk, 'RATE_LIMIT', {}), \
                patch.object(resident_access, 'SETTINGS_OVERRIDE', {}), \
                patch.object(ipsk.CAPTIVE_SESSIONS, 'get', return_value=MagicMock(mac='00:11:22:33:44:55')), \
                patch.object(ipsk, 'register_resident', side_effect=RuntimeError('fixture-reflected-secret')), \
                patch.object(ipsk, '_public_page') as page, patch('builtins.print') as output:
            handler.do_POST()
        self.assertNotIn('fixture-reflected-secret', str(output.call_args))
        self.assertNotIn('fixture-reflected-secret', str(page.call_args))
        self.assertEqual(page.call_args.args[-1], 503)

    def test_definition_list_actions_are_inside_definition(self):
        row = ui.kv_row('Serial', '<code>123</code>', '<button>Copy</button>')
        self.assertIn('<dd class="kv-value">', row)
        self.assertIn('<button>Copy</button></dd>', row)
        self.assertNotIn('</dd><button>', row)

    def test_enrollment_qr_has_white_background_and_four_module_quiet_zone(self):
        svg = app.qr_svg('https://ha.example.org/enroll/fixture')
        self.assertIn('<rect', svg)
        self.assertIn('fill="white"', svg)

    def test_schema_keeps_revoked_history_and_unique_current_mac_and_email(self):
        env = {'DB_NAME':'fixture','PORTAL_USER':'portal','PORTAL_PASSWORD':'fixture','RW_USER':'ca','RW_PASSWORD':'fixture',
               'RO_USER':'read','RO_PASSWORD':'fixture','ADMIN_HOST':'localhost','ADMIN_PORT':'3306','ADMIN_USER':'admin','ADMIN_PASSWORD':'fixture'}
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        with patch.dict(os.environ, env), patch.object(db_setup.pymysql,'connect',return_value=conn):
            db_setup.main()
        queries = [c.args[0] for c in cur.execute.call_args_list]
        self.assertEqual(sum('GENERATED ALWAYS AS (CASE WHEN active THEN RTRIM(mac_address) ELSE NULL END)' in q for q in queries), 2)
        self.assertTrue(any('CASE WHEN active THEN email ELSE NULL END' in q for q in queries))
        self.assertTrue(any('ADD COLUMN IF NOT EXISTS `expires_at`' in q for q in queries))
        self.assertTrue(any("ADD COLUMN IF NOT EXISTS `label` VARCHAR(100) NOT NULL DEFAULT ''" in q for q in queries))
        self.assertTrue(any('DROP INDEX IF EXISTS `uq_stepca_devices_mac`' in q for q in queries))

class ResidentManagementRegression(unittest.TestCase):
    def render(self, query=None, section="keys"):
        import datetime
        stamp = datetime.datetime(2026, 10, 2, 12, 30, 15, 987654)
        residents = [{"name":"Alex", "email":"alex@example.org", "unit":"101", "ipsk_name":"Living room TV",
                      "mac_address":"00:11:22:33:44:55", "created_at":stamp}]
        keys = [{"id":"active-key", "name":"Living room TV", "status":"active", "ssid_name":"Residents",
                 "associated_user":"Alex"},
                {"id":"expired-key", "name":"Old laptop", "status":"expired", "ssid_name":"Residents",
                 "associated_user":"Jordan"}]
        handler = app.Handler.__new__(app.Handler)
        handler.url = lambda path: path
        handler.page = MagicMock()
        with patch.dict(os.environ, {"PORTAL_DB_HOST":"fixture"}), \
                patch.object(app, "SUPERVISOR_TOKEN", "fixture"), \
                patch.object(app, "saved_options", return_value={"resident_onboarding":{}}), \
                patch.object(ipsk, "resident_inventory", side_effect=lambda search, sort, page: {
                    "rows": [row for row in residents if search.casefold() in " ".join(str(value) for value in row.values()).casefold()],
                    "total": len(residents), "matched": sum(search.casefold() in " ".join(str(value) for value in row.values()).casefold() for row in residents),
                    "page": 1, "pages": 1, "size": 25}), \
                patch.object(ipsk, "list_invites", return_value=[]), \
                patch.object(ipsk, "list_ipsks", return_value=keys) as live_keys, \
                patch.object(ipsk, "get_options", return_value={} ) as options, \
                patch.object(ipsk, "inactive_ipsk_ids", return_value=[]):
            handler.residents_page(query, section=section)
        if section not in ("keys", "devices"):
            live_keys.assert_not_called()
        if section != "create":
            options.assert_not_called()
        return handler.page.call_args.args[1]

    def test_keys_page_contains_only_inventory_and_creation_link(self):
        markup = self.render()
        self.assertIn('href="/ipsk/create"', markup)
        self.assertIn('id="device-keys"', markup)
        self.assertIn("2 Wi-Fi keys", markup)
        for unrelated in ('id="registered-devices"', 'id="create-device-key"',
                          'id="join-codes"', 'id="resident-access-settings"', 'Create invitation code'):
            self.assertNotIn(unrelated, markup)

    def test_devices_have_their_own_search_and_readable_dates(self):
        markup = self.render(section="devices")
        self.assertIn('action="/ipsk/devices"', markup)
        self.assertIn("1 registered device record", markup)
        self.assertIn("2026-10-02 12:30 UTC", markup)
        self.assertNotIn("987654", markup)
        self.assertNotIn('name="key_status"', markup)
        self.assertNotIn('id="device-keys"', markup)
        self.assertIn("No matching device records", self.render({"q": ["nobody"]}, section="devices"))

    def test_each_task_is_a_separate_page_with_current_navigation(self):
        checks = (("create", 'id="create-device-key"'), ("invitations", "Create invitation code"),
                  ("join-codes", 'id="join-codes"'), ("join-codes/settings", 'id="qr-settings"'),
                  ("access", "Save device access"))
        for section, expected in checks:
            with self.subTest(section=section):
                markup = self.render(section=section)
                self.assertIn(expected, markup)
                self.assertEqual(markup.count('aria-current="page"'),
                             0 if section in ("access", "join-codes/settings") else 1)
                self.assertNotIn('id="device-keys"', markup)
                self.assertNotIn('id="registered-devices"', markup)
                if section != "access":
                    self.assertNotIn("Save device access", markup)
                if section != "invitations":
                    self.assertNotIn("Create invitation code", markup)

    def test_search_matches_resident_key_and_network_and_status_filters_keys(self):
        markup = self.render({"q":["jordan"], "key_status":["expired"]})
        table = markup.split('id="device-keys"', 1)[1].split('<tbody role="rowgroup">', 1)[1].split('</tbody>', 1)[0]
        self.assertIn("Old laptop", table)
        self.assertNotIn("Living room TV", table)
        self.assertIn('value="expired" selected', markup)
        network_results = self.render({"q":["Residents"], "key_status":["active"]})
        table = network_results.split('id="device-keys"', 1)[1].split('<tbody role="rowgroup">', 1)[1].split('</tbody>', 1)[0]
        self.assertIn("Living room TV", table)
        self.assertNotIn("Old laptop", table)

    def test_empty_filter_result_has_clear_recovery_and_escaped_search(self):
        markup = self.render({"q":['<script>"'], "key_status":["revoked"]})
        self.assertIn("No matching keys", markup)
        self.assertIn("Clear filters", markup)
        self.assertIn('value="&lt;script&gt;&quot;"', markup)
        self.assertNotIn('<script>"', markup)

    def test_all_ipsk_get_routes_dispatch_to_the_matching_page(self):
        routes = {"/ipsk": "keys", "/ipsk/devices": "devices", "/ipsk/create": "create",
                  "/ipsk/invitations": "invitations", "/ipsk/join-codes": "join-codes",
                  "/settings/ipsk/join-codes": "join-codes/settings", "/settings/ipsk/access": "access"}
        for path, section in routes.items():
            with self.subTest(path=path):
                handler = app.Handler.__new__(app.Handler)
                handler.path = path + "?q=fixture"
                handler.allowed = lambda: True
                handler.residents_page = MagicMock()
                handler.do_GET()
                handler.residents_page.assert_called_once_with({"q": ["fixture"]}, section=section)
                self.assertEqual(handler.current_tab(), "/settings" if path.startswith("/settings") else "/ipsk")

    def test_legacy_bookmark_redirects_and_preserves_filters(self):
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/residents?q=fixture&key_status=active"
        handler.allowed = lambda: True
        handler.redirect = MagicMock()
        handler.do_GET()
        handler.redirect.assert_called_once_with("/ipsk?q=fixture&key_status=active")
        self.assertIn(("/ipsk", "IPSK", "wifi"), app.Handler.TABS)


class RemoteStatusRegression(unittest.TestCase):
    def test_only_explicit_expired_or_revoked_remote_keys_release_slots(self):
        keys = [{'id':'active','status':'active'}, {'id':'expired','status':'expired'},
                {'psk_group_id':'revoked','status':'revoked'}, {'id':'unknown','status':'unknown'},
                {'id':'no-status'}, {'status':'expired'}]
        self.assertEqual(ipsk.inactive_ipsk_ids(keys), ['expired','revoked'])
        cur = MagicMock()
        ipsk.sync_inactive_keys(cur, ['expired'])
        self.assertEqual(cur.execute.call_count, 2)
        self.assertTrue(all(call.args[1] == ('expired',) for call in cur.execute.call_args_list))


class HomeAssistantContractRegression(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiohttp import web
        self.messages = []
        self.auth_ok = True
        self.stall = False
        self.unknown = False
        async def websocket(request):
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            await socket.send_json({"type":"auth_required"})
            auth = await socket.receive_json()
            self.assertEqual(auth, {"type":"auth","access_token":"fixture-token"})
            await socket.send_json({"type":"auth_ok" if self.auth_ok else "auth_invalid"})
            if not self.auth_ok:
                return socket
            async for message in socket:
                command = json.loads(message.data)
                self.messages.append(command)
                if self.stall:
                    continue
                if self.unknown:
                    await socket.send_json({"id":command["id"],"type":"result","success":False,
                                            "error":{"code":"unknown_command","message":"Unknown command"}})
                else:
                    await socket.send_json({"id":999,"type":"event","event":{}})
                    result = {"networks":[]} if command["type"].endswith("options") else []
                    await socket.send_json({"id":command["id"],"type":"result","success":True,"result":result})
            return socket
        server = web.Application()
        server.router.add_get("/core/websocket", websocket)
        self.runner = web.AppRunner(server)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.patches = [patch.object(ipsk,"SUPERVISOR_TOKEN","fixture-token"),
                        patch.object(ipsk,"CORE_WEBSOCKET",f"http://127.0.0.1:{port}/core/websocket")]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        await self.runner.cleanup()
        for item in reversed(self.patches):
            item.stop()

    async def test_authentication_correlated_results_and_unrelated_events(self):
        result = await ipsk._core_call({"type":"step_ca_scep/ipsk/options"},{"type":"step_ca_scep/ipsk/list"})
        self.assertEqual(result,[{"networks":[]},[]])
        self.assertEqual([m["id"] for m in self.messages],[1,2])

    async def test_missing_provider_handlers_explain_required_integration(self):
        self.unknown = True
        with self.assertRaisesRegex(RuntimeError,"Step CA companion integration"):
            await ipsk._core_call({"type":"step_ca_scep/ipsk/options"})

    async def test_stalled_websocket_reply_hits_whole_exchange_deadline(self):
        self.stall = True
        with patch.object(ipsk, "CORE_RPC_TIMEOUT", .1):
            with self.assertRaisesRegex(RuntimeError, "did not respond in time"):
                await ipsk._core_call({"type":"step_ca_scep/ipsk/options"})

    async def test_rejected_home_assistant_authentication_never_sends_commands(self):
        self.auth_ok = False
        with self.assertRaisesRegex(RuntimeError,"authentication failed"):
            await ipsk._core_call({"type":"step_ca_scep/ipsk/options"})
        self.assertEqual(self.messages,[])


if __name__ == '__main__':
    unittest.main()
