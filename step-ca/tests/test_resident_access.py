"""Group-scoped resident self-service. All Duo, Wi-Fi and DB operations mocked."""

import http.client
import io
from pathlib import Path
import re
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import captive
import ipsk
import resident_access as access

CONFIG = {"self_service_enabled": True, "sign_in_required": True, "no_sign_in_user_list": False,
          "network_id": "N_fixture", "ssid_number": 0, "max_devices_per_resident": 5,
          "invite_required": False, "duo_group_id": "DG" + "A" * 18,
          "duo_admin_hostname": "api-fixture.duosecurity.com", "duo_admin_integration_key": "DI" + "A" * 18,
          "duo_admin_secret": "a" * 40, "duo_api_hostname": "api-fixture.duosecurity.com",
          "duo_client_id": "DI" + "B" * 18, "duo_client_secret": "b" * 40,
          "duo_redirect_uri": "https://ha.example.org/api/step_ca_scep/portal?action=duo_callback"}
IDENTITY = {"owner": "duo:DUresident", "user_id": "DUresident", "username": "resident",
            "name": "Test Resident", "email": "resident@example.org", "verified": True}
MAC = "00:11:22:33:44:55"


class DuoPolicy(unittest.TestCase):
    def test_valid_config_and_missing_group_or_credentials_fail_closed(self):
        access.validate_settings(CONFIG)
        for key in ("duo_group_id", "duo_admin_secret", "duo_client_secret", "duo_redirect_uri"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                access.validate_settings({**CONFIG, key: ""})

    def test_callback_and_api_host_are_restricted(self):
        for callback in ("http://ha.example.org/api/step_ca_scep/portal?action=duo_callback",
                         "https://ha.example.org/other", CONFIG["duo_redirect_uri"] + "&evil=1",
                         "https://user@ha.example.org/api/step_ca_scep/portal?action=duo_callback"):
            with self.subTest(callback=callback), self.assertRaises(ValueError):
                access.validate_settings({**CONFIG, "duo_redirect_uri": callback})
        with self.assertRaises(ValueError):
            access.validate_settings({**CONFIG, "duo_admin_hostname": "127.0.0.1"})

    def test_directory_uses_only_selected_group_and_follows_sdk_paging(self):
        client = MagicMock()
        client.get_group.return_value = {"status": "active"}
        client.get_group_users_iterator.return_value = iter([
            {"user_id": "DU2", "username": "Zulu"}, {"user_id": "DU1", "username": "Alice"}])
        with patch.object(access, "admin_client", return_value=client):
            result = access.group_members(CONFIG)
        self.assertEqual([m["username"] for m in result], ["Alice", "Zulu"])
        client.get_group_users_iterator.assert_called_once_with(CONFIG["duo_group_id"])
        client.get_users.assert_not_called()
        client.get_group.assert_called_once_with(CONFIG["duo_group_id"], api_version=2)

    def test_forged_user_selection_never_fetches_arbitrary_user(self):
        with patch.object(access, "group_members", return_value=[{"user_id":"DUallowed", "username":"allowed"}]), \
                patch.object(access, "admin_client") as client:
            with self.assertRaisesRegex(ValueError, "not in the permitted group"):
                access.member_identity(CONFIG, user_id="DUoutsider")
        client.assert_not_called()

    def test_directory_accepts_documented_active_group_status_casing(self):
        for status in ("Active", "active"):
            with self.subTest(status=status):
                client = MagicMock()
                client.get_group.return_value = {"status": status}
                client.get_group_users_iterator.return_value = iter([])
                with patch.object(access, "admin_client", return_value=client):
                    self.assertEqual(access.group_members(CONFIG), [])
                client.get_group_users_iterator.assert_called_once_with(CONFIG["duo_group_id"])
                client.get_users.assert_not_called()

    def test_directory_rejects_bypassed_disabled_and_unknown_group_statuses(self):
        for status in ("Bypass", "bypass", "Disabled", "disabled", "unknown", None):
            with self.subTest(status=status):
                client = MagicMock()
                client.get_group.return_value = {"status": status}
                with patch.object(access, "admin_client", return_value=client), self.assertRaises(ValueError):
                    access.group_members(CONFIG)
                client.get_group_users_iterator.assert_not_called()
                client.get_users.assert_not_called()

    def test_locked_user_and_inactive_group_are_rejected(self):
        client = MagicMock()
        client.get_group.return_value = {"status":"disabled"}
        with patch.object(access, "admin_client", return_value=client), self.assertRaises(ValueError):
            access.group_members(CONFIG)
        client.get_group_users_iterator.assert_not_called()
        client.get_user_by_id.return_value = {"user_id":"DUresident", "status":"locked out"}
        with patch.object(access, "group_members", return_value=[{"user_id":"DUresident", "username":"resident"}]), \
                patch.object(access, "admin_client", return_value=client), self.assertRaises(ValueError):
            access.member_identity(CONFIG, user_id="DUresident")

    def test_session_is_expiring_bounded_and_invalidated_by_policy_change(self):
        handler = MagicMock()
        with patch.object(access, "SESSIONS", {}):
            token, session = access.new_session(CONFIG)
            handler.headers = {"Cookie": "resident_session=" + token}
            self.assertIs(access.session_for(handler, CONFIG)[1], session)
            self.assertIsNone(access.session_for(handler, {**CONFIG,"sign_in_required":False})[1])
            token, session = access.new_session(CONFIG)
            session["expires"] = time.monotonic() - 1
            handler.headers = {"Cookie":"resident_session=" + token}
            self.assertIsNone(access.session_for(handler, CONFIG)[1])
            for _ in range(1000):
                access.new_session(CONFIG)
            with self.assertRaises(RuntimeError):
                access.new_session(CONFIG)

    def test_sdk_dependencies_and_signatures_are_available(self):
        client = access.universal_client(CONFIG)
        state = client.generate_state()
        auth_url = client.create_auth_url("resident", state, nonce="n" * 32)
        self.assertTrue(auth_url.startswith("https://api-fixture.duosecurity.com/oauth/v1/authorize?"))
        admin = access.admin_client(CONFIG)
        self.assertTrue(callable(admin.get_group_users_iterator))

    def test_lazy_directory_errors_do_not_include_provider_response(self):
        client = MagicMock()
        client.get_group.return_value = {"status": "active"}
        def pages():
            yield {"user_id": "DU1", "username": "Resident"}
            raise ValueError("fixture-reflected-secret")
        client.get_group_users_iterator.return_value = pages()
        with patch.object(access, "admin_client", return_value=client):
            with self.assertRaises(RuntimeError) as caught:
                access.group_members(CONFIG)
        self.assertNotIn("fixture-reflected-secret", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)


class AccessHttpFlow(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(ipsk, "PORTAL_ENABLED", True), patch.object(ipsk, "RATE_LIMIT", {}),
                        patch.object(ipsk, "CAPTIVE_SESSIONS", captive.CaptiveSessions()),
                        patch.object(ipsk.PublicPortalHandler, "allowed_clients", {"127.0.0.1"}),
                        patch.object(access, "SETTINGS_OVERRIDE", dict(CONFIG)), patch.object(access, "SESSIONS", {})]
        for item in self.patches:
            item.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ipsk.PublicPortalHandler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        for item in reversed(self.patches):
            item.stop()

    def request(self, method="GET", action="account", form=None, cookie="", query=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        path = "/portal?" + urlencode({"action":action, **(query or {})})
        connection.request(method, path, urlencode(form) if form is not None else None,
                           {"Cookie":cookie, "Content-Type":"application/x-www-form-urlencoded"})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    def session(self, identity=None, context=""):
        token, session = access.new_session(access.settings(), context, identity)
        return token, session, "resident_session=" + token

    def pending(self):
        token, session, cookie = self.session()
        session["pending"] = {"identity":dict(IDENTITY), "state":"test-state", "nonce":"n"*32,
                              "expires":time.monotonic()+300}
        return token, session, cookie

    def test_direct_duo_visit_has_login_and_secure_lax_cookie(self):
        status, headers, page = self.request()
        self.assertEqual(status, 200)
        self.assertIn("Continue with Duo", page)
        self.assertIn("HttpOnly; Secure; SameSite=Lax", headers["Set-Cookie"])
        self.assertNotIn("Create device key", page)

    def test_captive_entry_renders_each_configured_authentication_mode(self):
        modes = ((True, True, False, "Continue with Duo"),
                 (True, False, True, "Resident account"),
                 (True, False, False, "Full name"),
                 (False, False, False, "Get Wi-Fi access"))
        for self_service, sign_in, directory, expected in modes:
            with self.subTest(sign_in=sign_in, directory=directory, self_service=self_service):
                access.SETTINGS_OVERRIDE.update(self_service_enabled=self_service,
                                               sign_in_required=sign_in,
                                               no_sign_in_user_list=directory)
                with patch.object(access, "group_members", return_value=[
                        {"user_id": "DUresident", "username": "resident", "display_name": "Resident"}]):
                    status, _, page = self.request(action="", query={
                        "client_mac": MAC, "base_grant_url": "https://n1.network-auth.com/splash/grant"})
                self.assertEqual(status, 200)
                self.assertIn(expected, page)
                if not sign_in:
                    self.assertNotIn("Continue with Duo", page)

    def test_no_sign_in_cannot_load_directory_without_captive_entry(self):
        access.SETTINGS_OVERRIDE.update(sign_in_required=False, no_sign_in_user_list=True)
        with patch.object(access, "group_members") as members:
            status, _, page = self.request()
        self.assertEqual(status, 200)
        self.assertIn("Connect to setup Wi-Fi", page)
        members.assert_not_called()

    def test_private_mac_cannot_reach_group_directory(self):
        access.SETTINGS_OVERRIDE.update(sign_in_required=False,no_sign_in_user_list=True)
        with patch.object(access,"group_members") as members:
            status, _, _ = self.request(action="",query={"client_mac":"02:11:22:33:44:55",
                                                        "base_grant_url":"https://n1.network-auth.com/splash/grant"})
        self.assertEqual(status, 403)
        members.assert_not_called()

    def test_username_is_checked_before_duo_login(self):
        _, session, cookie = self.session()
        with patch.object(access,"member_identity",side_effect=ValueError("not permitted")), \
                patch.object(access,"universal_client") as sdk:
            status, _, _ = self.request("POST","duo_login",{"csrf":session["csrf"],"username":"outsider"},cookie)
        self.assertEqual(status, 400)
        sdk.assert_not_called()

    def test_callback_binds_cookie_state_nonce_and_rotates_session(self):
        token, session, cookie = self.pending()
        client = MagicMock()
        client.exchange_authorization_code_for_2fa_result.return_value = {
            "auth_result":{"result":"allow"},"amr":["mfa"],"preferred_username":"resident"}
        with patch.object(access,"universal_client",return_value=client), \
                patch.object(access,"member_identity",return_value=dict(IDENTITY)):
            status, headers, _ = self.request(action="duo_callback",cookie=cookie,
                                              query={"state":"test-state","duo_code":"fixture-code"})
            self.assertEqual(status, 303)
            self.assertIn("action=account",headers["Location"])
            self.assertNotIn(token, access.SESSIONS)
            self.assertNotIn(token,headers["Set-Cookie"])
            status, _, _ = self.request(action="duo_callback",cookie=cookie,
                                        query={"state":"test-state","duo_code":"fixture-code"})
            self.assertEqual(status,403)
        client.exchange_authorization_code_for_2fa_result.assert_called_once_with("fixture-code","resident","n"*32)

    def test_wrong_state_cannot_exchange_code(self):
        _, _, cookie = self.pending()
        with patch.object(access,"universal_client") as sdk:
            status, _, _ = self.request(action="duo_callback",cookie=cookie,
                                        query={"state":"wrong","duo_code":"fixture-code"})
        self.assertEqual(status,403)
        sdk.assert_not_called()

    def test_bypass_or_wrong_user_cannot_sign_in(self):
        for result in ({"auth_result":{"result":"allow"},"preferred_username":"resident"},
                       {"auth_result":{"result":"allow"},"amr":["mfa"],"preferred_username":"outsider"}):
            _, _, cookie = self.pending()
            client = MagicMock()
            client.exchange_authorization_code_for_2fa_result.return_value=result
            with patch.object(access,"universal_client",return_value=client):
                status, _, _ = self.request(action="duo_callback",cookie=cookie,
                                            query={"state":"test-state","duo_code":"fixture-code"})
            self.assertEqual(status,403)
            self.assertFalse(any(s["identity"] for s in access.SESSIONS.values()))

    def test_required_auth_cannot_be_bypassed_with_choose_or_legacy_post(self):
        _, session, cookie = self.session()
        for action in ("choose", ""):
            with patch.object(access,"create_device") as create,patch.object(ipsk,"register_resident") as register:
                status, _, _ = self.request("POST",action,{"csrf":session["csrf"],"name":"Fake Resident","email":"fake@example.org"},cookie)
            self.assertEqual(status,400)
            create.assert_not_called()
            register.assert_not_called()

    def test_forged_csrf_and_removed_member_cannot_create(self):
        _, session, cookie = self.session(dict(IDENTITY))
        form={"csrf":"forged","target":"other","device":"TV","mac":MAC}
        with patch.object(access,"create_device") as create:
            status, _, _=self.request("POST","create_device",form,cookie)
            self.assertEqual(status,400)
            form["csrf"]=session["csrf"]
            with patch.object(access,"member_identity",side_effect=ValueError("removed from group")):
                status, _, _=self.request("POST","create_device",form,cookie)
            self.assertEqual(status,400)
            create.assert_not_called()

    def test_device_creation_uses_session_owner_and_consumes_form_token(self):
        _, session, cookie=self.session(dict(IDENTITY))
        form={"csrf":session["csrf"],"target":"other","device":"TV","mac":MAC,"user_id":"outsider"}
        with patch.object(access,"member_identity",return_value=dict(IDENTITY)), \
                patch.object(access,"create_device",return_value={"name":"TV","ssid":"Fixture Wi-Fi","passphrase":"fixture-password"}) as create:
            status, _, page=self.request("POST","create_device",form,cookie)
            self.assertEqual(status,200)
            self.assertIn("device-wifi.svg",page)
            self.assertIn("Add another device",page)
            self.assertEqual(create.call_args.args[2]["owner"],IDENTITY["owner"])
            status, _, _=self.request("POST","create_device",form,cookie)
            self.assertEqual(status,400)
            self.assertEqual(create.call_count,1)

    def test_successful_creation_keeps_busy_until_old_form_token_is_consumed(self):
        _, session, cookie = self.session(dict(IDENTITY))
        old_csrf = session["csrf"]
        form = {"csrf": old_csrf, "target": "other", "device": "TV", "mac": MAC}
        observations = []
        def rotate(length):
            if length == 32:
                observations.append((session["busy"], session["csrf"]))
                return "fixture-new-csrf"
            return "fixture-script-nonce"
        with patch.object(access, "member_identity", return_value=dict(IDENTITY)), \
                patch.object(access, "create_device", return_value={"name": "TV", "ssid": "Fixture Wi-Fi", "passphrase": "fixture-password"}), \
                patch.object(access.secrets, "token_urlsafe", side_effect=rotate):
            status, _, _ = self.request("POST", "create_device", form, cookie)
        self.assertEqual(status, 200)
        self.assertEqual(observations, [(True, old_csrf)])
        self.assertFalse(session["busy"])
        self.assertEqual(session["csrf"], "fixture-new-csrf")

    def test_duo_form_policy_permits_only_configured_host(self):
        status, headers, _ = self.request()
        self.assertEqual(status, 200)
        self.assertIn("form-action 'self' https://api-fixture.duosecurity.com;", headers["Content-Security-Policy"])
        self.assertNotIn("*.duosecurity.com", headers["Content-Security-Policy"])
        with patch.object(access, "SETTINGS_OVERRIDE", {**CONFIG, "sign_in_required": False}):
            self.assertEqual(access.duo_form_origin(), "")
        with patch.object(access, "SETTINGS_OVERRIDE", {**CONFIG, "duo_api_hostname": "api-duo.duosecurity.com; form-action *"}):
            self.assertEqual(access.duo_form_origin(), "")

    def test_directory_provider_value_error_is_generic_on_resident_page(self):
        access.SETTINGS_OVERRIDE.update(sign_in_required=False, no_sign_in_user_list=True)
        _, _, cookie = self.session()
        client = MagicMock()
        client.get_group.side_effect = ValueError("fixture-reflected-secret")
        with patch.object(access, "admin_client", return_value=client):
            status, _, page = self.request(cookie=cookie)
        self.assertEqual(status, 503)
        self.assertNotIn("fixture-reflected-secret", page)
        self.assertIn("could not reach the resident service", page)

    def test_duo_token_exchange_errors_do_not_expose_provider_body(self):
        _, _, cookie = self.pending()
        client = MagicMock()
        client.exchange_authorization_code_for_2fa_result.side_effect = ValueError("fixture-reflected-secret")
        with patch.object(access, "universal_client", return_value=client):
            status, _, page = self.request(action="duo_callback", cookie=cookie,
                                          query={"state": "test-state", "duo_code": "fixture-code"})
        self.assertEqual(status, 503)
        self.assertNotIn("fixture-reflected-secret", page)
        self.assertFalse(any(s["identity"] for s in access.SESSIONS.values()))

    def test_no_sign_in_selection_is_unverified_and_session_rotates(self):
        access.SETTINGS_OVERRIDE.update(sign_in_required=False,no_sign_in_user_list=True)
        token, session, cookie=self.session()
        with patch.object(access,"member_identity",return_value={**IDENTITY,"verified":False}):
            status, headers, _=self.request("POST","choose",{"csrf":session["csrf"],"user_id":"DUresident"},cookie)
        self.assertEqual(status,303)
        self.assertNotIn(token,access.SESSIONS)
        self.assertFalse(next(iter(access.SESSIONS.values()))["identity"]["verified"])

    def test_device_validation_error_preserves_draft_and_shows_recovery_form(self):
        _, session, cookie = self.session(dict(IDENTITY))
        form = {"csrf":session["csrf"],"target":"other","device":"Bedroom speaker", "mac":"02:11:22:33:44:55", "unit":"101"}
        with patch.object(access,"member_identity",return_value=dict(IDENTITY)), \
                patch.object(access,"create_device",side_effect=ValueError("Turn off private addressing")):
            status, _, page = self.request("POST","create_device",form,cookie)
        self.assertEqual(status,400)
        self.assertIn('value="Bedroom speaker"',page)
        self.assertIn('value="101"',page)
        self.assertIn("Create device key and QR",page)

    def test_public_script_nonce_matches_policy_and_is_fresh(self):
        pages = [self.request() for _ in range(2)]
        nonces = []
        for status, headers, page in pages:
            self.assertEqual(status, 200)
            nonce = re.search(r'<script nonce="([A-Za-z0-9_-]+)">', page)[1]
            nonces.append(nonce)
            self.assertIn("script-src 'nonce-" + nonce + "'", headers["Content-Security-Policy"])
            self.assertNotIn("script-src 'unsafe-inline'", headers["Content-Security-Policy"])
            self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotEqual(*nonces)

    def test_current_device_form_marks_other_mac_for_conditional_validation(self):
        context = ipsk.CAPTIVE_SESSIONS.create(MAC, "https://n123.network-auth.com/splash/grant", "https://example.org")
        _, session, cookie = self.session(dict(IDENTITY), context)
        with patch.object(access, "member_identity", return_value=dict(IDENTITY)):
            status, _, page = self.request(cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('data-show-when="target=other" data-control-when-visible', page)
        self.assertIn('data-required-when-visible', page)
        self.assertIn('id="other-device-help"', page)
        self.assertIn("control.disabled = block.hidden", page)
        self.assertIn("control.required = !block.hidden", page)

    def test_success_guidance_branches_for_current_and_other_devices(self):
        for target in ("current", "other"):
            with self.subTest(target=target):
                context = ipsk.CAPTIVE_SESSIONS.create(MAC, "https://n123.network-auth.com/splash/grant", "https://example.org")
                _, session, cookie = self.session(dict(IDENTITY), context)
                form = {"csrf": session["csrf"], "target": target, "device": "TV", "mac": MAC}
                with patch.object(access, "member_identity", return_value=dict(IDENTITY)), \
                        patch.object(access, "create_device", return_value={"name":"TV", "ssid":"Fixture Wi-Fi", "passphrase":"fixture-password"}):
                    status, _, page = self.request("POST", "create_device", form, cookie)
                self.assertEqual(status, 200)
                self.assertIn("Save this Wi-Fi password before leaving", page)
                self.assertIn('aria-label="Copy Wi-Fi password"', page)
                self.assertIn("private or randomized addressing off", page)
                self.assertIn('class="btn text" href="', page)
                self.assertIn("Finish session", page)
                if target == "current":
                    self.assertIn("open Wi-Fi settings and join Fixture Wi-Fi", page)
                    self.assertIn("Finish setup", page)
                    self.assertIn("five-minute access window", page)
                else:
                    self.assertIn("Scan this QR with the other device", page)
                    self.assertNotIn("Finish setup</a>", page)

    def test_legacy_validation_recovery_preserves_and_escapes_non_secret_values(self):
        config = {**CONFIG, "self_service_enabled":False, "sign_in_required":False, "no_sign_in_user_list":False}
        context = ipsk.CAPTIVE_SESSIONS.create(MAC, "https://n123.network-auth.com/splash/grant", "https://example.org")
        form = {"csrf":context, "name":'Alex <script>', "email":"alex@example.org", "unit":'A"1', "invite":"secret-invite"}
        with patch.object(access, "SETTINGS_OVERRIDE", config), \
                patch.object(ipsk, "register_resident", side_effect=ValueError("Check your invitation")):
            status, _, page = self.request("POST", "", form, "portal_csrf=" + context)
        self.assertEqual(status, 400)
        self.assertIn('value="Alex &lt;script&gt;"', page)
        self.assertIn('value="alex@example.org"', page)
        self.assertIn('value="A&quot;1"', page)
        self.assertNotIn("secret-invite", page)
        self.assertIn("Get Wi-Fi access", page)
        self.assertIsNotNone(ipsk.CAPTIVE_SESSIONS.get(context))


class DevicePersistence(unittest.TestCase):
    def setUp(self):
        remote = patch.object(ipsk, "inactive_ipsk_ids", return_value=[])
        remote.start()
        self.addCleanup(remote.stop)

    def connection(self, responses):
        conn, cur=MagicMock(),MagicMock()
        conn.cursor.return_value.__enter__.return_value=cur
        cur.fetchone.side_effect=[{"acquired": 1}, *responses]
        return conn,cur

    def test_device_creation_stores_attribution_mac_and_verification_in_stepca_db(self):
        conn,cur=self.connection([{"owner_key":IDENTITY["owner"]},{"count":0},{"count":0},None,{"id":42}])
        config={**CONFIG,"invite_required":True}
        with patch.object(ipsk,"db_connect",return_value=conn), \
                patch.object(ipsk,"create_ipsk",return_value={"id":"fixture-key","ssid_name":"Fixture Wi-Fi","passphrase":"fixture-password"}):
            result=access.create_device(ipsk,config,IDENTITY,"TV",MAC,"101","INVITE","192.0.2.1")
        self.assertEqual(result["ssid"],"Fixture Wi-Fi")
        inserts=[call.args for call in cur.execute.call_args_list if "INSERT INTO stepca_resident_devices" in call.args[0]]
        self.assertEqual(inserts[0][1],(IDENTITY["owner"],"TV","101",MAC,"fixture-key","192.0.2.1",True))
        self.assertTrue(any("FOR UPDATE" in c.args[0] for c in cur.execute.call_args_list))
        self.assertTrue(any("SET used_at" in c.args[0] for c in cur.execute.call_args_list))
        conn.commit.assert_called_once()

    def test_random_device_mac_cannot_connect_to_db_or_create_key(self):
        with patch.object(ipsk,"db_connect") as db,patch.object(ipsk,"create_ipsk") as create:
            with self.assertRaises(captive.DeviceAddressError):
                access.create_device(ipsk,CONFIG,IDENTITY,"TV","02:11:22:33:44:55","","","192.0.2.1")
        db.assert_not_called()
        create.assert_not_called()

    def test_quota_and_duplicate_device_fail_before_key_creation(self):
        for responses in ([{}, {"count":5},{"count":0}], [{},{"count":0},{"count":0},{"mac_address":MAC}]):
            conn,_=self.connection(responses)
            with patch.object(ipsk,"db_connect",return_value=conn),patch.object(ipsk,"create_ipsk") as create:
                with self.assertRaises(ValueError):
                    access.create_device(ipsk,CONFIG,IDENTITY,"TV",MAC,"","","192.0.2.1")
            create.assert_not_called()
            conn.rollback.assert_called_once()

    def test_missing_authoritative_ssid_rolls_back_and_removes_created_key(self):
        conn,_=self.connection([{}, {"count":0},{"count":0},None])
        with patch.object(ipsk,"db_connect",return_value=conn), \
                patch.object(ipsk,"create_ipsk",return_value={"id":"created-key","passphrase":"fixture-password"}), \
                patch.object(ipsk,"set_ipsk_status") as cleanup:
            with self.assertRaises(ValueError):
                access.create_device(ipsk,CONFIG,IDENTITY,"TV",MAC,"","","192.0.2.1")
        conn.rollback.assert_called_once()
        cleanup.assert_called_once_with("created-key","delete")


class AdminAccessSettings(unittest.TestCase):
    def test_settings_save_preserves_blank_secrets_and_other_options(self):
        config={**CONFIG,"sign_in_required":False,"no_sign_in_user_list":True}
        form={"csrf":app.CSRF_TOKEN,"self_service_enabled":"1","no_sign_in_user_list":"1","max_devices_per_resident":"7",
              **{k:config.get(k,"") for k in access.TEXT_FIELDS}}
        body=urlencode(form).encode()
        handler=app.Handler.__new__(app.Handler)
        handler.path="/residents/access/settings"
        handler.headers={"Content-Length":str(len(body)),"Content-Type":"application/x-www-form-urlencoded"}
        handler.rfile=io.BytesIO(body)
        handler.residents_page=MagicMock()
        with patch.object(app,"saved_options",return_value={"ca_name":"Fixture CA","resident_onboarding":config}), \
                patch.object(app,"supervisor") as supervisor,patch.object(access,"SETTINGS_OVERRIDE",None):
            handler.handle_post()
            saved=supervisor.call_args.args[2]["options"]
            self.assertEqual(saved["ca_name"],"Fixture CA")
            self.assertEqual(saved["resident_onboarding"]["duo_admin_secret"],config["duo_admin_secret"])
            self.assertEqual(saved["resident_onboarding"]["max_devices_per_resident"],7)
            self.assertFalse(saved["resident_onboarding"]["sign_in_required"])
            self.assertEqual(access.SETTINGS_OVERRIDE,saved["resident_onboarding"])
        handler.residents_page.assert_called_once_with({"access_saved":["1"]}, section="access")

    def test_settings_card_never_inserts_saved_secret_values(self):
        card=access.admin_settings_card(ipsk,CONFIG,"csrf-field","/settings")
        for key in access.SECRET_FIELDS:
            self.assertNotIn(CONFIG[key],card)
        self.assertIn("Only this group",card)


if __name__ == "__main__":
    unittest.main()
