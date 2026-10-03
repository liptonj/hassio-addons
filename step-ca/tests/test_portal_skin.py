"""Portal skin validation, real public rendering and isolated settings writes."""

import base64
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
import app
import ipsk
import portal_skin as skin


class PortalSkinTests(unittest.TestCase):
    def handler(self, kind="appearance", form=None):
        handler = app.Handler.__new__(app.Handler)
        handler.path = f"/settings/captive-portal/{kind}" + ("/save" if form is not None else "")
        handler.headers = {"X-Ingress-Path": "/api/hassio_ingress/fixture"}
        handler.allowed = lambda: True
        handler.send = MagicMock()
        if form is not None:
            body = urlencode({"csrf": app.CSRF_TOKEN, **form}, doseq=True).encode()
            handler.headers.update({"Content-Length": str(len(body)), "Content-Type": "application/x-www-form-urlencoded"})
            handler.rfile = io.BytesIO(body)
        return handler

    def image(self, format="PNG", size=(800, 400)):
        buffer = io.BytesIO()
        Image.new("RGB", size, (0, 115, 160)).save(buffer, format=format)
        return buffer.getvalue()

    def test_pages_have_scoped_fields_and_work_without_ipsk_or_remote_services(self):
        for kind in skin.FIELDS:
            handler = self.handler(kind)
            with patch.object(app, "saved_options", return_value={}), patch.object(ipsk, "PORTAL_ENABLED", False), patch.object(ipsk, "get_options") as network:
                handler.do_GET()
            network.assert_not_called()
            markup = handler.send.call_args.args[1]
            self.assertIn("Captive portal", markup)
            self.assertIn("Portal preview", markup)
            self.assertIn(f'/api/hassio_ingress/fixture/settings/captive-portal/{kind}/save', markup)
            self.assertNotIn("MariaDB required", markup)
            other = "content" if kind == "appearance" else "appearance"
            for field in skin.FIELDS[other]:
                self.assertNotIn(f'name="{field}"', markup)

    def test_scoped_save_preserves_ca_identity_and_other_skin_section(self):
        config = {**skin.DEFAULTS, "portal_name": "Fixture building"}
        options = {"ca_name": "Fixture CA", "resident_onboarding": {"duo_client_secret": "fixture-secret"}, "captive_portal": config}
        handler = self.handler(form={"accent_color": "#ffff00", "portal_name": "injected", "duo_client_secret": "injected"})
        handler.portal_skin_page = MagicMock()
        with patch.object(app, "saved_options", return_value=options), patch.object(app, "supervisor") as remote, patch.object(skin, "SETTINGS_OVERRIDE", None):
            handler.handle_post()
            self.assertEqual(skin.SETTINGS_OVERRIDE["accent_color"], "#ffff00")
        saved = remote.call_args.args[2]["options"]
        self.assertEqual(saved["ca_name"], "Fixture CA")
        self.assertEqual(saved["resident_onboarding"]["duo_client_secret"], "fixture-secret")
        self.assertEqual(saved["captive_portal"]["portal_name"], "Fixture building")
        handler.portal_skin_page.assert_called_once_with("appearance", {"saved": ["1"]})

    def test_preview_never_persists_options_or_logo_and_preserves_draft(self):
        handler = self.handler(form={"intent": "preview", "accent_color": "#f0b400", "logo_preview": base64.b64encode(self.image()).decode()})
        handler.portal_skin_page = MagicMock()
        with patch.object(app, "saved_options", return_value={}), patch.object(app, "supervisor") as remote, patch.object(skin, "store_logo") as store, patch.object(skin, "SETTINGS_OVERRIDE", None):
            handler.handle_post()
            self.assertIsNone(skin.SETTINGS_OVERRIDE)
        remote.assert_not_called()
        store.assert_not_called()
        draft = handler.portal_skin_page.call_args.kwargs
        self.assertTrue(draft["preview"])
        self.assertEqual(draft["draft"]["accent_color"], "#f0b400")
        self.assertIn('name="logo_preview"', skin.form(draft["draft"], "appearance", "", "/save", draft["logo"]))

    def test_blank_optional_content_clears_saved_values(self):
        config, _ = skin.draft({**skin.DEFAULTS, "welcome_message": "old"}, "content", {"welcome_message": [""]})
        self.assertEqual(config["welcome_message"], "")

    def test_invalid_colors_theme_and_logo_paths_cannot_generate_css_or_read_files(self):
        for key, value in (("accent_color", "red;}</style><script>"), ("background_color", "url(https://example.org)"), ("theme", 'dark"><script>'), ("logo_file", "../../secrets/password")):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    skin.normalize({key: value})
                self.assertNotIn("<script>", skin.preview({**skin.DEFAULTS, key: value}))
        self.assertIsNone(skin.logo_bytes({"logo_file": "../../secrets/password"}))

    def test_text_is_escaped_and_welcome_does_not_replace_error_or_success_headings(self):
        config = skin.normalize({"portal_name": "<script>bad</script>", "welcome_heading": "Welcome", "welcome_message": "<img onerror=bad>", "footer_text": "Help <b>here</b>"})
        markup = skin.content(config, "Check your details", "FUNCTIONAL BODY", welcome=False)
        self.assertIn("Check your details", markup)
        self.assertNotIn("<h1>Welcome", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertIn("FUNCTIONAL BODY", markup)
        self.assertNotIn("<b>here", markup)
        self.assertIn("&lt;img", skin.content(config, "Connect", "BODY", welcome=True))

    def test_colors_keep_readable_button_labels_and_links_in_both_themes(self):
        for accent in ("#ffffff", "#000000", "#ffff00", "#03a9f4", "#ff0000", "#806080"):
            self.assertGreaterEqual(skin.contrast(skin.ink(accent), accent), 4.5)
            for surface in ("#ffffff", "#1c1c1c"):
                self.assertGreaterEqual(skin.contrast(skin.link_color(accent, surface), surface), 4.5)

    def test_images_are_bounded_reencoded_and_content_addressed(self):
        for format in ("PNG", "JPEG", "WEBP"):
            normalized = skin.normalize_logo(self.image(format))
            with Image.open(io.BytesIO(normalized)) as image:
                self.assertEqual(image.format, "PNG")
                self.assertLessEqual(image.width, 512)
                self.assertLessEqual(image.height, 160)
            with tempfile.TemporaryDirectory() as directory, patch.object(skin, "LOGO_DIR", Path(directory)):
                name = skin.store_logo(normalized)
                self.assertEqual(skin.store_logo(normalized), name)
                self.assertEqual(skin.logo_bytes({"logo_file": name}), normalized)
                (Path(directory) / name).write_bytes(b"tampered")
                self.assertIsNone(skin.logo_bytes({"logo_file": name}))
        for data in (b'<svg onload="bad"/>', b"invalid", self.image(size=(2049, 2)), b"x" * (256 * 1024 + 1)):
            with self.assertRaises(ValueError):
                skin.normalize_logo(data)

    def test_logo_metadata_is_removed(self):
        image = Image.new("RGB", (16, 16), "blue")
        exif = Image.Exif()
        exif[315] = "fixture private image author"
        source = io.BytesIO()
        image.save(source, format="JPEG", exif=exif)
        with Image.open(io.BytesIO(skin.normalize_logo(source.getvalue()))) as sanitized:
            self.assertFalse(sanitized.getexif())

    def test_remove_logo_is_scoped_and_does_not_read_upload(self):
        config, logo = skin.draft({**skin.DEFAULTS, "logo_file": "a" * 64 + ".png"}, "appearance", {"remove_logo": ["1"], "logo": [b"bad"]})
        self.assertEqual(config["logo_file"], "")
        self.assertIsNone(logo)

    def test_public_renderer_preserves_security_headers_cookie_status_and_help(self):
        handler = MagicMock()
        handler.wfile = io.BytesIO()
        with patch.object(skin, "SETTINGS_OVERRIDE", {**skin.DEFAULTS, "portal_name": "Building Wi-Fi", "welcome_heading": "Welcome home"}), patch.object(ipsk.resident_access, "duo_form_origin", return_value="https://api-fixture.duosecurity.com"):
            ipsk._public_page(handler, "Your device key is ready", "FUNCTIONAL CONTENT", status=201, set_cookie="fixture-cookie")
        markup = handler.wfile.getvalue().decode()
        self.assertIn("Building Wi-Fi", markup)
        self.assertIn("Your device key is ready", markup)
        self.assertIn("FUNCTIONAL CONTENT", markup)
        self.assertNotIn("<h1>Welcome home", markup)
        handler.send_response.assert_called_once_with(201)
        headers = dict(call.args for call in handler.send_header.call_args_list)
        self.assertEqual(headers["Set-Cookie"], "fixture-cookie")
        self.assertIn("img-src data:", headers["Content-Security-Policy"])
        self.assertIn("https://api-fixture.duosecurity.com", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_restart_reads_persisted_option_and_missing_logo_falls_back(self):
        with patch.object(skin, "SETTINGS_OVERRIDE", None), patch.dict(os.environ, {"CAPTIVE_PORTAL_SETTINGS_JSON": '{"portal_name":"Saved name","theme":"dark"}'}):
            self.assertEqual(skin.settings()["portal_name"], "Saved name")
            self.assertEqual(skin.settings()["theme"], "dark")
        markup = skin.content({**skin.DEFAULTS, "logo_file": "a" * 64 + ".png"}, "Title", "BODY")
        self.assertIn('class="brand-mark"', markup)

    def test_csrf_duplicates_and_upload_request_limit_block_writes(self):
        for form, expected in (({"csrf": "wrong"}, 403), ({"intent": ["save", "preview"]}, 400)):
            handler = self.handler(form=form)
            with patch.object(app, "supervisor") as remote:
                handler.handle_post()
            remote.assert_not_called()
            self.assertEqual(handler.send.call_args.args[0], expected)
        handler = self.handler(form={})
        handler.headers["Content-Length"] = str(skin.UPLOAD_LIMIT + 1)
        handler.handle_post()
        self.assertEqual(handler.send.call_args.args[0], 413)

    def test_failed_supervisor_write_retains_runtime_skin_and_draft(self):
        handler = self.handler("content", {"portal_name": "Draft name"})
        handler.portal_skin_page = MagicMock()
        with patch.object(app, "saved_options", return_value={}), patch.object(app, "supervisor", side_effect=RuntimeError("fixture failure")), patch.object(skin, "SETTINGS_OVERRIDE", skin.DEFAULTS):
            handler.handle_post()
            self.assertEqual(skin.SETTINGS_OVERRIDE, skin.DEFAULTS)
        self.assertEqual(handler.portal_skin_page.call_args.kwargs["draft"]["portal_name"], "Draft name")
        self.assertIn("Check the Home Assistant", str(handler.portal_skin_page.call_args.kwargs["error"]))


if __name__ == "__main__":
    unittest.main()
