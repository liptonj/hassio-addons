"""Shared captive portal branding, safe image storage and scoped settings forms."""

import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image, UnidentifiedImageError

import guidance
import ui

DEFAULTS = {
    "theme": "auto", "accent_color": "#03a9f4", "background_color": "",
    "logo_file": "", "portal_name": "Resident Wi-Fi", "welcome_heading": "",
    "welcome_message": "", "footer_text": "",
}
FIELDS = {
    "appearance": ("theme", "accent_color", "background_color", "logo_file"),
    "content": ("portal_name", "welcome_heading", "welcome_message", "footer_text"),
}
LIMITS = {"portal_name": 64, "welcome_heading": 80, "welcome_message": 600, "footer_text": 200}
LOGO_DIR = Path(os.environ.get("STEPPATH", "/data/step")) / "portal"
UPLOAD_LIMIT = 280 * 1024
SETTINGS_OVERRIDE = None


def esc(value):
    return html.escape(str(value or ""), quote=True)


def normalize(config):
    result = {**DEFAULTS, **{k: v for k, v in config.items() if k in DEFAULTS}}
    if result["theme"] not in ("auto", "light", "dark"):
        raise guidance.FieldError("theme", "Choose automatic, light or dark appearance.")
    for key in ("accent_color", "background_color"):
        value = str(result[key]).strip()
        if not (key == "background_color" and not value) and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise guidance.FieldError(key, "Enter a six-digit hex color, such as #03a9f4.")
        result[key] = value.lower()
    if result["logo_file"] and not re.fullmatch(r"[0-9a-f]{64}\.png", str(result["logo_file"])):
        raise ValueError("The saved portal logo reference is invalid. Upload the logo again.")
    for key, limit in LIMITS.items():
        value = str(result[key]).strip()
        if len(value) > limit:
            raise guidance.FieldError(key, f"Use at most {limit} characters.")
        if key == "portal_name" and not value:
            raise guidance.FieldError(key, "Enter a portal name.")
        result[key] = value
    return result


def settings():
    try:
        source = SETTINGS_OVERRIDE if SETTINGS_OVERRIDE is not None else json.loads(os.environ.get("CAPTIVE_PORTAL_SETTINGS_JSON") or "{}")
        return normalize(source)
    except (ValueError, TypeError, AttributeError):
        return dict(DEFAULTS)


def normalize_logo(data):
    if len(data) > 256 * 1024:
        raise guidance.FieldError("logo", "Choose a logo smaller than 256 KB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG", "WEBP") or image.width > 2048 or image.height > 2048:
                raise ValueError("unsupported logo")
            image.load()
            image = image.convert("RGBA")
            image.thumbnail((512, 160), Image.Resampling.LANCZOS)
            image.info.clear()
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            encoded = output.getvalue()
            if len(encoded) > 64 * 1024:
                raise ValueError("logo too complex")
            return encoded
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as err:
        raise guidance.FieldError("logo", "Choose a PNG, JPEG or WebP logo up to 2048 × 2048 pixels. A simpler image may be needed.") from err


def draft(config, kind, form):
    updated = dict(config)
    for key in FIELDS[kind]:
        if key != "logo_file" and key in form:
            updated[key] = str(form[key][0]).strip()
    logo = None
    if kind == "appearance":
        if form.get("remove_logo", [""])[0] == "1":
            updated["logo_file"] = ""
        else:
            upload = form.get("logo", [b""])[0]
            if upload:
                if not isinstance(upload, bytes):
                    raise guidance.FieldError("logo", "Use the logo upload control.")
                logo = normalize_logo(upload)
            elif form.get("logo_preview", [""])[0]:
                try:
                    raw = base64.b64decode(form["logo_preview"][0], validate=True)
                except (ValueError, TypeError) as err:
                    raise guidance.FieldError("logo", "Upload your logo again.") from err
                logo = normalize_logo(raw)
            if logo:
                updated["logo_file"] = hashlib.sha256(logo).hexdigest() + ".png"
    return normalize(updated), logo


def store_logo(data):
    """Content-addressed, atomic files keep concurrent public requests consistent."""
    name = hashlib.sha256(data).hexdigest() + ".png"
    LOGO_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = LOGO_DIR / name
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=LOGO_DIR, delete=False) as file:
            file.write(data)
            temporary = Path(file.name)
        try:
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return name


