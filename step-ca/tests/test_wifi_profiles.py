"""Generated Apple profiles and Wi-Fi option persistence; no running CA required.

Run: python -m unittest discover -s step-ca/tests
Dependencies match the admin service (plus PyYAML for schema checks).
"""
import copy
import datetime
import io
import zipfile
from pathlib import Path
import plistlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'admin'))
import app
import enroll
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def certificate(name):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    return (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))


class WifiProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.inter = certificate('Test root'), certificate('Test intermediate')

    def profile(self, networks, **extra):
        return plistlib.loads(enroll.build_profile(
            cn='test-device', challenge='test', scep_url='https://example.invalid/scep',
            ca_name='Test CA', organization='', root=self.root, intermediate=self.inter,
            wifi=networks, **extra))

    def wifi(self, method='eap_tls', **values):
        return app.wifi_settings({'ssid': 'Office', 'authentication': method, 'radius_server': 'custom', **values})

    def test_new_wifi_profiles_default_to_access_manager_server_trust(self):
        network = app.wifi_settings({'ssid': 'Office'})
        self.assertEqual(network['radius_server'], 'meraki_access_manager')
        eap = self.payloads(self.profile(network))[0]['EAPClientConfiguration']
        self.assertEqual(eap['TLSTrustedServerNames'], ['eap.meraki.com'])
        self.assertEqual(eap['AcceptEAPTypes'], [13])
        self.assertEqual(len(eap['PayloadCertificateAnchorUUID']), 3)
        config = yaml.safe_load((Path(__file__).resolve().parents[1] / 'config.yaml').read_text())
        self.assertEqual(config['options']['wifi']['radius_server'], 'meraki_access_manager')

    def test_explicit_custom_service_is_retained(self):
        self.assertEqual(app.wifi_settings({'ssid': 'Office', 'radius_server': 'custom'})['radius_server'], 'custom')

    def test_access_manager_ttls_defaults_to_pap_and_invalid_methods_are_rejected(self):
        network = app.wifi_settings({'ssid': 'Office', 'authentication': 'eap_ttls'})
        self.assertEqual(network['ttls_inner_authentication'], 'PAP')
        app.check_wifi_option(network)
        eap = self.payloads(self.profile(network))[0]['EAPClientConfiguration']
        self.assertEqual(eap['TTLSInnerAuthentication'], 'PAP')
        self.assertEqual(eap['TLSTrustedServerNames'], ['eap.meraki.com'])
        for method in ('peap', 'eap_fast'):
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, 'Access Manager supports'):
                app.check_wifi_option(app.wifi_settings({'ssid': 'Office', 'authentication': method}))
        with self.assertRaisesRegex(ValueError, 'Choose PAP'):
            app.check_wifi_option({**network, 'ttls_inner_authentication': 'MSCHAPv2'})

    def payloads(self, profile):
        return [p for p in profile['PayloadContent'] if p['PayloadType'] == 'com.apple.wifi.managed']

    def test_all_method_ids_and_identity_use(self):
        for method, (_, eap_id, _) in enroll.WIFI_AUTH.items():
            with self.subTest(method=method):
                network = self.wifi(method, password='sample-password')
                app.check_wifi_option(network)
                payload = self.payloads(self.profile(network))[0]
                if method == 'psk':
                    self.assertEqual(payload['Password'], 'sample-password')
                    self.assertNotIn('EAPClientConfiguration', payload)
                else:
                    self.assertEqual(payload['EAPClientConfiguration']['AcceptEAPTypes'], [eap_id])
                    self.assertEqual('PayloadCertificateUUID' in payload, method == 'eap_tls')
                    self.assertNotIn('PayloadCertificateAnchorUUID', payload)
                    self.assertEqual('PayloadCertificateAnchorUUID' in payload['EAPClientConfiguration'],
                                     method in enroll.TLS_EAP)

    def test_password_prompts_and_ttls_inner_methods(self):
        for inner in enroll.TTLS_INNER:
            payload = self.payloads(self.profile(self.wifi('eap_ttls', ttls_inner_authentication=inner)))[0]
            eap = payload['EAPClientConfiguration']
            self.assertEqual(eap['TTLSInnerAuthentication'], inner)
            self.assertNotIn('UserName', eap)
            self.assertNotIn('UserPassword', eap)
        network = self.wifi('peap', eap_username='alex', eap_password='private',
                            eap_outer_identity='anonymous', eap_client_certificate=True)
        payload = self.payloads(self.profile(network))[0]
        self.assertEqual(payload['EAPClientConfiguration']['UserPassword'], 'private')
        self.assertEqual(payload['EAPClientConfiguration']['OuterIdentity'], 'anonymous')
        self.assertTrue(payload['EAPClientConfiguration']['TLSCertificateIsRequired'])
        self.assertIn('PayloadCertificateUUID', payload)
        network['eap_password_per_connection'] = True
        eap = self.payloads(self.profile(network))[0]['EAPClientConfiguration']
        self.assertTrue(eap['OneTimeUserPassword'])
        self.assertNotIn('UserPassword', eap)

    def test_tls_limits_and_pac_validation(self):
        for network in (self.wifi(tls_minimum='1.3'),
                        self.wifi('peap', tls_minimum='1.3', tls_maximum='1.3'),
                        self.wifi('eap_fast', eap_fast_use_pac=True)):
            with self.assertRaises(ValueError):
                app.check_wifi_option(network)
        network = self.wifi('eap_ttls', tls_minimum='1.3', tls_maximum='1.3', eap_outer_identity='anon')
        app.check_wifi_option(network)
        eap = self.payloads(self.profile(network))[0]['EAPClientConfiguration']
        self.assertEqual(eap['TLSMaximumVersion'], '1.3')
        eap = self.payloads(self.profile(self.wifi('eap_fast', eap_fast_use_pac=True,
                                                 eap_fast_provision_pac=True)))[0]['EAPClientConfiguration']
        self.assertTrue(eap['EAPFASTProvisionPAC'])
        self.assertFalse(eap['EAPFASTProvisionPACAnonymously'])

    def test_hosted_ca_does_not_leak_to_other_networks(self):
        hosted = self.wifi(radius_server='meraki_access_manager', name='Hosted')
        own = self.wifi(ssid='Private', name='Private')
        again = self.wifi(ssid='Second', radius_server='meraki_access_manager', name='Second')
        profile = self.profile([hosted, own, again])
        w1, w2, w3 = self.payloads(profile)
        a1, a2, a3 = (p['EAPClientConfiguration']['PayloadCertificateAnchorUUID'] for p in (w1, w2, w3))
        self.assertEqual(len(a1), 3)
        self.assertEqual(len(a2), 2)
        self.assertEqual(a1, a3)
        refs = {p['PayloadUUID'] for p in profile['PayloadContent']}
        self.assertTrue(set(a1) <= refs)
        self.assertEqual(w1['EAPClientConfiguration']['TLSTrustedServerNames'], ['eap.meraki.com'])
        self.assertNotIn('TLSTrustedServerNames', w2['EAPClientConfiguration'])

    def test_sim_platform_and_passpoint(self):
        for method in ('eap_sim', 'eap_aka'):
            with self.assertRaisesRegex(ValueError, 'iOS profile'):
                self.profile(self.wifi(method), platform='macos')
        for method in ('eap_tls', 'eap_ttls', 'peap', 'eap_sim', 'eap_aka'):
            app.check_wifi_option(self.wifi(method, ssid='', passpoint=True, passpoint_domain='example.com'))
        for method in ('psk', 'leap'):
            with self.assertRaises(ValueError):
                app.check_wifi_option(self.wifi(method, password='sample-password', passpoint=True,
                                               passpoint_domain='example.com'))
        with self.assertRaises(ValueError):
            app.check_wifi_option(self.wifi('peap', mac_login_window=True))
        eap = self.payloads(self.profile(self.wifi('eap_sim', eap_sim_rands=2)))[0]['EAPClientConfiguration']
        self.assertEqual(eap['EAPSIMNumberOfRANDs'], 2)

    def test_optional_name_and_exact_ssid(self):
        app.check_wifi_option(self.wifi(name=''))
        with self.assertRaises(ValueError):
            app.check_wifi_option(self.wifi(ssid='', name='Named profile'))
        with self.assertRaises(ValueError):
            app.check_wifi_option(self.wifi(ssid='é' * 17))
        payload = self.payloads(self.profile(self.wifi(ssid=' Office ')))[0]
        self.assertEqual(payload['SSID_STR'], ' Office ')

    def test_no_secrets_in_edit_html(self):
        handler = object.__new__(app.Handler)
        handler.headers = {}
        values = dict(self.wifi('peap', eap_password='do-not-render', password='also-private',
                               proxy_password='proxy-private'), original='Office')
        markup = handler.wifi_form('', values)
        for secret in ('do-not-render', 'also-private', 'proxy-private'):
            self.assertNotIn(secret, markup)
        self.assertIn('clear_eap_password', markup)

    def test_save_preserves_and_clears_passwords_and_ssid_spaces(self):
        handler = object.__new__(app.Handler)
        handler.headers = {}
        handler.redirect = lambda path: None
        handler.wifi_page = lambda *args: self.fail(str(args))
        saved = self.wifi('peap', name='Office', eap_password='saved-secret')
        options = {'wifi_networks': [app.wifi_option(saved)]}
        form = {key: [str(value)] for key, value in saved.items() if not isinstance(value, (bool, list))
                and value is not None}
        form.update(original=['Office'], eap_password=[''], ssid=[' Office '])
        for clear in (False, True):
            with self.subTest(clear=clear), patch.object(app, 'saved_options', return_value=copy.deepcopy(options)), \
                    patch.object(app.Handler, 'save_wifi_networks') as save:
                form['clear_eap_password'] = ['1' if clear else '']
                handler.wifi_save(form)
                network = save.call_args.args[1][0]
                self.assertEqual(network['eap_password'], '' if clear else 'saved-secret')
                self.assertEqual(network['ssid'], ' Office ')

    def test_bundle_keeps_ios_when_sim_is_unavailable_on_mac(self):
        networks = [self.wifi('eap_sim', name='Carrier', include_by_default=False), self.wifi()]
        with patch.object(app, 'WIFI_NETWORKS', networks), patch.object(app, 'SCEP_CHALLENGE', 'test'), \
                patch.object(app, 'cert_chain', return_value=(self.root, self.inter)):
            data, _ = app.mdm_bundle('test-device', 'https://example.invalid')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.namelist()
            self.assertTrue(any('carrier' in name and name.startswith(app.MDM_PLATFORMS['ios'] + '/') for name in files))
            self.assertFalse(any('carrier' in name and name.startswith(app.MDM_PLATFORMS['macos'] + '/') for name in files))
            self.assertTrue(any(name.startswith(app.MDM_PLATFORMS['macos'] + '/') for name in files))
            self.assertIn('README.txt', files)
            self.assertIn('Carrier', archive.read('README.txt').decode())

    def test_legacy_method_does_not_apply_hidden_tunnel_settings(self):
        eap = enroll.eap_configuration(self.wifi('leap', eap_password='test',
                                                 eap_password_per_connection=True), 'device')
        self.assertEqual(eap['UserPassword'], 'test')
        self.assertNotIn('OneTimeUserPassword', eap)
        self.assertNotIn('TLSMinimumVersion', eap)

    def test_hidden_auth_settings_do_not_block_another_method(self):
        stale = dict(radius_server_names=['radius.example.com?'], tls_minimum='1.3', tls_maximum='1.2',
                     ttls_inner_authentication='invalid', eap_outer_identity='bad\nidentity')
        for method in ('eap_sim', 'eap_aka', 'leap', 'psk'):
            app.check_wifi_option(self.wifi(method, password='sample-password', **stale))
        with self.assertRaises(ValueError):
            app.check_wifi_option(self.wifi(radius_server_names=['radius.example.com?']))
        # Inner-TTLS settings do not apply to PEAP; SIM challenges do not apply to TLS.
        app.check_wifi_option(self.wifi('peap', ttls_inner_authentication='invalid', eap_sim_rands=-1))

    def test_reference_settings_match_the_selected_method(self):
        for method in enroll.WIFI_AUTH:
            with self.subTest(method=method):
                settings = app.mdm_wifi_settings(self.wifi(method, eap_password='never-display-this',
                                                           ttls_inner_authentication='PAP'))
                self.assertIn(enroll.WIFI_AUTH[method][0], settings)
                self.assertNotIn('never-display-this', settings)
                if method != 'eap_tls':
                    self.assertNotIn('EAP-TLS', settings)
                self.assertEqual('trusted server names =' in settings, method in enroll.TLS_EAP)
                if method == 'eap_ttls':
                    self.assertIn('inner authentication = PAP', settings)
                if method in ('eap_sim', 'eap_aka'):
                    self.assertIn('carrier SIM', settings)
        settings = app.mdm_wifi_settings(self.wifi('peap', eap_client_certificate=True,
                                                  radius_server='meraki_access_manager'))
        self.assertIn('also require client certificate = the SCEP payload', settings)
        self.assertIn('eap.meraki.com', settings)
        handler = object.__new__(app.Handler)
        handler.headers = {}
        captured = []
        handler.page = lambda title, body, **kwargs: captured.append(body)
        with patch.object(app, 'WIFI_NETWORKS', [self.wifi('eap_ttls')]):
            handler.options_page()
        self.assertIn('EAP-TTLS', captured[0])
        self.assertNotIn('EAP-TLS', captured[0])

    def test_device_profile_propagates_platform_and_rejects_mac_sim(self):
        with patch.object(app, 'WIFI_NETWORKS', [self.wifi('eap_sim')]), \
                patch.object(app, 'cert_chain', return_value=(self.root, self.inter)), \
                patch.object(app.SIGNER, 'sign', side_effect=lambda xml: xml):
            with self.assertRaises(enroll.UnsupportedWifiPlatform):
                app.profile_for('device', 'challenge', 'https://example.invalid', True, platform='macos')
            payload = self.payloads(plistlib.loads(app.profile_for(
                'device', 'challenge', 'https://example.invalid', True, platform='ios')))[0]
            self.assertEqual(payload['EAPClientConfiguration']['AcceptEAPTypes'], [18])

    def test_schema_covers_new_options(self):
        config = yaml.safe_load((Path(__file__).resolve().parents[1] / 'config.yaml').read_text())
        for schema in (config['schema']['wifi'], config['schema']['wifi_networks'][0]):
            for method in enroll.WIFI_AUTH:
                self.assertIn(method, schema['authentication'])
            for field in ('eap_username', 'eap_password', 'eap_outer_identity', 'tls_minimum', 'tls_maximum',
                          'ttls_inner_authentication', 'eap_sim_rands', 'eap_fast_use_pac'):
                self.assertIn(field, schema)


if __name__ == '__main__':
    unittest.main()
