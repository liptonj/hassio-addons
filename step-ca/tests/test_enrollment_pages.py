"""Focused enrollment routing, validation recovery and inventory actions."""

import datetime
from html.parser import HTMLParser
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms, self.inputs, self.current = [], {}, []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append(attrs)
        elif tag == "input":
            self.inputs[attrs.get("name")] = attrs
        elif tag == "a" and attrs.get("aria-current") == "page":
            self.current.append(attrs["href"])


class EnrollmentPagesTests(unittest.TestCase):
    prefix = "/api/hassio_ingress/fixture"

    def handler(self, path, form=None):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": self.prefix}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        handler.redirect = MagicMock()
        if form is not None:
            body = urlencode({"csrf": app.CSRF_TOKEN, **form}).encode()
            handler.headers.update({"Content-Length": str(len(body)),
                                    "Content-Type": "application/x-www-form-urlencoded"})
            handler.rfile = io.BytesIO(body)
        return handler

    def html(self, handler):
        return handler.send.call_args.args[1]

    def test_tasks_render_separately_and_only_read_their_own_dependencies(self):
        for path, action in (("/enroll", None), ("/enroll/new", "/enroll/new"),
                             ("/enroll/links", None), ("/enroll/issue", "/enroll/issue"),
                             ("/enroll/self", "/enroll/self")):
            with self.subTest(path=path):
                handler = self.handler(path)
                with patch.object(app.LINKS, "all", return_value=[]) as inventory, \
                        patch.object(app, "detect_base_url", return_value=("https://ha.example.org", "fixture")) as base, \
                        patch.object(app, "signer_status", return_value=(False, "Fixture signer unavailable")) as signer:
                    handler.do_GET()
                self.assertEqual(handler.send.call_args.args[0], 200)
                html = self.html(handler)
                parsed = Markup(html)
                self.assertEqual([form["action"] for form in parsed.forms],
                                 [] if action is None else [self.prefix + action])
                self.assertEqual(html.count('class="tab-menu'), 5)
                self.assertIn(self.prefix + path, parsed.current)
                self.assertEqual(inventory.call_count, int(path == "/enroll/links"))
                self.assertEqual(base.call_count, int(path == "/enroll/new"))
                self.assertEqual(signer.call_count, int(path == "/enroll/new"))

    def test_new_link_error_keeps_its_fields_and_does_not_create_a_link(self):
        handler = self.handler("/enroll/new")
        fields = {"label": ["Alex <phone>"], "cn": ["alex-phone"], "email": ["alex@example.org"],
                  "sans": ["phone.example.org"], "base_url": ["not a URL"], "hours": ["48"]}
        with patch.object(app.LINKS, "create") as create, \
                patch.object(app, "detect_base_url", return_value=("https://ha.example.org", "fixture")), \
                patch.object(app, "signer_status", return_value=(False, "Fixture signer unavailable")), \
                patch.object(app, "wifi_enabled", return_value=True), \
                patch.object(app, "wifi_names", return_value="Office"):
            handler.enroll_create(fields)
        create.assert_not_called()
        html = self.html(handler)
        parsed = Markup(html)
        self.assertIn("The link was not created", html)
        for name, value in fields.items():
            self.assertEqual(parsed.inputs[name]["value"], value[0])
        self.assertNotIn("checked", parsed.inputs["wifi"])
        self.assertNotIn("<phone>", html)
        self.assertNotIn('id="links"', html)
        self.assertNotIn('id="issue-certificate"', html)

    def test_issue_validation_and_backend_errors_stay_on_the_issue_form(self):
        for name, provider_error in (("bad!name", False), ("Printer", True)):
            with self.subTest(provider_error=provider_error):
                handler = self.handler("/enroll/issue")
                fields = {"cn": [name], "email": ["alex@example.org"], "sans": ["printer.example.org"]}
                with patch.object(app.enroll, "issue_p12", side_effect=RuntimeError("Fixture issuer unavailable")) as issue, \
                        patch.object(app.enroll, "load_extra_cas", return_value=[]):
                    handler.issue_direct(fields)
                self.assertEqual(issue.call_count, int(provider_error))
                html = self.html(handler)
                parsed = Markup(html)
                self.assertIn("Nothing was issued", html)
                self.assertEqual(parsed.forms[0]["action"], self.prefix + "/enroll/issue")
                for field, value in fields.items():
                    self.assertEqual(parsed.inputs[field]["value"], value[0])
                self.assertNotIn('id="new-link"', html)

    def test_new_and_legacy_issue_posts_keep_csrf_protection(self):
        for path in ("/enroll/new", "/enroll/self", "/enroll/issue", "/issue"):
            method = "enroll_create" if path == "/enroll/new" else "self_enroll" if path == "/enroll/self" else "issue_direct"
            for csrf in (app.CSRF_TOKEN, "invalid"):
                with self.subTest(path=path, csrf_valid=csrf == app.CSRF_TOKEN):
                    handler = self.handler(path, {"csrf": csrf, "cn": "Printer"})
                    setattr(handler, method, MagicMock())
                    handler.handle_post()
                    self.assertEqual(getattr(handler, method).call_count, int(csrf == app.CSRF_TOKEN))
                    if csrf != app.CSRF_TOKEN:
                        self.assertEqual(handler.send.call_args.args[0], 403)

    def test_links_page_paging_and_actions_preserve_the_inventory_location(self):
        expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).timestamp()
        links = [{"id": f"{n:064x}", "label": f"Device {n:02}", "cn": "", "created_by": "", "issued_cn": "",
                  "method": "", "state": "pending", "expires": expires, "sans": [], "group": ""} for n in range(26)]
        handler = self.handler("/enroll/links?links=waiting&page=2")
        with patch.object(app.LINKS, "all", return_value=links):
            handler.do_GET()
        html = self.html(handler)
        self.assertIn("Device 10", html)
        self.assertNotIn("Device 00", html)
        self.assertIn("Page 2 of 3", html)
        self.assertIn('/enroll/links?links=waiting&amp;page=3', html)
        self.assertIn('name="page" value="2"', html)
        for action, method in (("cancel", "cancel"), ("delete", "delete")):
            actor = self.handler("/enroll/" + "a" * 64 + "/" + action, {"view": "waiting", "page": "2"})
            with patch.object(app.LINKS, method) as remote:
                actor.handle_post()
            remote.assert_called_once()
            actor.redirect.assert_called_once_with("/enroll/links?links=waiting&page=2")
        self.assertEqual(handler.links_return({"view": ["invalid"], "page": ["//elsewhere"]}),
                         "/enroll/links?links=waiting")

    def test_legacy_list_bookmarks_redirect_with_their_query(self):
        for path, target in (("/enroll?links=used&page=2", "/enroll/links?links=used&page=2"),
                             ("/enroll?deleted=3", "/enroll/links?deleted=3"),
                             ("/issue", "/enroll/issue")):
            with self.subTest(path=path):
                handler = self.handler(path)
                handler.do_GET()
                handler.redirect.assert_called_once_with(target)

    def test_results_return_to_the_task_that_created_them(self):
        handler = self.handler("/enroll/new")
        handler.page = MagicMock()
        with patch.object(app.LINKS, "create", return_value="fixture-token"):
            handler.enroll_create({"label": ["Phone"], "cn": ["Phone"], "base_url": ["https://ha.example.org"]})
        self.assertEqual(handler.page.call_args.kwargs["back"], "/enroll/new")
        self.assertIn(self.prefix + "/enroll/links", handler.page.call_args.args[1])
        handler = self.handler("/enroll/issue")
        handler.page = MagicMock()
        cert = MagicMock(serial_number=123)
        with patch.object(app.enroll, "issue_p12", return_value=(b"fixture", "fixture-password", cert)), \
                patch.object(app.enroll, "load_extra_cas", return_value=[]), \
                patch.object(app.DOWNLOADS, "add", return_value="fixture-download"), \
                patch.object(app, "db_enabled", return_value=False):
            handler.issue_direct({"cn": ["Printer"]})
        self.assertEqual(handler.page.call_args.kwargs["back"], "/enroll/issue")
        self.assertIn("shown only once", handler.page.call_args.args[1])

    def test_public_enrollment_form_keeps_its_public_layout(self):
        handler = app.EnrollHandler.__new__(app.EnrollHandler)
        handler.headers = {}
        handler.send = MagicMock()
        handler.form_page("/api/step_ca_scep/enroll/fixture-token", {"cn": "", "wifi": False})
        html = self.html(handler)
        self.assertIn("Get a certificate", html)
        self.assertNotIn('class="tab-menu', html)
        self.assertNotIn("Enroll this computer", html)


if __name__ == "__main__":
    unittest.main()
