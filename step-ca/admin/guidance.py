"""Task guidance shared by the admin panel and public resident forms."""

import html
import re

class FieldError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def form_error(markup, error):
    """Associate a known server validation error with its editable input."""
    field = getattr(error, "field", "")
    if not re.fullmatch(r"[a-z_]+", field):
        return markup
    identity = r'\sid=(?:"' + field + r'"|\b' + field + r'\b)'
    pattern = r'<input\b[^>]*' + identity + r'[^>]*>|<select\b[^>]*' + identity + r'[^>]*>.*?</select>'
    def annotate(match):
        control = match[0]
        tail = ""
        if control.startswith("<select"):
            cut = control.index(">") + 1
            control, tail = control[:cut], control[cut:]
        error_id = field + "-error"
        described = re.search(r'aria-describedby="([^"]*)"', control)
        if described:
            control = control.replace(described[0], 'aria-describedby="' + described[1] + ' ' + error_id + '"')
        else:
            control = control[:-1] + ' aria-describedby="' + error_id + '">'
        control = control[:-1] + ' aria-invalid="true">'
        return control + tail + '<p class="field-error" id="' + error_id + '">' + html.escape(str(error)) + '</p>'
    return re.sub(pattern, annotate, markup, count=1, flags=re.DOTALL)


def progress(stage, identity=True):
    labels = ("Resident", "Device", "Save and connect") if identity else ("Register device", "Save and connect")
    stage = min(max(int(stage), 1), len(labels))
    return '<nav class="onboarding-progress" aria-label="Connection progress"><ol>' + ''.join(
        '<li' + (' aria-current="step"' if index == stage else '') + '>'
        + label
        + ('<span class="visually-hidden">, completed</span>' if index < stage else '') + '</li>'
        for index, label in enumerate(labels, 1)) + '</ol></nav>'


def resident_help():
    return ('<details class="expand resident-help"><summary>Need help connecting?</summary>'
            '<div class="card-content"><h2>Choose the right connection</h2>'
            '<p><b>Guest:</b> scan the guest QR. You do not need to register a resident device.</p>'
            '<p><b>Resident:</b> join setup Wi-Fi, open its sign-in notification and register. '
            'Save your individual password, finish setup, then join the resident network.</p>'
            '<p><b>Another device:</b> choose Another device if available, enter that device’s '
            'hardware Wi-Fi address, then scan its new QR on that device.</p>'
            '<h2>If something goes wrong</h2>'
            '<p><b>Private address:</b> turn private/random addressing off for this network '
            'in Wi-Fi settings, disconnect and reconnect to setup Wi-Fi.</p>'
            '<p><b>Expired session:</b> reconnect to setup Wi-Fi and open a fresh sign-in page. '
            'If Duo verification is required, start verification again.</p>'
            '<p><b>Lost password or device limit:</b> contact your building administrator '
            'to replace or remove a key. Existing passwords are not shown in self-service.</p>'
            '<p><b>No result after submitting:</b> do not repeat key creation immediately. '
            'Ask your administrator to check whether the key exists before retrying.</p>'
            '</div></details>')


HELP_TOPICS = (
    ("first-start", "Install and connect Step CA", "setup mariadb companion restart certificate",
     '<ol><li>Install and start MariaDB, then Step CA. Use MariaDB in the add-on options.</li>'
     '<li>Restart Home Assistant after the bundled Step CA companion is installed; add its discovered integration.</li>'
     '<li>Open Setup and checks to inspect database access and the existing Meraki connection.</li>'
     '<li>Keep certificate enrollment in Step CA. Resident Wi-Fi keys use its same MariaDB database.</li></ol>'),
    ("resident-setup", "Set up resident Wi-Fi", "meraki ssid policy captive splash invitation duo group",
     '<ol><li>In Meraki, enable an iPSK-without-RADIUS SSID and choose the registered-resident group policy.</li>'
     '<li>Save its network, SSID number and group policy in the add-on resident options.</li>'
     '<li>Set the default setup key’s policy to use a click-through splash page. Use your public HTTPS '
     'Home Assistant URL followed by /api/step_ca_scep/portal.</li>'
     '<li>Allow Home Assistant and any required Duo endpoints in the walled garden.</li>'
     '<li>Choose invitation and resident identity policies, then check them with a physical device.</li></ol>'
     '<p>Duo performs factor verification. A group-only account selector attributes access but does not verify identity.</p>'),
    ("qr-codes", "Share guest, setup or device access", "qr scan password guest registration onboarding",
     '<p>The guest QR joins the guest network; its Meraki policy must bypass splash. The setup QR '
     'joins setup Wi-Fi; residents then open Wi-Fi sign-in to create their own key.</p>'
     '<p>A device QR contains an individual Wi-Fi password. Scan it on the intended device. '
     'Save credentials before closing a one-time result; keep QR images private.</p>'),
    ("private-mac", "Fix a private or randomized address", "mac android apple iphone windows hardware",
     '<p>Registration requires the hardware Wi-Fi address. In this network’s Wi-Fi settings, '
     'turn off Private Wi-Fi Address (Apple), choose Use device MAC (Android), or turn off '
     'Random hardware addresses (Windows). Reconnect to setup Wi-Fi and open its sign-in page.</p>'
     '<p>For another device, enter that device’s Wi-Fi hardware address. Keep private addressing off '
     'on the resident network too. Menu names vary by device.</p>'),
    ("recover-access", "Recover an expired session or lost password", "timeout error retry quota limit duplicate key invitation",
     '<p>Expired sessions need a new setup-network sign-in, or fresh Duo verification where required. '
     'Invalid, used or expired invitations need a new code from the administrator.</p>'
     '<p>For a timeout after key creation, first search Wi-Fi keys and check Meraki Dashboard. '
     'A timeout does not prove that no key was created. Avoid another creation request until its result is known.</p>'
     '<p>To replace a lost device or password, confirm the resident and device, then revoke the old key '
     'and create a replacement. Revocation removes access; deletion is permanent.</p>'),
    ("certificates", "Install and troubleshoot certificates", "p12 pkcs12 scep mdm ca chain radius tls",
     '<p>Apple devices can install a certificate profile; other devices receive a password-protected .p12 '
     'file containing a certificate and private key. Save the one-time password and follow the result’s installation steps.</p>'
     '<p>The CA chain establishes who issued a certificate. SCEP lets managed devices request certificates. '
     'For EAP-TLS Wi-Fi, the RADIUS server must trust Step CA, and the device must trust the RADIUS server.</p>'
     '<p>If installation fails, check device time, certificate expiry, server names and the required trust chain. '
     'Profile signing does not by itself prove that a device has joined Wi-Fi.</p>'),
)


def help_topics(query=""):
    query = str(query)[:254].strip().casefold()
    terms = query.split()
    return [row for row in HELP_TOPICS if all(term in ' '.join(row).casefold() for term in terms)]


def page_number(value):
    try:
        return min(max(int(str(value)[:9]), 1), 1000000)
    except (ValueError, TypeError):
        return 1


def pagination(page, pages, start, end, total, link, label):
    if not total:
        return ""
    return (f'<nav class="pagination" aria-label="{html.escape(label, quote=True)}">'
            + (f'<a class="btn text" href="{html.escape(link(page - 1), quote=True)}">Previous</a>' if page > 1 else '')
            + f'<span role="status">Showing {start}–{end} of {total} · Page {page} of {pages}</span>'
            + (f'<a class="btn text" href="{html.escape(link(page + 1), quote=True)}">Next</a>' if page < pages else '')
            + '</nav>')
