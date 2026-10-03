"""Shared identity pages, scoped writes and compatibility with IPSK policy."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import identity_settings as identity
import ipsk

CONFIG = {
    "network_id": "N_fixture",
    "ssid_number": 0,
    "self_service_enabled": True,
    "sign_in_required": True,
    "no_sign_in_user_list": False,
    "max_devices_per_resident": 5,
    "duo_client_id": "fixture-client",
    "duo_client_secret": "fixture-sdk-secret",
    "duo_api_hostname": "api-fixture.duosecurity.com",
    "duo_redirect_uri": "https://ha.example.org/api/step_ca_scep/portal?action=duo_callback",
    "duo_group_id": "DG" + "A" * 18,
    "duo_admin_hostname": "api-fixture.duosecurity.com",
    "duo_admin_integration_key": "fixture-admin",
    "duo_admin_secret": "fixture-admin-secret",
    "guest_ssid": "Guest Wi-Fi",
    "guest_psk": "fixture-guest-password",
}


class SharedIdentityTests(unittest.TestCase):
    def handler(self, path, form=None):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        if form is not None:
            data = urlencode({"csrf": app.CSRF_TOKEN, **form}).encode()
            handler.headers.update(
                {
                    "Content-Length": str(len(data)),
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            )
            handler.rfile = io.BytesIO(data)
        return handler

    def test_shared_pages_work_with_ipsk_and_database_unconfigured(self):
        for kind in identity.FIELDS:
            with self.subTest(kind=kind):
                handler = self.handler("/settings/identity/" + kind)
                with (
                    patch.object(
                        app,
                        "saved_options",
                        return_value={"resident_onboarding": CONFIG},
                    ),
                    patch.object(ipsk, "PORTAL_ENABLED", False),
                    patch.object(app, "SUPERVISOR_TOKEN", ""),
                    patch.object(
                        ipsk,
                        "get_options",
                        side_effect=AssertionError("No Wi-Fi request"),
                    ),
                    patch.object(
                        ipsk.resident_access,
                        "group_members",
                        side_effect=AssertionError("No directory fetch"),
                    ),
                ):
                    handler.do_GET()
                markup = handler.send.call_args.args[1]
                self.assertIn("Identity &amp; access", markup)
                self.assertNotIn("Resident portal disabled", markup)
                self.assertNotIn("MariaDB required", markup)
                for field in identity.FIELDS[kind]:
                    self.assertIn('name="' + field + '"', markup)
                other = "directory" if kind == "authentication" else "authentication"
                for field in identity.FIELDS[other]:
                    self.assertNotIn('name="' + field + '"', markup)
                for secret in identity.SECRET_FIELDS:
                    self.assertNotIn(CONFIG[secret], markup)

    def test_ipsk_policy_links_to_identity_without_provider_fields(self):
        handler = self.handler("/settings/ipsk/access")
        with patch.object(
            app, "saved_options", return_value={"resident_onboarding": CONFIG}
        ):
            handler.do_GET()
        markup = handler.send.call_args.args[1]
        for fields in identity.FIELDS.values():
            for field in fields:
                self.assertNotIn('name="' + field + '"', markup)
        self.assertIn('/settings/identity/authentication"', markup)
        self.assertIn('/settings/identity/directory"', markup)
        self.assertIn("Device access", markup)

    def save(self, kind, form, config=None):
        config = dict(CONFIG if config is None else config)
        handler = self.handler("/settings/identity/" + kind + "/save", form)
        handler.identity_page = MagicMock()
        with (
            patch.object(
                app,
                "saved_options",
                return_value={"ca_name": "Fixture CA", "resident_onboarding": config},
            ),
            patch.object(app, "supervisor") as remote,
            patch.object(ipsk.resident_access, "SETTINGS_OVERRIDE", None),
        ):
            handler.handle_post()
            saved = remote.call_args.args[2]["options"] if remote.called else None
            override = ipsk.resident_access.SETTINGS_OVERRIDE
        return handler, saved, override

    def test_authentication_save_is_independent_and_preserves_other_fields(self):
        config = {**CONFIG, "network_id": "", "sign_in_required": False}
        form = {
            "duo_client_id": " updated-client ",
            "duo_client_secret": "",
            "duo_group_id": "injected-group",
            "self_service_enabled": "0",
        }
        handler, options, override = self.save("authentication", form, config)
        self.assertEqual(options["ca_name"], "Fixture CA")
        saved = options["resident_onboarding"]
        self.assertEqual(saved, {**config, "duo_client_id": "updated-client"})
        self.assertEqual(override, saved)
        handler.identity_page.assert_called_once_with(
            "authentication", {"saved": ["1"]}
        )

    def test_directory_save_preserves_authentication_and_consumer_policy(self):
        handler, options, _ = self.save(
            "directory",
            {
                "duo_admin_hostname": "api-directory.duosecurity.com",
                "duo_admin_secret": "",
                "duo_client_id": "injected-client",
                "sign_in_required": "0",
            },
        )
        self.assertEqual(
            options["resident_onboarding"],
            {**CONFIG, "duo_admin_hostname": "api-directory.duosecurity.com"},
        )
        handler.identity_page.assert_called_once_with("directory", {"saved": ["1"]})

    def test_policy_save_cannot_replace_identity_credentials(self):
        handler = self.handler(
            "/settings/ipsk/access/save",
            {
                "self_service_enabled": "1",
                "sign_in_required": "1",
                "max_devices_per_resident": "7",
                "duo_client_secret": "injected-secret",
                "duo_group_id": "injected-group",
            },
        )
        handler.residents_page = MagicMock()
        with (
            patch.object(
                app, "saved_options", return_value={"resident_onboarding": dict(CONFIG)}
            ),
            patch.object(app, "supervisor") as remote,
            patch.object(ipsk.resident_access, "SETTINGS_OVERRIDE", None),
        ):
            handler.handle_post()
        self.assertEqual(
            remote.call_args.args[2]["options"]["resident_onboarding"],
            {**CONFIG, "max_devices_per_resident": 7},
        )
        handler.residents_page.assert_called_once_with(
            {"access_saved": ["1"]}, section="access"
        )

    def test_invalid_callback_keeps_safe_draft_and_never_saves_new_secret(self):
        handler, saved, override = self.save(
            "authentication",
            {
                "duo_client_id": "updated-client",
                "duo_client_secret": "new-private-secret",
                "duo_redirect_uri": "http://invalid.example.org/",
            },
        )
        self.assertIsNone(saved)
        self.assertIsNone(override)
        call = handler.identity_page.call_args.kwargs
        self.assertEqual(call["error"].field, "duo_redirect_uri")
        self.assertEqual(call["draft"]["duo_client_id"], "updated-client")
        self.assertNotIn("duo_client_secret", call["draft"])
        self.assertNotIn("new-private-secret", str(call))

    def test_active_consumer_cannot_clear_required_authentication(self):
        handler, saved, _ = self.save("authentication", {"duo_client_id": ""})
        self.assertIsNone(saved)
        self.assertIn(
            "Complete the Duo Universal SDK",
            str(handler.identity_page.call_args.kwargs["error"]),
        )

    def test_shared_save_routes_reject_bad_csrf(self):
        for kind in identity.FIELDS:
            handler = self.handler(
                "/settings/identity/" + kind + "/save", {"csrf": "wrong"}
            )
            handler.identity_save = MagicMock()
            handler.handle_post()
            handler.identity_save.assert_not_called()
            self.assertEqual(handler.send.call_args.args[0], 403)

    def test_read_failure_is_recoverable_without_provider_details(self):
        handler = self.handler("/settings/identity/directory")
        with patch.object(
            app, "saved_options", side_effect=RuntimeError("private-provider-secret")
        ):
            handler.do_GET()
        markup = handler.send.call_args.args[1]
        self.assertIn("Settings unavailable", markup)
        self.assertNotIn("private-provider-secret", markup)
        self.assertNotIn('<form method="post"', markup)

    def test_all_onboarding_fields_have_exactly_one_reference_category(self):
        import settings_menu
        import yaml

        config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "config.yaml").read_text()
        )
        sections = list(settings_menu.ONBOARDING_SECTIONS.values())
        self.assertEqual(
            set(config["options"]["resident_onboarding"]), set().union(*sections)
        )
        self.assertEqual(
            sum(len(section) for section in sections), len(set().union(*sections))
        )

    def test_shared_module_is_packaged(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("admin/identity_settings.py", (root / "Dockerfile").read_text())
        self.assertIn(
            "!admin/identity_settings.py", (root / ".dockerignore").read_text()
        )


if __name__ == "__main__":
    unittest.main()
