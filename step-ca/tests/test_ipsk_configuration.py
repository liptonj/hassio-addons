"""IPSK configuration and independent provider checks, using local fixtures."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import identity_settings
import ipsk
import resident_access as access
import settings_menu

DIRECTORY = {"duo_group_id": "DG" + "A" * 18,
             "duo_admin_hostname": "api-fixture.duosecurity.com",
             "duo_admin_integration_key": "DI" + "A" * 18,
             "duo_admin_secret": "private-directory-secret"}
AUTH = {"duo_client_id": "DI" + "B" * 18,
        "duo_client_secret": "private-auth-secret",
        "duo_api_hostname": "api-fixture.duosecurity.com",
        "duo_redirect_uri": "https://ha.example.org/api/step_ca_scep/portal?action=duo_callback"}
CHOICES = {"networks": [{"id": "N_fixture", "name": "Fixture network"}],
           "ssids": [{"number": 0, "name": "Resident Wi-Fi"}],
           "group_policies": [{"id": "42", "name": "Registered residents"}]}
ONBOARDING = {"enabled": True, "invite_required": False, "network_id": "N_fixture",
              "ssid_number": 0, "group_policy_id": "42", "duration_hours": 24}


class IPSKConfigurationTests(unittest.TestCase):
    def handler(self, path, form=None):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        handler.redirect = MagicMock()
        if form is not None:
            body = urlencode({"csrf": app.CSRF_TOKEN, **form}).encode()
            handler.headers["Content-Length"] = str(len(body))
            handler.rfile = io.BytesIO(body)
        return handler

    def test_directory_loads_without_wifi_or_authentication_configuration(self):
        client = MagicMock()
        client.get_group.return_value = {"status": "active"}
        client.get_group_users_iterator.return_value = iter([
            {"user_id": "DUfixture", "username": "<Resident>"}])
        # Required IPSK authentication is intentionally incomplete.
        config = {**DIRECTORY, "sign_in_required": True, "network_id": ""}
        handler = self.handler("/settings/identity/directory/test", {})
        with patch.object(app, "saved_options", return_value={"resident_onboarding": config}), \
                patch.object(access, "admin_client", return_value=client), \
                patch.object(app, "supervisor") as writes:
            handler.handle_post()
        markup = handler.send.call_args.args[1]
        self.assertIn("1 permitted users loaded", markup)
        self.assertIn("&lt;Resident&gt;", markup)
        self.assertNotIn(DIRECTORY["duo_admin_secret"], markup)
        writes.assert_not_called()
        client.get_users.assert_not_called()

    def test_authentication_check_is_independent_and_does_not_start_sign_in(self):
        handler = self.handler("/settings/identity/authentication/test", {})
        client = MagicMock()
        with patch.object(app, "saved_options", return_value={"resident_onboarding": AUTH}), \
                patch.object(access, "universal_client", return_value=client), \
                patch.object(app, "supervisor") as writes:
            handler.handle_post()
        self.assertIn("Duo connection succeeded", handler.send.call_args.args[1])
        client.health_check.assert_called_once_with()
        client.create_auth_url.assert_not_called()
        writes.assert_not_called()

    def test_provider_error_does_not_reflect_secrets_and_offers_retry(self):
        for kind, config, method in (("directory", DIRECTORY, "group_members"),
                                     ("authentication", AUTH, "universal_client")):
            handler = self.handler("/settings/identity/" + kind + "/test", {})
            with patch.object(app, "saved_options", return_value={"resident_onboarding": config}), \
                    patch.object(access, method, side_effect=RuntimeError("private-provider-response")):
                handler.handle_post()
            markup = handler.send.call_args.args[1]
            self.assertIn("connection check failed", markup)
            self.assertIn("/" + kind + "/test", markup)
            self.assertNotIn("private-provider-response", markup)

    def test_empty_directory_explains_how_to_add_members(self):
        handler = self.handler("/settings/identity/directory/test", {})
        with patch.object(app, "saved_options", return_value={"resident_onboarding": DIRECTORY}), \
                patch.object(access, "group_members", return_value=[]):
            handler.handle_post()
        self.assertIn("Add members in Duo", handler.send.call_args.args[1])

    def test_missing_directory_credentials_fail_before_any_provider_request(self):
        handler = self.handler("/settings/identity/directory/test", {})
        with patch.object(app, "saved_options", return_value={}), \
                patch.object(access, "group_members") as fetch:
            handler.handle_post()
        fetch.assert_not_called()
        self.assertIn("Enter the permitted Duo group ID", handler.send.call_args.args[1])

    def test_checks_and_network_save_require_csrf(self):
        for route in ("/settings/identity/authentication/test", "/settings/identity/directory/test", "/settings/ipsk/network/save"):
            handler = self.handler(route, {"csrf": "invalid"})
            with patch.object(app, "saved_options") as read:
                handler.handle_post()
            read.assert_not_called()
            self.assertEqual(handler.send.call_args.args[0], 403)

    def test_network_editor_exposes_all_onboarding_fields_and_keeps_zero_ssid(self):
        handler = self.handler("/settings/ipsk/network")
        with patch.object(app, "saved_options", return_value={"resident_onboarding": ONBOARDING}), \
                patch.object(app, "SUPERVISOR_TOKEN", "fixture"), \
                patch.object(ipsk, "get_options", return_value=CHOICES):
            handler.do_GET()
        markup = handler.send.call_args.args[1]
        for field in settings_menu.IPSK_NETWORK_FIELDS:
            self.assertIn('name="' + field + '"', markup)
        self.assertIn('<option value="0" selected>Resident Wi-Fi', markup)
        self.assertIn("Load network options", markup)

    def test_save_changes_only_network_fields_and_requires_restart(self):
        config = {**ONBOARDING, **DIRECTORY, **AUTH, "guest_ssid": "Guest"}
        form = {**ONBOARDING, "enabled": "1", "invite_required": "1",
                "duration_hours": "0", "duo_client_secret": "injected"}
        handler = self.handler("/settings/ipsk/network/save", form)
        handler.ipsk_network_page = MagicMock()
        with patch.object(app, "saved_options", return_value={"database": "mariadb", "resident_onboarding": config}), \
                patch.object(ipsk, "get_options", return_value=CHOICES), \
                patch.object(app, "supervisor") as write:
            handler.handle_post()
        saved = write.call_args.args[2]["options"]["resident_onboarding"]
        self.assertEqual(saved, {**config, "invite_required": True, "duration_hours": 0})
        handler.ipsk_network_page.assert_called_once_with({"saved": ["1"]})

    def test_bad_network_values_cannot_save_and_keep_draft(self):
        for bad in ({"ssid_number": "15"}, {"duration_hours": "-1"},
                    {"duration_hours": "bad"}, {"group_policy_id": "forged"},
                    {"network_id": "unavailable"}, {"network_id": ""}):
            handler = self.handler("/settings/ipsk/network/save", {**ONBOARDING, "enabled": "1", **bad})
            handler.ipsk_network_page = MagicMock()
            with patch.object(app, "saved_options", return_value={"database": "mariadb", "resident_onboarding": {}}), \
                    patch.object(ipsk, "get_options", return_value=CHOICES), \
                    patch.object(app, "supervisor") as write:
                handler.handle_post()
            write.assert_not_called()
            self.assertEqual(handler.ipsk_network_page.call_args.kwargs["draft"][next(iter(bad))], next(iter(bad.values())))

    def test_onboarding_cannot_enable_without_mariadb(self):
        handler = self.handler("/settings/ipsk/network/save", {**ONBOARDING, "enabled": "1"})
        handler.ipsk_network_page = MagicMock()
        with patch.object(app, "saved_options", return_value={"database": "embedded"}), \
                patch.object(app, "supervisor") as write:
            handler.handle_post()
        write.assert_not_called()
        self.assertIn("MariaDB", str(handler.ipsk_network_page.call_args.kwargs["error"]))

    def test_device_limit_is_validated_even_with_all_access_modes_off(self):
        for limit in (0, 51, "invalid"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                access.validate_settings({"max_devices_per_resident": limit})

    def test_captive_access_and_provider_forms_preserve_ingress(self):
        for route in ("/settings/captive-portal/authentication", "/settings/identity/authentication", "/settings/identity/directory"):
            handler = self.handler(route)
            with patch.object(app, "saved_options", return_value={"resident_onboarding": {**DIRECTORY, **AUTH}}):
                handler.do_GET()
            markup = handler.send.call_args.args[1]
            self.assertEqual(handler.send.call_args.args[0], 200)
            for field in identity_settings.SECRET_FIELDS:
                self.assertNotIn({**DIRECTORY, **AUTH}[field], markup)
            self.assertIn('action="/api/hassio_ingress/fixture/settings/', markup)

    def test_callback_error_preserves_draft_up_to_schema_limit(self):
        callback = AUTH["duo_redirect_uri"] + "&invalid=" + "a" * 800
        handler = self.handler("/settings/identity/authentication/save", {"duo_redirect_uri": callback})
        handler.identity_page = MagicMock()
        with patch.object(app, "saved_options", return_value={"resident_onboarding": AUTH}), \
                patch.object(app, "supervisor") as write:
            handler.handle_post()
        write.assert_not_called()
        self.assertEqual(handler.identity_page.call_args.kwargs["draft"]["duo_redirect_uri"], callback)


if __name__ == "__main__":
    unittest.main()
