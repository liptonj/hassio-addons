"""Navigation contracts: usable destinations, selection and real section anchors."""

import datetime
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app


class NavigationMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.menus, self.current, self.ids, self.links = [], [], set(), []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details" and "tab-menu" in attrs.get("class", "").split():
            self.menus.append(attrs)
        if tag == "a":
            self.links.append(attrs["href"])
            if attrs.get("aria-current") == "page":
                self.current.append(attrs["href"])
        if "id" in attrs:
            self.ids.add(attrs["id"])


class NavigationDropdownTests(unittest.TestCase):
    def handler(self, path):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.send = MagicMock()
        return handler

    def render(self, path):
        handler = self.handler(path)
        handler.page("Fixture", "<p>Fixture</p>")
        return NavigationMarkup(handler.send.call_args.args[1])

    def test_every_main_section_has_a_closed_dropdown_and_real_task_links(self):
        parsed = self.render("/ipsk")
        self.assertEqual(len(parsed.menus), 5)
        self.assertTrue(all("open" not in menu for menu in parsed.menus))
        for target in ("/?status=expiring", "/enroll#new-link", "/enroll/self",
                       "/ipsk/devices", "/ipsk/invitations", "/ipsk/join-codes", "/ipsk/create",
                       "/ca#root-ca", "/ca#authority-downloads", "/settings/identity",
                       "/settings/captive-portal"):
            with self.subTest(target=target):
                self.assertIn("/api/hassio_ingress/fixture" + target, parsed.links)

    def test_current_option_tracks_certificate_filter_and_ipsk_task(self):
        for path, current in (("/", "/?status=active"), ("/?status=all", "/?status=all"),
                              ("/?status=revoked", "/?status=revoked"),
                              ("/?status=invalid", "/?status=active"),
                              ("/ipsk/create", "/ipsk/create"), ("/ipsk/devices", "/ipsk/devices")):
            with self.subTest(path=path):
                self.assertEqual(self.render(path).current, ["/api/hassio_ingress/fixture" + current])

    def test_enrollment_menu_anchors_exist_in_the_real_page(self):
        handler = self.handler("/enroll")
        with patch.object(app, "detect_base_url", return_value=("https://ha.example.org", "fixture")), \
                patch.object(app, "signer_status", return_value=(False, "Fixture signer unavailable")), \
                patch.object(app.LINKS, "all", return_value=[]):
            handler.enroll_page()
        self.assertTrue({"new-link", "links", "issue-certificate"}.issubset(
            NavigationMarkup(handler.send.call_args.args[1]).ids))

    def test_authority_menu_anchors_exist_in_the_real_page(self):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fixture CA")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365))
                .sign(key, hashes.SHA256()))
        handler = self.handler("/ca")
        with patch.object(app, "cert_chain", return_value=(cert, cert)), \
                patch.object(app.enroll, "load_extra_cas", return_value=[]):
            handler.ca_page()
        self.assertTrue({"root-ca", "intermediate-ca", "authority-downloads", "authority-endpoints"}.issubset(
            NavigationMarkup(handler.send.call_args.args[1]).ids))


if __name__ == "__main__":
    unittest.main()
