"""Guest, setup and device join QRs; no external service calls."""

import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import ipsk
import yaml


class WifiQr(unittest.TestCase):
    def test_payload_escapes_all_wifi_delimiters_and_preserves_spaces(self):
        self.assertEqual(ipsk.wifi_qr_payload(' Home;WiFi:"\\ ', ' pass;word,:"\\ '),
                         'WIFI:T:WPA;S: Home\\;WiFi\\:\\"\\\\ ;P: pass\\;word\\,\\:\\"\\\\ ;;')

    def test_utf8_ssid_byte_limit_and_invalid_secrets(self):
        ipsk.validate_wifi_credentials("界" * 10, "sample-password")
        for ssid, secret in (("界" * 11, "sample-password"), ("", "sample-password"),
                             ("Wifi", "short"), ("Wifi", "pass\nword"), ("Wifi", "é" * 8)):
            with self.subTest(ssid=ssid, secret=secret), self.assertRaises(ValueError):
                ipsk.validate_wifi_credentials(ssid, secret)
        ipsk.validate_wifi_credentials("Wifi", "a" * 64)

    def test_image_is_a_valid_svg_with_no_scripts(self):
        image = ipsk.wifi_qr_image("Guest Wi-Fi", "guest-password")
        self.assertTrue(image.startswith("data:image/svg+xml;base64,"))
        root = ET.fromstring(base64.b64decode(image.split(",", 1)[1]))
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertTrue(root.findall(".//{http://www.w3.org/2000/svg}path"))
        self.assertTrue(any(rect.get("fill") == "white" for rect in
                            root.findall(".//{http://www.w3.org/2000/svg}rect")))
        self.assertFalse(root.findall(".//{http://www.w3.org/2000/svg}script"))

    def test_card_has_download_and_escapes_names_without_saved_secret_field(self):
        card = ipsk.wifi_join_card("Guest <access>", "Guest <wifi>", "sample-password", "Scan & join",
                                   filename="guest-wifi.svg")
        self.assertIn('download="guest-wifi.svg"', card)
        self.assertIn("Guest &lt;access&gt;", card)
        self.assertIn("Scan &amp; join", card)
        self.assertNotIn("sample-password", card)
        self.assertNotIn("<input", card)

    def test_device_qr_uses_current_ssid_and_revealed_key(self):
        with patch.object(ipsk, "core_call", return_value=[{
                "id": "key1", "name": "TV", "status": "active", "ssid_name": "Actual network",
        }]), patch.object(ipsk, "reveal_ipsk", return_value="current-password") as reveal:
            details = ipsk.ipsk_join_details("key1")
        self.assertEqual(details["ssid"], "Actual network")
        self.assertEqual(details["passphrase"], "current-password")
        reveal.assert_called_once_with("key1")

    def test_inactive_keys_cannot_reveal_for_qr(self):
        for status in ("revoked", "expired", "unknown", None):
            with self.subTest(status=status), patch.object(ipsk, "core_call", return_value=[{
                    "status": status, "ssid_name": "Wifi",
            }]), patch.object(ipsk, "reveal_ipsk") as reveal:
                with self.assertRaises(ValueError):
                    ipsk.ipsk_join_details("key1")
                reveal.assert_not_called()

    def test_missing_ssid_does_not_generate_a_guessed_network_qr(self):
        with patch.object(ipsk, "core_call", return_value=[{"status": "active"}]), \
                patch.object(ipsk, "reveal_ipsk") as reveal:
            with self.assertRaisesRegex(ValueError, "network name"):
                ipsk.ipsk_join_details("key1")
        reveal.assert_not_called()

    def test_options_schema_covers_both_qr_pairs(self):
        config = yaml.safe_load((Path(__file__).resolve().parents[1] / "config.yaml").read_text())
        for key in ("guest_ssid", "guest_psk", "setup_ssid", "setup_psk"):
            self.assertIn(key, config["options"]["resident_onboarding"])
            self.assertIn(key, config["schema"]["resident_onboarding"])


