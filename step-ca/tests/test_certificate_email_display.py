"""Keep certificate addresses readable when pages pass through Cloudflare."""

import datetime
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app


class CertificateEmailDisplayTests(unittest.TestCase):
    email = "device-owner@example.org"

    def certificate(self):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fixture-device")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(123)
                .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName([x509.RFC822Name(self.email)]), critical=False)
                .sign(key, hashes.SHA256()))
        return app.cert_summary("123", cert.public_bytes(serialization.Encoding.DER), {}, None)

    def handler(self, path):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.send = MagicMock()
        return handler

    def assert_protected_address(self, html):
        protected = html.split("<!--email_off-->", 1)[1].split("<!--/email_off-->", 1)[0]
        self.assertIn(self.email, protected)
        self.assertNotIn("/cdn-cgi/l/email-protection", html)
        self.assertNotIn("__cf_email__", html)

    def test_certificate_list_and_details_keep_original_email_inside_edge_opt_out(self):
        certificate = self.certificate()
        for path in ("/", "/cert/123"):
            with self.subTest(path=path):
                handler = self.handler(path)
                with patch.object(app, "db_enabled", return_value=True), \
                        patch.object(app, "fetch_certs", return_value=[certificate]), \
                        patch.object(app.DELETED, "all", return_value=set()), \
                        patch.object(app.Handler, "health", return_value=""):
                    if path == "/":
                        handler.list_page({})
                    else:
                        handler.detail_page("123", {})
                self.assert_protected_address(handler.send.call_args.args[1])
        self.assertEqual(certificate["sans"], [self.email])

    def test_response_disallows_transformation_without_allowing_injected_scripts(self):
        handler = self.handler("/")
        handler.command = "GET"
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        app.Handler.send(handler, 200, self.email, nonce="fixture-nonce")
        headers = dict(call.args for call in handler.send_header.call_args_list)
        self.assertEqual(headers["Cache-Control"], "no-store, no-transform")
        self.assertIn("script-src 'nonce-fixture-nonce';", headers["Content-Security-Policy"])
        self.assertNotIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(handler.wfile.getvalue().decode(), self.email)

    def test_public_enrollment_uses_same_email_opt_out(self):
        handler = app.EnrollHandler.__new__(app.EnrollHandler)
        handler.send = MagicMock()
        handler.page("Certificate", f"<p>{self.email}</p>")
        self.assert_protected_address(handler.send.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
