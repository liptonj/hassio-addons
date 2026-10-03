"""Shared authentication and user-directory configuration, independent of Wi-Fi."""

import html
import re
from urllib.parse import urlsplit

import guidance

FIELDS = {
    "authentication": (
        "duo_client_id",
        "duo_client_secret",
        "duo_api_hostname",
        "duo_redirect_uri",
    ),
    "directory": (
        "duo_group_id",
        "duo_admin_hostname",
        "duo_admin_integration_key",
        "duo_admin_secret",
    ),
}
SECRET_FIELDS = ("duo_client_secret", "duo_admin_secret")
LABELS = {
    "duo_client_id": "Client ID",
    "duo_client_secret": "Client secret",
    "duo_api_hostname": "Web SDK API hostname",
    "duo_redirect_uri": "Public callback URL",
    "duo_group_id": "Duo group ID",
    "duo_admin_hostname": "Admin API hostname",
    "duo_admin_integration_key": "Admin API integration key",
    "duo_admin_secret": "Admin API secret",
}


def esc(value):
    return html.escape(str(value or ""), quote=True)


def duo_hostname(value):
    if not re.fullmatch(r"api-[A-Za-z0-9]+\.duosecurity\.com", str(value or "")):
        raise ValueError(
            "Enter a Duo API hostname such as api-xxxxxxxx.duosecurity.com, without https://."
        )
    return value


def validate(config, kind, required=False):
    """Validate a provider without requiring an IPSK network or enabled portal."""
    if not required and not any(config.get(key) for key in FIELDS[kind]):
        return
    if kind == "directory":
        if not re.fullmatch(r"DG[A-Z0-9]{18}", str(config.get("duo_group_id") or "")):
            raise guidance.FieldError(
                "duo_group_id",
                "Enter the permitted Duo group ID (DG followed by 18 letters or digits).",
            )
        if not all(config.get(k) for k in FIELDS[kind]):
            raise ValueError(
                "Enter the Duo Admin API credentials to check permitted group members."
            )
        host_key = "duo_admin_hostname"
    else:
        if not all(config.get(k) for k in FIELDS[kind]):
            raise ValueError(
                "Complete the Duo Universal SDK settings before requiring sign-in."
            )
        host_key = "duo_api_hostname"
    try:
        duo_hostname(config[host_key])
    except ValueError as err:
        raise guidance.FieldError(host_key, str(err)) from err
    if kind == "authentication":
        callback = urlsplit(config["duo_redirect_uri"])
        if (
            callback.scheme != "https"
            or not callback.hostname
            or callback.username
            or callback.password
            or callback.path != "/api/step_ca_scep/portal"
            or callback.query != "action=duo_callback"
            or callback.fragment
            or any(ord(c) < 33 for c in config["duo_redirect_uri"])
        ):
            raise guidance.FieldError(
                "duo_redirect_uri",
                "Use your public HTTPS Home Assistant URL followed by /api/step_ca_scep/portal?action=duo_callback.",
            )


def merge(config, kind, form):
    updated = dict(config)
    for key in FIELDS[kind]:
        if key in SECRET_FIELDS:
            updated[key] = str(form.get(key, [""])[0]) or config.get(key, "")
        elif key in form:
            updated[key] = str(form[key][0]).strip()
    return updated


def form(config, kind, csrf, action_url, related_url):
    def field(key):
        secret = key in SECRET_FIELDS
        hint = "Blank keeps the saved secret." if secret else ""
        if key == "duo_redirect_uri":
            hint = "Current IPSK callback: https://your-home-assistant/api/step_ca_scep/portal?action=duo_callback"
        elif key == "duo_group_id":
            hint = "Only members of this group are included. The full Duo tenant directory is never listed."
        attrs = (
            'type="password" autocomplete="new-password" placeholder="Keep the saved secret"'
            if secret
            else f'type="text" autocomplete="off" value="{esc(config.get(key))}"'
        )
        return (
            f'<div class="field"><label for="{key}">{LABELS[key]}</label>'
            f'<input id="{key}" name="{key}" maxlength="512" aria-describedby="{key}-help" {attrs}>'
            f'<small class="muted" id="{key}-help">{esc(hint)}</small></div>'
        )

    authentication = kind == "authentication"
    title = "Duo Universal SDK" if authentication else "Duo user directory"
    intro = (
        "Configure identity verification here. Each application chooses whether to require it. Duo verifies a second factor; it does not provide primary password SSO."
        if authentication
        else "Configure the permitted user group and directory connection here. Applications can use this directory without owning its configuration. Selecting a user does not authenticate them."
    )
    help_text = (
        "The current callback serves IPSK. Duo failure or bypass blocks verification. Allow Duo Universal Prompt and its required resources through the setup network’s walled garden."
        if authentication
        else "Use a separate Duo Admin API application with only Grant resource – Read enabled."
    )
    other = "User directory" if authentication else "Authentication"
    fields = FIELDS[kind]
    rows = "".join(
        '<div class="field-row">'
        + "".join(field(key) for key in fields[i : i + 2])
        + "</div>"
        for i in (0, 2)
    )
    return (
        f'<p class="settings-intro">{intro}</p><section class="card identity-settings">'
        f'<div class="card-header"><h3>{title}</h3></div><div class="card-content">'
        f'<form method="post" action="{esc(action_url)}">{csrf}{rows}'
        f'<p class="hint">{help_text}</p><button class="btn" type="submit">Save {kind if authentication else "user directory"}</button>'
        f'</form></div></section><p class="hint"><a href="{esc(related_url)}">{other}</a></p>'
    )
