"""Captive onboarding gates; all external Wi-Fi and database calls are mocked."""

import http.client
import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import captive
import ipsk
import db_setup


BASE_GRANT = "https://n123.network-auth.com/splash/grant?token=example"
HARDWARE_MAC = "00:11:22:33:44:55"


class CaptivePolicy(unittest.TestCase):
    def test_normalizes_supported_hardware_addresses(self):
        for address in ("00:11:22:AB:CD:EF", "00-11-22-ab-cd-ef", "001122abcdef", "0011.22ab.cdef"):
            self.assertEqual(captive.hardware_mac(address), "00:11:22:ab:cd:ef")

    def test_rejects_every_locally_administered_unicast_prefix(self):
        for prefix in range(256):
            if prefix & 3 == 2:
                with self.subTest(prefix=prefix), self.assertRaises(captive.DeviceAddressError):
                    captive.hardware_mac(f"{prefix:02x}:11:22:33:44:55")

    def test_rejects_missing_malformed_multicast_and_zero_addresses(self):
        for address in (None, "", "00:11", "00::11:22:33:44:55", "0011-2233-4455",
                        "00:11:22:33:44:5Z", "01:11:22:33:44:55", "ff:ff:ff:ff:ff:ff",
                        "00:00:00:00:00:00", "00:11:22:33:44:55<script>"):
            with self.subTest(address=address), self.assertRaises(captive.DeviceAddressError):
                captive.hardware_mac(address)

    def test_grant_preserves_meraki_fields_and_encodes_continuation(self):
        result = captive.grant_url(BASE_GRANT + "&duration=9999&continue_url=old",
                                   "https://example.org/path?a=1&b=2")
        query = parse_qs(urlsplit(result).query)
        self.assertEqual(query["token"], ["example"])
        self.assertEqual(query["duration"], ["300"])
        self.assertEqual(query["continue_url"], ["https://example.org/path?a=1&b=2"])

    def test_rejects_untrusted_grant_targets(self):
        for url in ("http://n123.network-auth.com/splash/grant",
                    "https://network-auth.com.evil.org/splash/grant",
                    "https://evil.org/splash/grant", "https://n123.network-auth.com:444/splash/grant",
                    "https://user:pass@n123.network-auth.com/splash/grant",
                    "https://n123.network-auth.com/other", BASE_GRANT + "#fragment",
                    BASE_GRANT + "\r\nHeader:value"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                captive.grant_url(url)

    def test_rejects_non_web_continuation(self):
        with self.assertRaises(ValueError):
            captive.grant_url(BASE_GRANT, "javascript:alert(1)")

    def test_sessions_are_bounded_expire_and_can_be_consumed(self):
        now = [0]
        sessions = captive.CaptiveSessions(ttl=10, capacity=1, clock=lambda: now[0])
        token = sessions.create(HARDWARE_MAC, BASE_GRANT)
        self.assertEqual(sessions.get(token).mac, HARDWARE_MAC)
        with self.assertRaises(RuntimeError):
            sessions.create(HARDWARE_MAC, BASE_GRANT)
        now[0] = 10
        self.assertIsNone(sessions.get(token))
        token = sessions.create(HARDWARE_MAC, BASE_GRANT)
        sessions.discard(token)
        self.assertIsNone(sessions.get(token))

    def test_random_mac_cannot_reach_database_or_key_creation(self):
        with patch.object(ipsk, "db_connect") as db, patch.object(ipsk, "create_ipsk") as create:
            with self.assertRaises(captive.DeviceAddressError):
                ipsk.register_resident("Test Resident", "test@example.org", "101", "INVITE",
                                       "192.0.2.1", "02:11:22:33:44:55")
        db.assert_not_called()
        create.assert_not_called()


class CaptiveHttpFlow(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(ipsk, "PORTAL_ENABLED", True),
                        patch.object(ipsk, "CAPTIVE_SESSIONS", captive.CaptiveSessions()),
                        patch.object(ipsk.PublicPortalHandler, "allowed_clients", {"127.0.0.1"}),
                        patch.object(ipsk, "RATE_LIMIT", {})]
        for item in self.patches:
            item.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ipsk.PublicPortalHandler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        for item in reversed(self.patches):
            item.stop()

    def request(self, method="GET", path="/portal", form=None, cookie=""):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        headers = {"Cookie": cookie}
        body = urlencode(form) if form is not None else None
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    def landing(self, mac=HARDWARE_MAC):
        return self.request(path="/portal?" + urlencode({
            "client_mac": mac, "base_grant_url": BASE_GRANT,
            "user_continue_url": "https://example.org/",
        }))

    def test_direct_visit_shows_setup_instructions_without_form(self):
        status, _, page = self.request()
        self.assertEqual(status, 200)
        self.assertIn("Connect to setup Wi-Fi", page)
        self.assertNotIn("<form", page)

    def test_private_mac_landing_has_recovery_and_no_registration_or_grant(self):
        with patch.object(ipsk, "register_resident") as register:
            status, _, page = self.landing("da:11:22:33:44:55")
        self.assertEqual(status, 403)
        self.assertIn("Private Wi-Fi Address", page)
        self.assertIn("Use device MAC", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("Finish captive portal", page)
        register.assert_not_called()

    def test_missing_mac_or_grant_cannot_open_registration(self):
        for query in ({"base_grant_url": BASE_GRANT}, {"client_mac": HARDWARE_MAC}):
            status, _, page = self.request(path="/portal?" + urlencode(query))
            self.assertIn(status, (400, 403))
            self.assertNotIn("<form", page)

    def test_duplicate_redirect_parameters_are_rejected(self):
        status, _, page = self.request(path="/portal?" + urlencode({
            "client_mac": HARDWARE_MAC, "base_grant_url": BASE_GRANT,
        }) + "&client_mac=02:11:22:33:44:55")
        self.assertEqual(status, 400)
        self.assertNotIn("<form", page)

    def test_forged_csrf_without_captive_session_is_rejected(self):
        with patch.object(ipsk, "register_resident") as register:
            status, _, _ = self.request("POST", form={"csrf": "fake"}, cookie="portal_csrf=fake")
        self.assertEqual(status, 403)
        register.assert_not_called()

    def test_success_uses_server_mac_and_consumes_session(self):
        status, headers, page = self.landing()
        self.assertEqual(status, 200)
        token = re.search(r'name=csrf value="([^"]+)"', page)[1]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        form = {"csrf": token, "name": "Test Resident", "email": "test@example.org",
                "unit": "101", "invite": "INVITE", "client_mac": "02:11:22:33:44:55"}
        with patch.object(ipsk, "register_resident", return_value={
            "name": "Test Resident", "ssid": "Resident Wi-Fi", "passphrase": "fixture-password",
        }) as register:
            status, headers, page = self.request("POST", form=form, cookie=cookie)
            self.assertEqual(status, 200)
            self.assertEqual(register.call_args.args[-1], HARDWARE_MAC)
            self.assertIn("Finish captive portal", page)
            self.assertIn("duration=300", page)
            self.assertIn("Max-Age=0", headers["Set-Cookie"])
            status, _, _ = self.request("POST", form=form, cookie=cookie)
            self.assertEqual(status, 403)
            self.assertEqual(register.call_count, 1)


    def test_self_service_identity_and_device_limits_have_separate_budgets(self):
        def reply(engine, handler, action, form, ip):
            engine._public_page(handler, "Fixture response", "Fixture")
        with patch.object(ipsk.resident_access, "enabled", return_value=True), \
                patch.object(ipsk.resident_access, "handle_post", side_effect=reply):
            for _ in range(6):
                status, _, _ = self.request("POST", "/portal?action=create_device", {"csrf":"fixture"})
                self.assertEqual(status, 200)
            status, _, _ = self.request("POST", "/portal?action=duo_login", {"csrf":"fixture"})
            self.assertEqual(status, 200)
        self.assertEqual(len(ipsk.RATE_LIMIT[("127.0.0.1", "device")]), 6)
        self.assertEqual(len(ipsk.RATE_LIMIT[("127.0.0.1", "identity")]), 1)


class ResidentPersistence(unittest.TestCase):
    def setUp(self):
        remote = patch.object(ipsk, "inactive_ipsk_ids", return_value=[])
        remote.start()
        self.addCleanup(remote.stop)

    def test_registration_persists_hardware_mac_and_accepts_optional_empty_unit(self):
        conn, cursor = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [{"acquired": 1}, None, None, {"id": 42}]
        settings = {"network_id": "N_fixture", "ssid_number": 1, "duration_hours": 0}
        with patch.dict(os.environ, {"RESIDENT_SETTINGS_JSON": json.dumps(settings)}), \
                patch.object(ipsk, "INVITE_REQUIRED", True), \
                patch.object(ipsk, "db_connect", return_value=conn), \
                patch.object(ipsk, "create_ipsk", return_value={
                    "id": "fixture-key", "passphrase": "fixture-password", "ssid_name": "Fixture Wi-Fi",
                }) as create:
            result = ipsk.register_resident("Test Resident", "test@example.org", "", "INVITE",
                                            "192.0.2.1", "00-11-22-33-44-55")
        self.assertEqual(result["ssid"], "Fixture Wi-Fi")
        inserts = [c.args for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT")]
        self.assertEqual(len(inserts), 1)
        self.assertIn("source_ip, mac_address", inserts[0][0])
        self.assertEqual(inserts[0][1][-2:], ("192.0.2.1", HARDWARE_MAC))
        create.assert_called_once()
        conn.commit.assert_called_once()
        self.assertTrue(any("SET used_at" in c.args[0] for c in cursor.execute.call_args_list))

    def test_existing_device_cannot_create_another_key_or_consume_invite(self):
        conn, cursor = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [{"acquired": 1}, None, {"id": 1}]
        with patch.dict(os.environ, {"RESIDENT_SETTINGS_JSON": '{"network_id":"N_fixture"}'}), \
                patch.object(ipsk, "INVITE_REQUIRED", True), \
                patch.object(ipsk, "db_connect", return_value=conn), \
                patch.object(ipsk, "create_ipsk") as create:
            with self.assertRaisesRegex(ValueError, "already registered"):
                ipsk.register_resident("Test Resident", "test@example.org", "101", "INVITE",
                                       "192.0.2.1", HARDWARE_MAC)
        create.assert_not_called()
        conn.commit.assert_not_called()
        self.assertFalse(any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list))

    def test_database_setup_selects_stepca_schema_and_upgrades_columns(self):
        env = {"DB_NAME": "stepca_fixture", "PORTAL_USER": "portal", "PORTAL_PASSWORD": "fixture",
               "RW_USER": "ca", "RW_PASSWORD": "fixture", "RO_USER": "read", "RO_PASSWORD": "fixture",
               "ADMIN_HOST": "localhost", "ADMIN_PORT": "3306", "ADMIN_USER": "admin", "ADMIN_PASSWORD": "fixture"}
        conn, cursor = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with patch.dict(os.environ, env), patch.object(db_setup.pymysql, "connect", return_value=conn):
            db_setup.main()
        conn.select_db.assert_called_once_with("stepca_fixture")
        queries = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertTrue(any("ADD COLUMN IF NOT EXISTS `source_ip`" in q for q in queries))
        self.assertTrue(any("ADD COLUMN IF NOT EXISTS `mac_address`" in q for q in queries))
        self.assertTrue(any("ADD UNIQUE INDEX IF NOT EXISTS" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