def logo_bytes(config):
    name = config.get("logo_file", "")
    if re.fullmatch(r"[0-9a-f]{64}\.png", str(name)):
        try:
            with (LOGO_DIR / name).open("rb") as file:
                data = file.read(64 * 1024 + 1)
            if len(data) <= 64 * 1024 and hashlib.sha256(data).hexdigest() + ".png" == name:
                return data
        except OSError:
            pass
    return None


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722), strict=True))


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


def ink(background):
    return max(("#000000", "#ffffff"), key=lambda color: contrast(color, background))


def link_color(accent, surface):
    """Keep the brand hue while bringing links and focus outlines above 4.5:1."""
    target = ink(surface)
    rgb = [int(accent[i:i + 2], 16) for i in (1, 3, 5)]
    end = [int(target[i:i + 2], 16) for i in (1, 3, 5)]
    for step in range(101):
        color = "#" + "".join(f"{round(a + (b - a) * step / 100):02x}" for a, b in zip(rgb, end, strict=True))
        if contrast(color, surface) >= 4.5:
            return color
    return target


def css(config):
    rules = []
    for theme in ("light", "dark"):
        surface, text, muted, background, border = (
            ("#ffffff", "#212121", "#616161", "#fafafa", "#767676") if theme == "light"
            else ("#1c1c1c", "#e1e1e1", "#b0b0b0", "#111111", "#949494")
        )
        background = config["background_color"] or background
        accent = config["accent_color"]
        variables = (f"color-scheme:{theme};--primary-color:{accent};--accent-fill:{accent};"
                     f"--portal-button-ink:{ink(accent)};--accent-ink:{link_color(accent, surface)};"
                     f"--focus-color:{link_color(accent, surface)};--primary-background-color:{background};"
                     f"--card-background-color:{surface};--secondary-background-color:{surface};"
                     f"--primary-text-color:{text};--secondary-text-color:{muted};--outline:{border};"
                     f"--divider-color:{border};--hover:{'#eeeeee' if theme == 'light' else '#333333'};"
                     f"--portal-outer-ink:{ink(background)};--warn-ink:{'#805000' if theme == 'light' else '#ffd28a'};"
                     f"--bad-ink:{'#b3261e' if theme == 'light' else '#ffb4ab'};--info-ink:{link_color('#039be5', surface)};"
                     f"--ok-ink:{link_color('#4caf50', surface)};--danger-fill:#b3261e;")
        selector = f'.portal-skin[data-portal-theme="{theme}"]'
        if theme == "light":
            selector += ',.portal-skin[data-portal-theme="auto"]'
        rules.append(selector + "{" + variables + "}")
        if theme == "dark":
            rules.append('@media(prefers-color-scheme:dark){.portal-skin[data-portal-theme="auto"]{' + variables + '}}')
    return "".join(rules) + """
.portal-skin{background:var(--primary-background-color);color:var(--primary-text-color);overflow-wrap:anywhere}
.portal-skin .brand,.portal-skin .portal-footer{color:var(--portal-outer-ink)}
.portal-skin .brand{align-items:center;flex-wrap:wrap;gap:12px}
.portal-skin .brand-logo{max-width:min(240px,100%);max-height:80px;width:auto;height:auto;object-fit:contain}
.portal-skin .brand-mark{color:var(--portal-outer-ink);background:transparent}
.portal-skin .btn:not(.text):not(.danger):not(:disabled){color:var(--portal-button-ink)}
.portal-skin .btn:not(.text):not(.danger):not(:disabled):hover{background:var(--accent-fill);filter:brightness(.98)}
.portal-skin .portal-footer{margin:20px 4px 0;font-size:13px;line-height:20px;white-space:pre-line}
.portal-skin .portal-welcome{white-space:pre-line;margin-bottom:20px}
.portal-skin input:not([type=hidden]),.portal-skin select{font-size:16px}
.portal-skin input[type=checkbox],.portal-skin input[type=radio]{accent-color:var(--accent-ink)}
.portal-preview{border-radius:12px;border:1px solid var(--outline);margin-top:16px}
.portal-preview .public{padding:24px 16px}
.portal-preview .card-header h3{font-size:24px;line-height:32px}
.portal-preview .preview-button{pointer-events:none}
.portal-editor .card-content{padding-top:16px}
.portal-editor textarea{font-family:inherit;font-size:16px}
.portal-editor input,.portal-editor select{font-size:16px}
"""