class AdminQrRoutes(unittest.TestCase):
    def handler(self, path, values):
        body = urlencode({"csrf": app.CSRF_TOKEN, **values}).encode()
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(body)), "Content-Type": "application/x-www-form-urlencoded"}
        handler.rfile = io.BytesIO(body)
        handler.residents_page = MagicMock()
        handler.send = MagicMock()
        return handler

    def test_saving_qr_settings_preserves_existing_secrets_and_other_options(self):
        options = {"ca_name": "Fixture CA", "resident_onboarding": {
            "network_id": "N_fixture", "invite_required": True,
            "guest_ssid": "Guest", "guest_psk": "saved-guest-password",
            "setup_ssid": "Setup", "setup_psk": "saved-setup-password",
        }}
        handler = self.handler("/residents/qr/settings", {
            "guest_ssid": " Guest ", "guest_psk": "", "setup_ssid": "Setup", "setup_psk": "",
        })
        with patch.object(app, "saved_options", return_value=options), patch.object(app, "supervisor") as supervisor:
            handler.handle_post()
        saved = supervisor.call_args.args[2]["options"]
        self.assertEqual(saved["ca_name"], "Fixture CA")
        self.assertEqual(saved["resident_onboarding"]["guest_psk"], "saved-guest-password")
        self.assertEqual(saved["resident_onboarding"]["guest_ssid"], " Guest ")
        self.assertTrue(saved["resident_onboarding"]["invite_required"])
        handler.residents_page.assert_called_once_with({"qr_saved": ["1"]}, section="join-codes/settings")

    def test_clearing_a_network_clears_its_saved_secret(self):
        handler = self.handler("/residents/qr/settings", {"guest_ssid": "", "setup_ssid": ""})
        with patch.object(app, "saved_options", return_value={"resident_onboarding": {
                "guest_ssid": "Guest", "guest_psk": "saved-password",
        }}), patch.object(app, "supervisor") as supervisor:
            handler.handle_post()
        saved = supervisor.call_args.args[2]["options"]["resident_onboarding"]
        self.assertEqual(saved["guest_ssid"], "")
        self.assertEqual(saved["guest_psk"], "")

    def test_guest_and_setup_cannot_use_identical_credentials(self):
        handler = self.handler("/residents/qr/settings", {
            "guest_ssid": "Wifi", "guest_psk": "same-password",
            "setup_ssid": "Wifi", "setup_psk": "same-password",
        })
        with patch.object(app, "saved_options", return_value={}), patch.object(app, "supervisor") as supervisor:
            handler.handle_post()
        supervisor.assert_not_called()
        self.assertIn("different guest", str(handler.residents_page.call_args.kwargs["error"]))

    def test_invalid_qr_password_does_not_save(self):
        handler = self.handler("/residents/qr/settings", {"guest_ssid": "Wifi", "guest_psk": "short"})
        with patch.object(app, "saved_options", return_value={}), patch.object(app, "supervisor") as supervisor:
            handler.handle_post()
        supervisor.assert_not_called()
        self.assertTrue(str(handler.residents_page.call_args.kwargs["error"]))

    def test_create_for_other_device_automatically_shows_its_qr(self):
        handler = self.handler("/ipsk/create", {
            "name": "Living room TV", "network_id": "N_fixture", "ssid_number": "0",
            "passphrase": " spaced-password ", "duration_hours": "0", "group_policy_id": "101",
        })
        details = {"id": "key1", "name": "Living room TV", "ssid": "Wifi", "passphrase": " spaced-password "}
        with patch.object(ipsk, "get_options", return_value={
                "networks": [{"id": "N_fixture"}], "ssids": [{"number": 0}], "group_policies": [{"id": "101"}],
        }), patch.object(ipsk, "create_admin_ipsk", return_value={"id": "key1"}) as create, \
                patch.object(ipsk, "ipsk_join_details", return_value=details):
            handler.handle_post()
        self.assertEqual(create.call_args.args[3], " spaced-password ")
        handler.residents_page.assert_called_once_with({}, created_key="key1", join_key=details, section="create")

    def test_qr_retrieval_failure_reports_created_key_without_creating_again(self):
        handler = self.handler("/ipsk/create", {
            "name": "TV", "network_id": "N_fixture", "ssid_number": "0", "duration_hours": "0", "group_policy_id": "101",
        })
        with patch.object(ipsk, "get_options", return_value={
                "networks": [{"id": "N_fixture"}], "ssids": [{"number": 0}], "group_policies": [{"id": "101"}],
        }), patch.object(ipsk, "create_admin_ipsk", return_value={"id": "key1"}) as create, \
                patch.object(ipsk, "ipsk_join_details", side_effect=ValueError("unavailable")):
            handler.handle_post()
        create.assert_called_once()
        self.assertEqual(handler.residents_page.call_args.kwargs["created_key"], "key1")
        self.assertIn("key was created", str(handler.residents_page.call_args.kwargs["error"]))

    def test_show_qr_action_retrieves_existing_key_without_creating(self):
        handler = self.handler("/ipsk/key/action", {"ipsk_id": "key1", "action": "qr"})
        details = {"id": "key1", "name": "TV", "ssid": "Wifi", "passphrase": "sample-password"}
        with patch.object(ipsk, "ipsk_join_details", return_value=details), \
                patch.object(ipsk, "create_admin_ipsk") as create:
            handler.handle_post()
        create.assert_not_called()
        handler.residents_page.assert_called_once_with({}, join_key=details)

    def test_qr_settings_still_require_admin_csrf(self):
        handler = self.handler("/residents/qr/settings", {"csrf": "wrong"})
        with patch.object(app, "supervisor") as supervisor:
            handler.handle_post()
        supervisor.assert_not_called()
        self.assertEqual(handler.send.call_args.args[0], 403)


if __name__ == "__main__":
    unittest.main()
