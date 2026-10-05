"""Authority tasks must be distinct and display the certificate or file they name."""

import datetime
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app


class AuthorityPagesTests(unittest.TestCase):
    prefix = "/api/hassio_ingress/fixture"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        root_key = ec.generate_private_key(ec.SECP256R1())
        inter_key = ec.generate_private_key(ec.SECP256R1())
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fixture root")])
        inter_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fixture issuing CA")])
        self.root = self.certificate(root_name, root_name, root_key, root_key, 101)
        self.inter = self.certificate(inter_name, root_name, inter_key, root_key, 202)
        for name, certificate in (("root", self.root), ("intermediate", self.inter)):
            path = Path(self.directory.name) / (name + ".pem")
            path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
            patcher = patch.object(app, "ROOT_CERT" if name == "root" else "INTERMEDIATE_CERT", str(path))
            patcher.start()
            self.addCleanup(patcher.stop)

    def certificate(self, subject, issuer, key, signer, serial, start=-1, end=365):
        return (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
                .public_key(key.public_key()).serial_number(serial)
                .not_valid_before(self.now + datetime.timedelta(days=start))
                .not_valid_after(self.now + datetime.timedelta(days=end))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .sign(signer, hashes.SHA256()))

    def handler(self, path):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"X-Ingress-Path": self.prefix}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        return handler

    def html(self, handler):
        return handler.send.call_args.args[1]

    def test_each_task_has_its_own_content_and_current_dropdown_option(self):
        for path, title in (("/ca", "Authority overview"), ("/ca/root", "Root CA"),
                            ("/ca/intermediate", "Intermediate CA"), ("/ca/downloads", "Authority downloads"),
                            ("/ca/endpoints", "Authority endpoints")):
            with self.subTest(path=path):
                handler = self.handler(path)
                with patch.object(app, "detect_base_url", return_value=("https://ha.example.org", "fixture")):
                    handler.do_GET()
                self.assertEqual(handler.send.call_args.args[0], 200)
                html = self.html(handler)
                self.assertIn(f"<title>{title}</title>", html)
                self.assertIn(f'href="{self.prefix}{path}" aria-current="page"', html)
                self.assertEqual(html.count('class="tab-menu'), 5)
                main = html.split('<main id="main-content"', 1)[1].split('</main>', 1)[0]
                self.assertNotIn('<form', main)
                self.assertNotIn('action="' + self.prefix + '/ca/extra', main)
                self.assertEqual('<dt>Subject</dt>' in main, path in ("/ca/root", "/ca/intermediate"))
                self.assertEqual('<h2>Downloads</h2>' in main, path == "/ca/downloads")
                self.assertEqual('<h2>Endpoints</h2>' in main, path == "/ca/endpoints")

    def test_root_and_intermediate_show_their_actual_metadata_and_only_their_file(self):
        for kind, cert, filename, other in (("root", self.root, "root_ca.pem", "intermediate_ca.pem"),
                                            ("intermediate", self.inter, "intermediate_ca.pem", "root_ca.pem")):
            with self.subTest(kind=kind):
                handler = self.handler('/ca/' + kind)
                handler.authority_certificate_page(kind)
                html = self.html(handler)
                self.assertIn(cert.subject.rfc4514_string(), html)
                self.assertIn(cert.issuer.rfc4514_string(), html)
                self.assertIn('<dt>Valid from</dt>', html)
                self.assertIn('<dt>Valid until</dt>', html)
                self.assertIn(str(cert.serial_number), html)
                self.assertIn(app.enroll.fingerprint(cert), html)
                self.assertIn(self.prefix + '/download/' + filename, html)
                self.assertNotIn('/download/' + other, html)

    def test_certificate_status_accounts_for_validity_start_expiry_and_renewal(self):
        key = ec.generate_private_key(ec.SECP256R1())
        name = self.root.subject
        for start, end, expected in ((1, 365, 'Not yet valid'), (-3, -1, 'Expired'),
                                      (-1, 100, 'Renew soon'), (-1, 365, 'Valid')):
            with self.subTest(expected=expected):
                cert = self.certificate(name, name, key, key, 1001, start, end)
                self.assertIn('>' + expected + '</span>', app.Handler.authority_status(cert, self.now))

    def test_tasks_do_not_read_unrelated_certificate_trust_or_endpoint_services(self):
        for path in ('/ca', '/ca/root', '/ca/intermediate', '/ca/downloads', '/ca/endpoints'):
            with self.subTest(path=path):
                handler = self.handler(path)
                with patch.object(app.enroll, 'load_extra_cas') as extra, \
                        patch.object(app, 'detect_base_url', return_value=('https://ha.example.org', 'fixture')) as base:
                    handler.do_GET()
                extra.assert_not_called()
                self.assertEqual(base.call_count, int(path == '/ca/endpoints'))
        Path(app.INTERMEDIATE_CERT).unlink()
        handler = self.handler('/ca/root')
        handler.do_GET()
        self.assertIn('Fixture root', self.html(handler))

    def test_endpoints_match_companion_routes_escape_values_and_do_not_expose_challenges(self):
        handler = self.handler('/ca/endpoints')
        with patch.object(app, 'detect_base_url', return_value=('https://ha.example.org', 'fixture source')), \
                patch.object(app, 'SCEP_PROVISIONER', 'custom scep'), \
                patch.object(app, 'SCEP_CHALLENGE', 'DO-NOT-DISPLAY'), \
                patch.object(app, 'GROUPS', {'adults': {'challenge': 'GROUP-SECRET'}}):
            handler.authority_endpoints_page()
        html = self.html(handler)
        for suffix in ('scep/custom%20scep', 'scep/adults', 'roots.pem', 'crl', 'crl?pem'):
            self.assertIn('data-copy="https://ha.example.org/api/step_ca_scep/' + suffix + '"', html)
        self.assertIn('From fixture source.', html)
        self.assertIn('SCEP follows its configured enrollment challenge policy', html)
        self.assertIn('Set; accepts the static challenge or one-time enrollment links.', html)
        self.assertNotIn('DO-NOT-DISPLAY', html)
        self.assertNotIn('GROUP-SECRET', html)
        with patch.object(app, 'detect_base_url', return_value=('https://ha.example.org/?a=1&b=2', 'source <untrusted>')):
            handler.authority_endpoints_page()
        html = self.html(handler)
        self.assertIn('source &lt;untrusted&gt;', html)
        self.assertIn('a=1&amp;b=2', html)
        with patch.object(app, 'detect_base_url', return_value=('https://ha.example.org', 'fixture')), \
                patch.object(app, 'SCEP_CHALLENGE', ''), \
                patch.object(app, 'GROUPS', {'adults': {'challenge': ''}}):
            handler.authority_endpoints_page()
        html = self.html(handler)
        self.assertIn('Not set; default SCEP does not validate a challenge.', html)
        self.assertIn('One-time enrollment links only.', html)

    def test_missing_base_url_offers_recovery_without_copyable_placeholders(self):
        handler = self.handler('/ca/endpoints')
        with patch.object(app, 'detect_base_url', return_value=('', '')):
            handler.authority_endpoints_page()
        html = self.html(handler)
        self.assertIn('Home Assistant URL not configured', html)
        self.assertIn('enrollment.public_url', html)
        self.assertNotIn('data-copy=', html)
        self.assertNotIn('&lt;Home Assistant URL&gt;', html)

    def test_download_descriptions_and_actual_pem_payloads_agree(self):
        handler = self.handler('/ca/downloads')
        handler.authority_downloads_page()
        html = self.html(handler)
        self.assertIn('The same CA chain in a .crt file', html)
        self.assertIn('additional device trust certificates', html)
        self.assertIn('Revoked certificates, in PEM format', html)
        root_pem = self.root.public_bytes(serialization.Encoding.PEM)
        inter_pem = self.inter.public_bytes(serialization.Encoding.PEM)
        for route, contents in (('root_ca.pem', root_pem), ('intermediate_ca.pem', inter_pem),
                                ('ca-chain.pem', inter_pem + root_pem), ('meraki-ca-chain.crt', inter_pem + root_pem),
                                ('ca-bundle.pem', root_pem + inter_pem)):
            with self.subTest(route=route):
                self.assertIn(self.prefix + '/download/' + route, html)
                download = self.handler('/download/' + route)
                with patch.object(app.enroll, 'load_extra_cas', return_value=[]):
                    download.do_GET()
                self.assertEqual(download.send.call_args.args[1], contents)
                self.assertEqual(download.send.call_args.args[2], 'application/x-pem-file')
        crl = b'-----BEGIN X509 CRL-----\nfixture\n-----END X509 CRL-----\n'
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(crl)
        download = self.handler('/download/crl.pem')
        with patch.object(app.urllib.request, 'urlopen', return_value=response) as upstream:
            download.do_GET()
        upstream.assert_called_once_with(app.CRL_URL, timeout=10)
        self.assertEqual(download.send.call_args.args[1], crl)

    def test_device_trust_is_one_canonical_settings_destination(self):
        destinations = app.Handler.SECTION_PAGES['/ca']
        self.assertEqual([path for path, _, _ in destinations if 'trust' in path],
                         ['/settings/certificates/trust'])
        self.assertEqual(app.canonical_url('/tools/cas'), '/settings/certificates/trust')
        self.assertEqual(len({path for path, _, _ in destinations}), len(destinations))
        handler = self.handler('/settings/certificates/trust')
        with patch.object(app.enroll, 'load_extra_cas', return_value=[]):
            handler.cas_page({})
        html = self.html(handler)
        self.assertEqual(html.count('<h2 class="settings-title">Device trust certificates</h2>'), 1)
        self.assertNotIn('<h2>Device trust certificates</h2>', html)
        self.assertIn('<h2>Additional CA certificates</h2>', html)
        self.assertIn('<title>Device trust certificates</title>', html)


if __name__ == '__main__':
    unittest.main()