def content(config, title, body, welcome=False, logo=None, preview=False):
    logo = logo if logo is not None else logo_bytes(config)
    brand = (f'<img class="brand-logo" src="data:image/png;base64,{base64.b64encode(logo).decode()}" alt="">'
             if logo else f'<span class="brand-mark">{ui.icon("wifi")}</span>')
    title = config["welcome_heading"] if welcome and config["welcome_heading"] else title
    intro = f'<p class="portal-welcome">{esc(config["welcome_message"])}</p>' if welcome and config["welcome_message"] else ""
    heading = "h3" if preview else "h1"
    return (f'<div class="brand">{brand}<span>{esc(config["portal_name"])}</span></div>'
            f'<div class="card"><div class="card-header"><{heading}>{esc(title)}</{heading}></div>'
            f'<div class="card-content">{intro}{body}</div></div>'
            + (f'<p class="portal-footer">{esc(config["footer_text"])}</p>' if config["footer_text"] else ""))


def preview(config, logo=None):
    try:
        config = normalize(config)
    except ValueError:
        return '<p class="hint">Correct the highlighted settings to preview this draft.</p>'
    body = ('<p>This sample shows the welcome screen. Your network controls which fields and sign-in steps appear.</p>'
            '<span class="btn preview-button" aria-hidden="true">Continue</span>')
    return (f'<style>{css(config)}</style><section aria-label="Portal preview" class="portal-preview portal-skin" data-portal-theme="{config["theme"]}">'
            '<div class="public">' + content(config, "Connect to resident Wi-Fi", body, welcome=True, logo=logo, preview=True) + '</div></section>')


def form(config, kind, csrf, action_url, logo=None):
    labels = {"accent_color": "Accent color", "background_color": "Background color", "portal_name": "Portal name",
              "welcome_heading": "Welcome heading", "welcome_message": "Welcome message", "footer_text": "Footer text"}
    fields = ""
    if kind == "appearance":
        choices = "".join(f'<option value="{value}"{" selected" if config["theme"] == value else ""}>{label}</option>' for value, label in (("auto", "Follow device appearance"), ("light", "Light"), ("dark", "Dark")))
        fields = f'<div class="field"><label for="theme">Appearance</label><select id="theme" name="theme">{choices}</select></div>'
        for key in ("accent_color", "background_color"):
            help_text = "Buttons use this color; text and links adjust for contrast." if key == "accent_color" else "Leave blank to use the light or dark theme background."
            fields += (f'<div class="field"><label for="{key}">{labels[key]}</label><input id="{key}" name="{key}" value="{esc(config[key])}" maxlength="7" placeholder="#03a9f4" aria-describedby="{key}-help">'
                       f'<small class="muted" id="{key}-help">{help_text}</small></div>')
        fields += ('<div class="field"><label for="logo">Portal logo</label><input id="logo" name="logo" type="file" accept="image/png,image/jpeg,image/webp" aria-describedby="logo-help">'
                   '<small class="muted" id="logo-help">PNG, JPEG or WebP. Up to 256 KB and 2048 × 2048 pixels. The logo is stored with the add-on and needs no external connection.</small></div>')
        if config["logo_file"]:
            fields += '<label class="check"><input type="checkbox" name="remove_logo" value="1">Remove the logo and use the Wi-Fi icon</label>'
        if logo:
            fields += f'<input type="hidden" name="logo_preview" value="{base64.b64encode(logo).decode()}">'
    else:
        for key in FIELDS[kind]:
            hint = "Shown above every portal screen." if key == "portal_name" else "Optional. Shown on welcome screens." if key.startswith("welcome") else "Optional. Shown below every portal screen."
            control = (f'<textarea id="{key}" name="{key}" maxlength="{LIMITS[key]}" aria-describedby="{key}-help">{esc(config[key])}</textarea>' if key in ("welcome_message", "footer_text") else
                       f'<input id="{key}" name="{key}" value="{esc(config[key])}" maxlength="{LIMITS[key]}" aria-describedby="{key}-help"{" required" if key == "portal_name" else ""}>')
            fields += f'<div class="field"><label for="{key}">{labels[key]}</label>{control}<small class="muted" id="{key}-help">{hint}</small></div>'
    return (f'<p class="settings-intro">Customize the public captive portal. Saved changes apply immediately to new page loads.</p>'
            f'<section class="card portal-editor"><div class="card-content"><form method="post" enctype="multipart/form-data" action="{esc(action_url)}">{csrf}{fields}'
            '<div class="actions form-submit"><button class="btn" name="intent" value="save" type="submit">Save ' + kind + '</button>'
            '<button class="btn text" name="intent" value="preview" type="submit">Preview changes</button></div></form></div></section>'
            '<h3>Portal preview</h3><p class="hint">A sample welcome screen. Preview changes to see your draft before saving.</p>' + preview(config, logo))
