"""Central settings navigation and grouped Home Assistant configuration summaries."""

import html
import re
from urllib.parse import urlsplit, urlunsplit

import ui
import identity_settings


GROUPS = (
    (
        "certificates",
        "Certificates",
        "shield-check",
        "Issuance, SCEP groups and device trust",
        (
            (
                "issuance",
                "Authority and SCEP",
                "CA identity, certificate lifetimes and SCEP defaults",
            ),
            (
                "groups",
                "Certificate groups",
                "Organizational units, challenges and group lifetimes",
            ),
            (
                "trust",
                "Device trust certificates",
                "Additional CAs included in enrollment profiles",
            ),
        ),
    ),
    (
        "enrollment",
        "Enrollment & Wi-Fi",
        "qrcode",
        "Enrollment links, Wi-Fi profiles and profile signing",
        (
            (
                "defaults",
                "Enrollment defaults",
                "Public URL and one-time link lifetime",
            ),
            (
                "networks",
                "Wi-Fi profiles",
                "Client networks, authentication, proxy and Passpoint",
            ),
            (
                "signing",
                "Profile signing",
                "Certificate and private-key filenames for Apple profiles",
            ),
            ("mdm", "MDM profiles", "SCEP values and downloadable device profiles"),
        ),
    ),
    (
        "ipsk",
        "IPSK",
        "wifi",
        "Wi-Fi onboarding, device access and guest/setup networks",
        (
            (
                "network",
                "Network and onboarding",
                "Meraki network, SSID, policy, invitations and key lifetime",
            ),
            (
                "access",
                "Device access",
                "Self-service, device limits and use of shared identity services",
            ),
            (
                "join-codes",
                "Guest and setup networks",
                "Network credentials used by the shared join codes",
            ),
        ),
    ),
    (
        "identity",
        "Identity & access",
        "account-group",
        "Shared authentication and user directory",
        (
            (
                "authentication",
                "Authentication",
                "Duo verification provider and callback",
            ),
            (
                "directory",
                "User directory",
                "Permitted user group and directory connection",
            ),
        ),
    ),
    (
        "captive-portal", "Captive portal", "wifi-lock",
        "Branding, appearance and welcome content",
        (("appearance", "Appearance", "Logo, colors and light or dark appearance"),
         ("content", "Content", "Portal name, welcome message and footer")),
    ),
    (
        "system",
        "System",
        "cog",
        "Storage, companion integration and connection checks",
        (
            ("storage", "Database", "MariaDB or embedded storage and database name"),
            (
                "integration",
                "Home Assistant integration",
                "Bundled companion installation",
            ),
            (
                "checks",
                "Setup and checks",
                "Installation guidance and read-only connection checks",
            ),
            (
                "help",
                "Help and troubleshooting",
                "Searchable connection and recovery guides",
            ),
            ("tools", "Certificate tools", "Sign requests and download MDM profiles"),
            (
                "options",
                "All add-on options",
                "Complete saved configuration, grouped by purpose",
            ),
        ),
    ),
)

ALIASES = {
    "/tools": "/settings/system/tools",
    "/tools/groups": "/settings/certificates/groups",
    "/tools/cas": "/settings/certificates/trust",
    "/tools/wifi": "/settings/enrollment/networks",
    "/tools/mdm": "/settings/enrollment/mdm",
    "/tools/sign": "/settings/system/sign",
    "/tools/setup": "/settings/system/checks",
    "/tools/help": "/settings/system/help",
    "/tools/options": "/settings/system/options",
    "/tools/restart": "/settings/system/restart",
    "/ipsk/access/settings": "/settings/ipsk/access/save",
    "/ipsk/qr/settings": "/settings/ipsk/join-codes/save",
    "/residents/access/settings": "/settings/ipsk/access/save",
    "/residents/qr/settings": "/settings/ipsk/join-codes/save",
    "/ipsk/access": "/settings/ipsk/access",
    "/ipsk/join-codes/settings": "/settings/ipsk/join-codes",
}

