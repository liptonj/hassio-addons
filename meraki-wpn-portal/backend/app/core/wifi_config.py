"""WiFi configuration utilities for device provisioning.

Generates:
- Apple .mobileconfig profiles for iOS/macOS
- WiFi QR codes for Android and other devices
- WiFi config strings for manual configuration
"""

import base64
import io
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def generate_wifi_qr_string(
    ssid: str,
    passphrase: str,
    security: str = "WPA",
    hidden: bool = False,
) -> str:
    """Generate WiFi QR code string format.

    Format: WIFI:T:<security>;S:<ssid>;P:<password>;H:<hidden>;;

    Parameters
    ----------
    ssid : str
        Network SSID name
    passphrase : str
        WiFi password
    security : str
        Security type: WPA, WEP, or nopass
    hidden : bool
        Whether the network is hidden

    Returns
    -------
    str
        WiFi QR code string
    """
    # Escape special characters in SSID and passphrase
    def escape_special(value: str) -> str:
        special_chars = ["\\", ";", ",", ":", '"']
        for char in special_chars:
            value = value.replace(char, f"\\{char}")
        return value

    escaped_ssid = escape_special(ssid)
    escaped_pass = escape_special(passphrase)
    hidden_str = "true" if hidden else "false"

    return f"WIFI:T:{security};S:{escaped_ssid};P:{escaped_pass};H:{hidden_str};;"


def generate_wifi_qr_code(
    ssid: str,
    passphrase: str,
    security: str = "WPA",
    hidden: bool = False,
    size: int = 300,
) -> str:
    """Generate WiFi QR code as base64-encoded PNG.

    Parameters
    ----------
    ssid : str
        Network SSID name
    passphrase : str
        WiFi password
    security : str
        Security type
    hidden : bool
        Whether the network is hidden
    size : int
        QR code size in pixels

    Returns
    -------
    str
        Base64-encoded PNG image data URL
    """
    try:
        import qrcode
        from qrcode.image.pure import PyPNGImage
    except ImportError:
        logger.warning("qrcode library not available, returning empty QR")
        return ""

    wifi_string = generate_wifi_qr_string(ssid, passphrase, security, hidden)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    img = qr.make_image(image_factory=PyPNGImage)

    # Save to bytes buffer
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)

    # Encode as base64
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_data}"


def generate_apple_mobileconfig(
    ssid: str,
    passphrase: str,
    organization: str = "Meraki WPN Portal",
    description: str | None = None,
    display_name: str | None = None,
) -> str:
    """Generate Apple .mobileconfig WiFi profile.

    This profile can be installed on iOS/iPadOS/macOS devices
    to automatically configure WiFi settings.

    Parameters
    ----------
    ssid : str
        Network SSID name
    passphrase : str
        WiFi password
    organization : str
        Organization name for the profile
    description : str | None
        Profile description
    display_name : str | None
        Display name for the profile

    Returns
    -------
    str
        XML content for .mobileconfig file
    """
    profile_uuid = str(uuid.uuid4()).upper()
    payload_uuid = str(uuid.uuid4()).upper()

    if not description:
        description = f"WiFi configuration for {ssid}"
    if not display_name:
        display_name = f"{ssid} WiFi"

    # Apple .mobileconfig XML format
    config = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>AutoJoin</key>
            <true/>
            <key>CaptiveBypass</key>
            <false/>
            <key>DisableAssociationMACRandomization</key>
            <false/>
            <key>EncryptionType</key>
            <string>WPA2</string>
            <key>HIDDEN_NETWORK</key>
            <false/>
            <key>IsHotspot</key>
            <false/>
            <key>Password</key>
            <string>{passphrase}</string>
            <key>PayloadDescription</key>
            <string>Configures Wi-Fi settings</string>
            <key>PayloadDisplayName</key>
            <string>Wi-Fi</string>
            <key>PayloadIdentifier</key>
            <string>com.apple.wifi.managed.{payload_uuid}</string>
            <key>PayloadType</key>
            <string>com.apple.wifi.managed</string>
            <key>PayloadUUID</key>
            <string>{payload_uuid}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>ProxyType</key>
            <string>None</string>
            <key>SSID_STR</key>
            <string>{ssid}</string>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>{description}</string>
    <key>PayloadDisplayName</key>
    <string>{display_name}</string>
    <key>PayloadIdentifier</key>
    <string>com.merakiwpn.wifi.{profile_uuid}</string>
    <key>PayloadOrganization</key>
    <string>{organization}</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{profile_uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>"""

    return config


def generate_android_wifi_intent_url(ssid: str, passphrase: str) -> str:
    """Generate Android WiFi configuration intent URL.

    This URL can be used to open WiFi settings on Android with pre-filled values.
    Note: Android doesn't support direct WiFi configuration via URL,
    but the QR code method works better.

    Parameters
    ----------
    ssid : str
        Network SSID name
    passphrase : str
        WiFi password

    Returns
    -------
    str
        Intent URL (limited support)
    """
    # Android WiFi intent (limited support across versions)
    return f"intent://wifi#Intent;scheme=wifi;S.ssid={ssid};end"


def get_wifi_config_data(
    ssid: str,
    passphrase: str,
    ipsk_name: str,
    organization: str = "Meraki WPN Portal",
) -> dict[str, Any]:
    """Get all WiFi configuration options for a device.

    Parameters
    ----------
    ssid : str
        Network SSID name
    passphrase : str
        WiFi password
    ipsk_name : str
        Name of the iPSK (for display)
    organization : str
        Organization name

    Returns
    -------
    dict
        Dictionary with all config options:
        - qr_code: Base64 QR code image
        - qr_string: WiFi QR string format
        - mobileconfig: Apple profile XML
        - wifi_string: Display string for manual config
    """
    return {
        "ssid": ssid,
        "passphrase": passphrase,
        "ipsk_name": ipsk_name,
        "qr_code": generate_wifi_qr_code(ssid, passphrase),
        "qr_string": generate_wifi_qr_string(ssid, passphrase),
        "mobileconfig": generate_apple_mobileconfig(
            ssid=ssid,
            passphrase=passphrase,
            organization=organization,
            display_name=f"{ipsk_name} WiFi",
        ),
        "wifi_string": f"Network: {ssid}\nPassword: {passphrase}",
    }
