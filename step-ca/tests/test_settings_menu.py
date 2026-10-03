"""Central settings routes, ingress links, configuration coverage and form guards."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import settings_menu as menu


class SettingsMenuTests(unittest.TestCase):
    def handler(self, path="/settings", form=None):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        handler.redirect = MagicMock()
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

    def markup(self, handler):
        return handler.send.call_args.args[1]

    def test_hub_has_four_categories_and_no_eager_service_requests(self):
        handler = self.handler()
        with patch.object(app, "supervisor") as remote:
            handler.do_GET()
        remote.assert_not_called()
        markup = self.markup(handler)
        self.assertEqual(markup.count('class="row settings-row"'), 4)
        self.assertIn('href="/api/hassio_ingress/fixture/settings/ipsk"', markup)
        self.assertIn("aria-current=page", markup)
        self.assertIn("<span>Settings</span>", markup)
        self.assertNotIn("<span>Tools</span>", markup)

    def test_each_category_has_local_links_and_working_breadcrumbs(self):
        for slug, title, _, _, leaves in menu.GROUPS:
            with self.subTest(slug=slug):
                handler = self.handler("/settings/" + slug)
                handler.do_GET()
                markup = self.markup(handler)
                self.assertIn('aria-label="Breadcrumb"', markup)
                self.assertIn('aria-label="Settings navigation"', markup)
                self.assertIn('aria-current="page">' + menu.esc(title), markup)
                for leaf, label, _ in leaves:
                    self.assertIn(
                        'href="/api/hassio_ingress/fixture/settings/'
                        + slug
                        + "/"
                        + leaf
                        + '"',
                        markup,
                    )

    def test_old_bookmarks_preserve_query_when_redirecting(self):
        for old, new in menu.ALIASES.items():
            with self.subTest(old=old):
                handler = self.handler(old + "?edit=Office&check=1")
                handler.do_GET()
                handler.redirect.assert_called_once_with(new + "?edit=Office&check=1")

    def test_links_keep_ingress_prefix_queries_fragments_and_action_suffixes(self):
        handler = self.handler()
        examples = {
            "/tools/wifi?edit=Office#wifi-form": "/settings/enrollment/networks?edit=Office#wifi-form",
            "/tools/groups/family/delete": "/settings/certificates/groups/family/delete",
            "/ipsk/access/settings": "/settings/ipsk/access/save",
            "/ipsk/join-codes/settings": "/settings/ipsk/join-codes",
            "/tools/groupsevil": "/tools/groupsevil",
        }
        for old, new in examples.items():
            self.assertEqual(handler.url(old), "/api/hassio_ingress/fixture" + new)

    def test_all_declared_addon_options_have_a_category(self):
        config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "config.yaml").read_text()
        )
        assigned = {key for fields in menu.OPTION_PAGES.values() for key, _ in fields}
        self.assertEqual(set(config["options"]), assigned)

    def test_complete_summary_redacts_nested_secrets_and_escapes_values(self):
        options = {
            "ca_name": "<script>bad</script>",
            "scep_challenge": "hidden-scep-value",
            "groups": [{"name": "Family", "challenge": "hidden-group-value"}],
            "wifi_networks": [
                {
                    "ssid": "Office",
                    "eap_password": "hidden-eap-value",
                    "proxy_password": "hidden-proxy-value",
                }
            ],
            "resident_onboarding": {
                "guest_psk": "hidden-guest-value",
                "duo_client_secret": "hidden-duo-value",
                "max_devices_per_resident": 5,
            },
            "custom_future_option": {"api_secret": "hidden-new-value"},
        }
        handler = self.handler("/settings/system/options")
        with patch.object(
            app,
            "supervisor",
            return_value={"slug": "af1e6959_step-ca-scep", "options": options},
        ):
            handler.do_GET()
        markup = self.markup(handler)
        for secret in (
            "hidden-scep-value",
            "hidden-group-value",
            "hidden-eap-value",
            "hidden-proxy-value",
            "hidden-guest-value",
            "hidden-duo-value",
            "hidden-new-value",
        ):
            self.assertNotIn(secret, markup)
        self.assertIn("&lt;script&gt;bad&lt;/script&gt;", markup)
        self.assertIn(
            'href="/hassio/addon/af1e6959_step-ca-scep/config" target="_top"', markup
        )
        self.assertIn("Additional add-on options", markup)
        self.assertIn("Saved", markup)

    def test_onboarding_summary_excludes_identity_and_join_code_fields(self):
        handler = self.handler("/settings/ipsk/network")
        options = {
            "resident_onboarding": {
                "network_id": "N_fixture",
                "ssid_number": 0,
                "invite_required": False,
                "duo_api_hostname": "private-host",
                "guest_ssid": "private-guest",
            }
        }
        with patch.object(app, "supervisor", return_value={"options": options}):
            handler.do_GET()
        markup = self.markup(handler)
        self.assertIn("N_fixture", markup)
        self.assertIn('settings-value">0', markup)
        self.assertIn('settings-value">No', markup)
        self.assertNotIn("private-host", markup)
        self.assertNotIn("private-guest", markup)

    def test_unavailable_settings_show_recovery_without_exception_body(self):
        handler = self.handler("/settings/system/storage")
        with patch.object(
            app, "supervisor", side_effect=RuntimeError("hidden-provider-secret")
        ):
            handler.do_GET()
        markup = self.markup(handler)
        self.assertIn("Settings unavailable", markup)
        self.assertIn("Configuration tab", markup)
        self.assertNotIn("hidden-provider-secret", markup)

    def test_new_form_routes_reach_original_handlers_after_validation(self):
        for route, method, fields in (
            ("/settings/enrollment/networks/save", "wifi_save", {"ssid": "Office"}),
            ("/settings/certificates/groups/save", "group_save", {"name": "family"}),
            ("/settings/system/restart", "restart_addon", {}),
        ):
            with self.subTest(route=route):
                handler = self.handler(route, fields)
                setattr(handler, method, MagicMock())
                handler.handle_post()
                getattr(handler, method).assert_called_once()
                rejected = self.handler(route, {**fields, "csrf": "wrong"})
                setattr(rejected, method, MagicMock())
                rejected.handle_post()
                getattr(rejected, method).assert_not_called()
                self.assertEqual(rejected.send.call_args.args[0], 403)

    def test_ipsk_settings_routes_dispatch_to_existing_form_services(self):
        for route, legacy in (
            ("/settings/ipsk/access/save", "/ipsk/access/settings"),
            ("/settings/ipsk/join-codes/save", "/ipsk/qr/settings"),
        ):
            self.assertEqual(menu.legacy_path(route), legacy)

    def test_new_module_is_included_in_image_build_context(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("admin/settings_menu.py", (root / "Dockerfile").read_text())
        self.assertIn("!admin/settings_menu.py", (root / ".dockerignore").read_text())


if __name__ == "__main__":
    unittest.main()