# Every top-level add-on option belongs to one of these pages. Nested Wi-Fi and
# identity options retain their existing editors; no new configuration store.
OPTION_PAGES = {
    "certificates/issuance": (
        ("ca_name", "Authority name"),
        ("certificate_subject", "Issued certificate subject"),
        ("dns_names", "CA DNS names"),
        ("scep_provisioner_name", "SCEP provisioner"),
        ("scep_challenge", "SCEP challenge"),
        ("encryption_algorithm", "SCEP encryption algorithm"),
        ("min_public_key_length", "Minimum public-key length"),
        ("include_root", "Include root in SCEP response"),
        ("force_cn", "Require certificate name"),
        ("default_cert_duration", "Default certificate lifetime"),
        ("max_cert_duration", "Maximum certificate lifetime"),
    ),
    "certificates/groups": (("groups", "Certificate groups"),),
    "enrollment/defaults": (("enrollment", "Enrollment defaults"),),
    "enrollment/networks": (
        ("wifi", "Legacy single network"),
        ("wifi_networks", "Wi-Fi profiles"),
    ),
    "enrollment/signing": (("profile_signing", "Profile signing"),),
    "ipsk/network": (("resident_onboarding", "IPSK onboarding"),),
    "ipsk/access": (("resident_onboarding", "IPSK device access"),),
    "ipsk/join-codes": (("resident_onboarding", "Guest and setup networks"),),
    "identity/authentication": (("resident_onboarding", "Authentication"),),
    "identity/directory": (("resident_onboarding", "User directory"),),
    "captive-portal/appearance": (("captive_portal", "Captive portal skin"),),
    "system/storage": (
        ("database", "Database backend"),
        ("mariadb_database", "MariaDB database name"),
    ),
    "system/integration": (
        ("install_integration", "Install bundled companion integration"),
    ),
}

LABELS = {
    "public_url": "Public HTTPS URL",
    "link_hours": "Link lifetime in hours",
    "ssl_certificate": "Certificate filename",
    "ssl_key": "Private-key filename",
    "enabled": "IPSK onboarding enabled",
    "invite_required": "Require an invitation",
    "network_id": "Meraki network ID",
    "ssid_number": "SSID number",
    "group_policy_id": "Registered-resident policy ID",
    "duration_hours": "Key lifetime in hours",
    "guest_ssid": "Guest SSID",
    "guest_psk": "Guest password",
    "setup_ssid": "Setup SSID",
    "setup_psk": "Setup password",
    "self_service_enabled": "Self-service enabled",
    "sign_in_required": "Require Duo verification",
    "no_sign_in_user_list": "Duo account selector",
    "max_devices_per_resident": "Device limit per resident",
}
SECRET_NAMES = {
    "scep_challenge",
    "challenge",
    "password",
    "eap_password",
    "proxy_password",
    "guest_psk",
    "setup_psk",
    "duo_client_secret",
    "duo_admin_secret",
}
IPSK_NETWORK_FIELDS = {
    "enabled",
    "invite_required",
    "network_id",
    "ssid_number",
    "group_policy_id",
    "duration_hours",
}
ONBOARDING_SECTIONS = {
    "ipsk/network": IPSK_NETWORK_FIELDS,
    "ipsk/access": {
        "self_service_enabled",
        "sign_in_required",
        "no_sign_in_user_list",
        "max_devices_per_resident",
    },
    "ipsk/join-codes": {"guest_ssid", "guest_psk", "setup_ssid", "setup_psk"},
    "identity/authentication": set(identity_settings.FIELDS["authentication"]),
    "identity/directory": set(identity_settings.FIELDS["directory"]),
}


def esc(value):
    return html.escape(str(value), quote=True)


def canonical_url(value):
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/") or "/"
    for old in sorted(ALIASES, key=len, reverse=True):
        if path == old or (old.startswith("/tools/") and path.startswith(old + "/")):
            path = ALIASES[old] + path[len(old) :]
            break
    return urlunsplit(("", "", path, parsed.query, parsed.fragment))


def legacy_path(path):
    """Normalize central form endpoints before existing validation and CSRF checks."""
    for old, new in ALIASES.items():
        if old.startswith("/residents/"):
            continue
        if path == new or (old.startswith("/tools/") and path.startswith(new + "/")):
            return old + path[len(new) :]
    return path


