"""Regression checks for installation guidance and resident form recovery."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import guidance
import ipsk
import resident_access


class GuidanceRegression(unittest.TestCase):
    def test_input_error_preserves_hint_and_escapes_text(self):
        markup = '<input id="mac" aria-describedby="hardware-hint">'
        result = guidance.form_error(markup, guidance.FieldError("mac", '<bad "address">'))
        self.assertIn('aria-describedby="hardware-hint mac-error"', result)
        self.assertIn('aria-invalid="true"', result)
        self.assertIn('&lt;bad &quot;address&quot;&gt;', result)

    def test_select_error_follows_closing_control(self):
        markup = '<select id=resident><option>Choose</option></select>'
        result = guidance.form_error(markup, guidance.FieldError("resident", "Choose an account"))
        self.assertIn('aria-invalid="true"', result)
        self.assertLess(result.index('</select>'), result.index('<p class="field-error"'))

    def test_unknown_error_does_not_annotate_a_control(self):
        markup = '<input id=name>'
        self.assertEqual(guidance.form_error(markup, ValueError("Expired")), markup)
        self.assertEqual(guidance.form_error(markup, guidance.FieldError('name" onclick=', "Invalid")), markup)

    def test_progress_marks_one_step_and_previous_steps_completed(self):
        result = guidance.progress(2)
        self.assertEqual(result.count('aria-current="step"'), 1)
        self.assertIn('<li aria-current="step">Device', result)
        self.assertEqual(result.count(', completed'), 1)
        self.assertIn('Save and connect', guidance.progress(99, identity=False))

    def test_help_search_is_case_insensitive_and_bounded(self):
        self.assertEqual(guidance.help_topics("PRIVATE MAC"), guidance.help_topics("private mac"))
        self.assertTrue(guidance.help_topics("private mac"))
        self.assertEqual(guidance.help_topics("unmatched" * 1000), [])

    def test_page_number_rejects_invalid_and_bounds_extreme_values(self):
        for value in (None, "invalid", "-4", "0"):
            self.assertEqual(guidance.page_number(value), 1)
        self.assertEqual(guidance.page_number("999999999999"), 1000000)

    def test_pagination_escapes_links_and_omits_unavailable_directions(self):
        result = guidance.pagination(1, 2, 1, 25, 26, lambda page: f'/residents?q=<x>&page={page}', "Records")
        self.assertNotIn('>Previous<', result)
        self.assertIn('>Next<', result)
        self.assertIn('q=&lt;x&gt;&amp;page=2', result)
        self.assertEqual(guidance.pagination(1, 1, 0, 0, 0, str, "Records"), "")

    def test_identity_and_device_forms_return_progress_and_field_recovery(self):
        session = {"csrf": "fixture", "captive": "", "identity": None,
                   "identity_draft": {"name": "Resident", "email": 'bad"email'}}
        config = {"self_service_enabled": True, "sign_in_required": False, "invite_required": True}
        identity = resident_access.identity_form(ipsk, config, session, guidance.FieldError("email", "Fix email"))
        self.assertIn('bad&quot;email', identity)
        self.assertIn('aria-describedby="email-error"', identity)
        session.update(identity={"name": "Resident"}, draft={"device": "TV", "mac": "02:11:22:33:44:55"})
        device = resident_access.account_form(ipsk, config, session, guidance.FieldError("mac", "Use hardware MAC"))
        self.assertIn('aria-current="step">Device', device)
        self.assertIn('other-device-help mac-error', device)
        self.assertIn('value="TV"', device)
        self.assertNotIn('name=invite autocomplete=off required value=', device)


class SetupRegression(unittest.TestCase):
    def render(self, query=None, config=None, options=None, url="", db_error=None):
        handler = app.Handler.__new__(app.Handler)
        handler.url = lambda path: path
        handler.page = MagicMock()
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = db_error
        with patch.dict(os.environ, {"PORTAL_DB_HOST": "fixture"}), \
                patch.object(app, "SUPERVISOR_TOKEN", "fixture"), \
                patch.object(app, "ENROLL_PUBLIC_URL", url), \
                patch.object(app, "saved_options", return_value={}), \
                patch.object(app, "_fetch_core_urls", return_value=("", "", "")), \
                patch.object(ipsk.resident_access, "settings", return_value=config or {}), \
                patch.object(ipsk, "db_connect", return_value=connection) as db, \
                patch.object(ipsk, "get_options", return_value=options or {"networks": []}) as provider, \
                patch.object(ipsk, "create_ipsk") as create:
            handler.setup_page(query)
        create.assert_not_called()
        return handler.page.call_args.args[1], db, provider, connection

    def test_checks_are_explicit_and_do_not_run_on_initial_page(self):
        markup, db, provider, _ = self.render()
        self.assertIn("Not checked", markup)
        self.assertIn('data-readiness-check', markup)
        db.assert_not_called()
        provider.assert_not_called()

    def test_requested_checks_read_five_tables_and_selected_network(self):
        config = {"network_id": "N_fixture", "ssid_number": 0, "group_policy_id": "101"}
        options = {"networks": [{"id": "N_fixture"}], "ssids": [{"number": 0}], "group_policies": [{"id": "101"}]}
        markup, _, provider, conn = self.render({"check": ["1"]}, config, options, "https://ha.example.org")
        self.assertIn("Available", markup)
        self.assertIn("Configured; not verified", markup)
        provider.assert_called_once_with("N_fixture")
        statements = conn.cursor.return_value.__enter__.return_value.execute.call_args_list
        self.assertEqual(len(statements), 5)
        self.assertTrue(all(call.args[0].startswith("SELECT 1 FROM stepca_") for call in statements))

    def test_failed_check_does_not_expose_provider_or_database_error(self):
        markup, _, _, _ = self.render({"check": ["1"]}, db_error=RuntimeError("fixture-secret"))
        self.assertIn("Needs attention", markup)
        self.assertNotIn("fixture-secret", markup)

    def test_invalid_public_urls_are_not_reported_as_configured(self):
        for url in ("http://ha.example.org", "https://user:password@ha.example.org", "https://ha.example.org:broken", "https://ha.example.org?secret=value"):
            with self.subTest(url=url):
                markup, _, _, _ = self.render(url=url)
                self.assertIn("Needs HTTPS URL", markup)

    def test_missing_selected_policy_requires_attention(self):
        markup, _, _, _ = self.render({"check": ["1"]},
            {"network_id": "N_fixture", "ssid_number": 0, "group_policy_id": "missing"},
            {"networks": [{"id": "N_fixture"}], "ssids": [{"number": 0}], "group_policies": []})
        self.assertIn("selected network, enabled iPSK SSID or policy is unavailable", markup)

    def test_help_search_escapes_query_and_has_empty_recovery(self):
        handler = app.Handler.__new__(app.Handler)
        handler.url = lambda path: path
        handler.page = MagicMock()
        handler.help_page({"q": ['<script>"']})
        markup = handler.page.call_args.args[1]
        self.assertIn('&lt;script&gt;&quot;', markup)
        self.assertIn('No matching guides', markup)
        self.assertIn('Clear search', markup)


if __name__ == "__main__":
    unittest.main()
