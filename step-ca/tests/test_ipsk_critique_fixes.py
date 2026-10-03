"""Recovery and task handoffs from the IPSK critique; service calls stay mocked."""

import datetime
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import guidance
import ipsk
import resident_access as access

OPTIONS = {
    "networks": [{"id": "N_fixture", "name": "Home"}],
    "ssids": [{"number": 0, "name": "Home Wi-Fi"}],
    "group_policies": [{"id": "101", "name": "Resident access"}],
}


class CritiqueFixes(unittest.TestCase):
    def handler(self, path, values):
        body = urlencode({"csrf": app.CSRF_TOKEN, **values}).encode()
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {
            "Content-Length": str(len(body)),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        handler.rfile = io.BytesIO(body)
        handler.residents_page = MagicMock()
        handler.redirect = MagicMock()
        handler.send = MagicMock()
        return handler

    def render(
        self, section, query=None, draft=None, error="", keys=None, records=None
    ):
        handler = app.Handler.__new__(app.Handler)
        handler.url = lambda path: path
        handler.page = MagicMock()
        inventory = {
            "rows": records or [],
            "total": len(records or []),
            "matched": len(records or []),
            "page": 1,
            "pages": 1,
            "size": 25,
        }
        with (
            patch.dict(os.environ, {"PORTAL_DB_HOST": "fixture"}),
            patch.object(app, "SUPERVISOR_TOKEN", "fixture"),
            patch.object(
                app,
                "saved_options",
                return_value={
                    "resident_onboarding": {
                        "network_id": "N_fixture",
                        "duo_group_id": "saved-group",
                    }
                },
            ),
            patch.object(access, "settings", return_value={"network_id": "N_fixture"}),
            patch.object(ipsk, "get_options", return_value=OPTIONS),
            patch.object(ipsk, "list_ipsks", return_value=keys or []),
            patch.object(ipsk, "inactive_ipsk_ids", return_value=[]),
            patch.object(ipsk, "resident_inventory", return_value=inventory),
            patch.object(ipsk, "list_invites", return_value=[]),
        ):
            app.Handler.residents_page(
                handler, query, section=section, draft=draft, error=error
            )
        return handler.page.call_args.args[1]

    def test_admin_password_error_preserves_other_fields_and_never_reflects_secret(
        self,
    ):
        values = {
            "name": "TV <script>",
            "user": 'A"lex',
            "unit": "101",
            "network_id": "N_fixture",
            "ssid_number": "0",
            "group_policy_id": "101",
            "duration_hours": "168",
            "passphrase": "short",
        }
        handler = self.handler("/ipsk/create", values)
        with patch.object(ipsk, "create_admin_ipsk") as create:
            handler.handle_post()
        create.assert_not_called()
        args, kwargs = handler.residents_page.call_args
        self.assertEqual(kwargs["error"].field, "passphrase")
        self.assertEqual(
            kwargs["draft"],
            {k: v for k, v in values.items() if k not in ("network_id", "passphrase")},
        )
        page = self.render("create", args[0], kwargs["draft"], kwargs["error"])
        for value in (
            "TV &lt;script&gt;",
            "A&quot;lex",
            'value="101"',
            'value="168"',
            'value="0" selected',
            'value="101" selected',
        ):
            self.assertIn(value, page)
        self.assertIn('aria-invalid="true"', page)
        self.assertIn('id="passphrase-error"', page)
        self.assertNotIn('value="short"', page)
        self.assertNotIn("passphrase", kwargs["draft"])

    def test_unknown_policy_is_rejected_before_provisioning(self):
        handler = self.handler(
            "/ipsk/create",
            {
                "name": "TV",
                "network_id": "N_fixture",
                "ssid_number": "0",
                "group_policy_id": "missing",
            },
        )
        with (
            patch.object(ipsk, "get_options", return_value=OPTIONS),
            patch.object(ipsk, "create_admin_ipsk") as create,
        ):
            handler.handle_post()
        create.assert_not_called()
        self.assertEqual(
            handler.residents_page.call_args.kwargs["error"].field, "group_policy_id"
        )

    def test_qr_error_retains_names_but_not_passwords(self):
        handler = self.handler(
            "/ipsk/qr/settings",
            {"guest_ssid": "Guest", "guest_psk": "short", "setup_ssid": "Setup"},
        )
        with (
            patch.object(app, "saved_options", return_value={}),
            patch.object(app, "supervisor") as save,
        ):
            handler.handle_post()
        save.assert_not_called()
        kwargs = handler.residents_page.call_args.kwargs
        self.assertEqual(
            kwargs["draft"], {"guest_ssid": "Guest", "setup_ssid": "Setup"}
        )
        page = self.render(
            "join-codes/settings", draft=kwargs["draft"], error=kwargs["error"]
        )
        self.assertIn('value="Guest"', page)
        self.assertIn('id="guest_psk-error"', page)
        self.assertNotIn('value="short"', page)

    def test_hidden_duo_settings_survive_saving_with_both_modes_off(self):
        saved = {
            "network_id": "N_fixture",
            "duo_group_id": "saved-group",
            "duo_admin_secret": "saved-secret",
            "duo_client_id": "saved-client",
        }
        handler = self.handler(
            "/ipsk/access/settings",
            {"self_service_enabled": "1", "max_devices_per_resident": "7"},
        )
        with (
            patch.object(
                app, "saved_options", return_value={"resident_onboarding": saved}
            ),
            patch.object(app, "supervisor") as save,
            patch.object(access, "SETTINGS_OVERRIDE", None),
        ):
            handler.handle_post()
        settings = save.call_args.args[2]["options"]["resident_onboarding"]
        self.assertEqual(settings["duo_group_id"], "saved-group")
        self.assertEqual(settings["duo_admin_secret"], "saved-secret")
        self.assertEqual(settings["duo_client_id"], "saved-client")
        self.assertFalse(settings["sign_in_required"])
        self.assertFalse(settings["no_sign_in_user_list"])

    def test_access_error_keeps_mode_and_non_secret_fields(self):
        handler = self.handler(
            "/ipsk/access/settings",
            {
                "sign_in_required": "1",
                "duo_group_id": "invalid-group",
                "duo_client_secret": "new-secret",
                "max_devices_per_resident": "7",
            },
        )
        with (
            patch.object(
                app,
                "saved_options",
                return_value={"resident_onboarding": {"network_id": "N_fixture"}},
            ),
            patch.object(app, "supervisor") as save,
        ):
            handler.handle_post()
        save.assert_not_called()
        kwargs = handler.residents_page.call_args.kwargs
        self.assertTrue(kwargs["draft"]["sign_in_required"])
        self.assertNotIn("duo_client_secret", kwargs["draft"])
        page = self.render("access", draft=kwargs["draft"], error=kwargs["error"])
        self.assertIn('value="invalid-group"', page)
        self.assertIn('id="duo_group_id-error"', page)
        self.assertNotIn("new-secret", page)

    def test_access_provider_failure_still_returns_recoverable_draft(self):
        handler = self.handler(
            "/ipsk/access/settings",
            {"self_service_enabled": "1", "max_devices_per_resident": "7"},
        )
        with patch.object(
            app, "saved_options", side_effect=RuntimeError("Supervisor unavailable")
        ):
            handler.handle_post()
        kwargs = handler.residents_page.call_args.kwargs
        self.assertEqual(str(kwargs["error"]), "Supervisor unavailable")
        self.assertEqual(kwargs["draft"]["max_devices_per_resident"], "7")

    def test_device_link_selects_exact_key_and_preserves_return_search(self):
        records = [
            {
                "name": "Alex",
                "email": "alex@example.org",
                "unit": "101",
                "ipsk_id": "key-1",
                "ipsk_name": "TV",
                "mac_address": "00:11:22:33:44:55",
                "created_at": datetime.datetime(2026, 10, 2),
            }
        ]
        page = self.render(
            "devices", {"q": ["Alex"], "record_sort": ["name"]}, records=records
        )
        self.assertIn("key_id=key-1&amp;device_q=Alex&amp;device_sort=name", page)
        keys = [
            {"id": "key-1", "name": "TV", "status": "active"},
            {"id": "key-10", "name": "Different device", "status": "active"},
        ]
        page = self.render(
            "keys",
            {"key_id": ["key-1"], "device_q": ["Alex"], "device_sort": ["name"]},
            keys=keys,
        )
        self.assertNotIn("Different device", page)
        self.assertIn(
            "/ipsk/devices?q=Alex&amp;record_sort=name&amp;record_page=1", page
        )
        self.assertIn('name="key_id" value="key-1"', page)
        handler = self.handler(
            "/ipsk/key/action",
            {
                "ipsk_id": "key-1",
                "action": "reveal",
                "key_id": "key-1",
                "device_q": "Alex",
            },
        )
        with patch.object(ipsk, "reveal_ipsk", return_value="fixture-password"):
            handler.handle_post()
        self.assertEqual(
            handler.residents_page.call_args.args[0],
            {"key_id": ["key-1"], "device_q": ["Alex"]},
        )

    def test_invitation_label_is_validated_and_persisted_without_storing_code(self):
        with patch.object(ipsk, "db_connect") as db:
            with self.assertRaises(guidance.FieldError):
                ipsk.create_invite("Fixture admin", "invalid\nlabel")
            db.assert_not_called()
            code = ipsk.create_invite("Fixture admin", "Alex — unit 101")
            cursor = db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            sql, values = cursor.execute.call_args.args
            self.assertIn("SHA2(%s, 256)", sql)
            self.assertIn("label", sql)
            self.assertEqual(values, (code, "Fixture admin", "Alex — unit 101"))

    def test_current_and_other_device_results_prioritize_the_correct_next_action(self):
        result = {"name": "TV", "ssid": "Home Wi-Fi", "passphrase": "fixture-password"}
        for identity in (True, False):
            page = ipsk.device_success(
                result, "https://fixture.network-auth.com/splash/grant", identity
            )
            self.assertLess(
                page.index("Copy Wi-Fi password"), page.index("Finish setup</a>")
            )
            self.assertLess(
                page.index("Finish setup</a>"), page.index("QR for another device")
            )
            self.assertIn("It is shown only once", page)
        other = ipsk.device_success(result)
        self.assertLess(other.index('class="qr"'), other.index("Copy Wi-Fi password"))
        self.assertNotIn("Finish setup</a>", other)


if __name__ == "__main__":
    unittest.main()