def option_rows(name, value, label=None):
    """Render data recursively; saved credential values never enter HTML."""
    label = label or LABELS.get(name, name.replace("_", " ").capitalize())
    if name in SECRET_NAMES or name.endswith(("_secret", "_password", "_psk")):
        display = "Saved" if value else "Not set"
    elif isinstance(value, dict):
        return "".join(
            option_rows(key, item, LABELS.get(key)) for key, item in value.items()
        ) or ui.kv_row(esc(label), "Not set")
    elif isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            return "".join(
                option_rows(name, item, label) for item in value
            ) or ui.kv_row(esc(label), "None")
        display = ", ".join(str(item) for item in value) or "None"
    elif isinstance(value, bool):
        display = "Yes" if value else "No"
    else:
        display = "Not set" if value is None or value == "" else str(value)
    return ui.kv_row(
        esc(label), '<span class="settings-value">' + esc(display) + "</span>"
    )


class SettingsMixin:
    def settings_location(self):
        path = canonical_url(urlsplit(getattr(self, "path", "/settings")).path)
        group = next(
            (
                row
                for row in GROUPS
                if path == "/settings/" + row[0]
                or path.startswith("/settings/" + row[0] + "/")
            ),
            None,
        )
        leaf = (
            next(
                (
                    row
                    for row in group[4]
                    if path == "/settings/" + group[0] + "/" + row[0]
                    or path.startswith("/settings/" + group[0] + "/" + row[0] + "/")
                ),
                None,
            )
            if group
            else None
        )
        return path, group, leaf

    def settings_row(self, path, label, description, glyph="chevron-right"):
        return (
            f'<a class="row settings-row" href="{esc(self.url(path))}">'
            f'<span class="row-text"><span class="row-title">{esc(label)}</span>'
            f'<span class="row-sub">{esc(description)}</span></span>{ui.icon(glyph, "row-icon")}</a>'
        )

    def settings_index(self, category=""):
        group = next((row for row in GROUPS if row[0] == category), None)
        if group:
            rows = "".join(
                self.settings_row(f"/settings/{category}/{slug}", label, description)
                for slug, label, description in group[4]
            )
            title, description = group[1], group[3]
        else:
            rows = "".join(
                self.settings_row("/settings/" + slug, label, description, glyph)
                for slug, label, glyph, description, _ in GROUPS
            )
            title, description = (
                "Settings",
                "Choose a category to configure certificates, enrollment, Wi-Fi, shared identity or the add-on.",
            )
        self.page(
            title,
            f'<p class="settings-intro">{esc(description)}</p><div class="card"><div class="rows">{rows}</div></div>',
        )

    def settings_shell(self, title, body):
        path, group, leaf = self.settings_location()
        if path == "/settings":
            return body
        categories = "".join(
            f'<a href="{esc(self.url("/settings/" + slug))}"'
            + (
                ' aria-current="page"'
                if group and group[0] == slug and not leaf
                else ""
            )
            + (' class="selected-category"' if group and group[0] == slug else "")
            + f">{esc(label)}</a>"
            for slug, label, _, _, _ in GROUPS
        )
        children = (
            "".join(
                f'<a href="{esc(self.url("/settings/" + group[0] + "/" + slug))}"'
                + (' aria-current="page"' if leaf and leaf[0] == slug else "")
                + f">{esc(label)}</a>"
                for slug, label, _ in group[4]
            )
            if group
            else ""
        )
        menu = (
            '<details class="settings-menu" open><summary>Settings menu'
            + ui.icon("chevron-down", "chev")
            + '</summary><nav aria-label="Settings navigation">'
            + categories
            + (
                '<div class="settings-submenu">' + children + "</div>"
                if children
                else ""
            )
            + "</nav></details>"
        )
        breadcrumb = f'<nav class="settings-breadcrumb" aria-label="Breadcrumb"><a href="{esc(self.url("/settings"))}">Settings</a>'
        if group:
            breadcrumb += (
                f'<span aria-hidden="true">/</span><a href="{esc(self.url("/settings/" + group[0]))}">{esc(group[1])}</a>'
                if leaf
                else f'<span aria-hidden="true">/</span><span aria-current="page">{esc(group[1])}</span>'
            )
        if leaf:
            breadcrumb += f'<span aria-hidden="true">/</span><span aria-current="page">{esc(leaf[1])}</span>'
        heading = leaf[1] if leaf else title
        return (
            '<div class="settings-layout">'
            + menu
            + '<div class="settings-content">'
            + breadcrumb
            + f'</nav><h2 class="settings-title">{esc(heading)}</h2>'
            + body
            + "</div></div>"
        )

    def settings_summary(self, topic, reader, query=None, all_options=False):
        query = query or {}
        try:
            info = reader()
            options = info.get("options") or {}
            slug = info.get("slug", "")
            edit = (
                f'<a class="btn" href="/hassio/addon/{esc(slug)}/config" target="_top">Edit in Home Assistant</a>'
                if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", slug)
                else "<p>Open Settings → Add-ons → Step CA → Configuration in Home Assistant to edit these options.</p>"
            )
            note = '<p class="hint">These are saved add-on options. Changes apply after restarting Step CA. Existing certificates are retained.</p>'
            panels = []
            for key, fields in OPTION_PAGES.items():
                if key != topic and not all_options:
                    continue
                rows = ""
                for name, label in fields:
                    value = options.get(name)
                    if name == "resident_onboarding" and isinstance(value, dict):
                        value = {
                            k: v
                            for k, v in value.items()
                            if k in ONBOARDING_SECTIONS[key]
                        }
                    rows += option_rows(name, value, label)
                label = next(
                    (
                        leaf[1]
                        for group in GROUPS
                        for leaf in group[4]
                        if key == group[0] + "/" + leaf[0]
                    ),
                    key,
                )
                panels.append(
                    f'<section class="card"><div class="card-header"><h3>{esc(label)}</h3></div><dl class="rows">{rows}</dl></section>'
                )
            body = edit + note + "".join(panels)
            if all_options:
                assigned = {
                    field for fields in OPTION_PAGES.values() for field, _ in fields
                }
                extra = "".join(
                    option_rows(key, value)
                    for key, value in options.items()
                    if key not in assigned
                )
                onboarding = options.get("resident_onboarding") or {}
                known = set().union(*ONBOARDING_SECTIONS.values())
                extra += "".join(
                    option_rows(key, value)
                    for key, value in onboarding.items()
                    if key not in known
                )
                if extra:
                    body += (
                        '<section class="card"><div class="card-header"><h3>Additional add-on options</h3></div><dl class="rows">'
                        + extra
                        + "</dl></section>"
                    )
        except RuntimeError:
            body = ui.alert(
                "warning",
                "Saved add-on options could not be read. Check the Home Assistant connection, or open the add-on’s Configuration tab.",
                "Settings unavailable",
            )
        self.page("All add-on options" if all_options else "Add-on settings", body)

    def settings_get(self, path, query, reader):
        if path == "/settings":
            self.settings_index()
            return True
        category = path.removeprefix("/settings/")
        if category in {row[0] for row in GROUPS}:
            self.settings_index(category)
            return True
        pages = {
            "/settings/certificates/groups": lambda: self.groups_page(query),
            "/settings/certificates/trust": lambda: self.cas_page(query),
            "/settings/enrollment/networks": lambda: self.wifi_page(query),
            "/settings/enrollment/mdm": lambda: self.mdm_page(query),
            "/settings/ipsk/access": lambda: self.residents_page(
                query, section="access"
            ),
            "/settings/ipsk/join-codes": lambda: self.residents_page(
                query, section="join-codes/settings"
            ),
            "/settings/identity/authentication": lambda: self.identity_page(
                "authentication", query
            ),
            "/settings/identity/directory": lambda: self.identity_page(
                "directory", query
            ),
            "/settings/captive-portal/appearance": lambda: self.portal_skin_page("appearance", query),
            "/settings/captive-portal/content": lambda: self.portal_skin_page("content", query),
            "/settings/system/checks": lambda: self.setup_page(query),
            "/settings/system/help": lambda: self.help_page(query),
            "/settings/system/tools": self.tools_page,
            "/settings/system/sign": lambda: self.sign_page(query),
            "/settings/system/options": lambda: self.settings_summary(
                "", reader, all_options=True
            ),
        }
        if path in pages:
            pages[path]()
            return True
        if category in OPTION_PAGES:
            self.settings_summary(category, reader, query)
            return True
        return False
