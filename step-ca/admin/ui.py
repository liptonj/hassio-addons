"""Shared look for the management panel and the enrollment pages.

The panel follows Home Assistant's own Settings pages: its theme variables, its
Material Design Icons, and its card, table, chip, and alert patterns. Inside
Home Assistant's frame a small script copies the user's live theme onto the page.
"""

import datetime
import html

# Material Design Icons (pictogrammers.com, Apache 2.0), the set Home Assistant uses.
ICONS = {
    'certificate': 'M4,3C2.89,3 2,3.89 2,5V15A2,2 0 0,0 4,17H12V22L15,19L18,22V17H20A2,2 0 0,0 22,15V8L22,6V5A2,2 0 0,0 20,3H16V3H4M12,5L15,7L18,5V8.5L21,10L18,11.5V15L15,13L12,15V11.5L9,10L12,8.5V5M4,5H9V7H4V5M4,9H7V11H4V9M4,13H9V15H4V13Z',
    'magnify': 'M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z',
    'wifi': 'M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z',
    'download': 'M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z',
    'wrench': 'M22.7,19L13.6,9.9C14.5,7.6 14,4.9 12.1,3C10.1,1 7.1,0.6 4.7,1.7L9,6L6,9L1.6,4.7C0.4,7.1 0.9,10.1 2.9,12.1C4.8,14 7.5,14.5 9.8,13.6L18.9,22.7C19.3,23.1 19.9,23.1 20.3,22.7L22.6,20.4C23.1,20 23.1,19.3 22.7,19Z',
    'content-copy': 'M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z',
    'arrow-left': 'M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z',
    'shield-check': 'M10,17L6,13L7.41,11.59L10,14.17L16.59,7.58L18,9M12,1L3,5V11C3,16.55 6.84,21.74 12,23C17.16,21.74 21,16.55 21,11V5L12,1Z',
    'shield-alert-outline': 'M21,11C21,16.55 17.16,21.74 12,23C6.84,21.74 3,16.55 3,11V5L12,1L21,5V11M12,21C15.75,20 19,15.54 19,11.22V6.3L12,3.18L5,6.3V11.22C5,15.54 8.25,20 12,21M11,7H13V13H11V7M11,15H13V17H11V15Z',
    'alert': 'M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z',
    'alert-circle-outline': 'M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z',
    'check-circle-outline': 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z',
    'information-outline': 'M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z',
    'laptop': 'M4,6H20V16H4M20,18A2,2 0 0,0 22,16V6C22,4.89 21.1,4 20,4H4C2.89,4 2,4.89 2,6V16A2,2 0 0,0 4,18H0V20H24V18H20Z',
    'qrcode': 'M3,11H5V13H3V11M11,5H13V9H11V5M9,11H13V15H11V13H9V11M15,11H17V13H19V11H21V13H19V15H21V19H19V21H17V19H13V21H11V17H15V15H17V13H15V11M19,19V15H17V19H19M15,3H21V9H15V3M17,5V7H19V5H17M3,3H9V9H3V3M5,5V7H7V5H5M3,15H9V21H3V15M5,17V19H7V17H5Z',
    'key-variant': 'M22,18V22H18V19H15V16H12L9.74,13.74C9.19,13.91 8.61,14 8,14A6,6 0 0,1 2,8A6,6 0 0,1 8,2A6,6 0 0,1 14,8C14,8.61 13.91,9.19 13.74,9.74L22,18M7,5A2,2 0 0,0 5,7A2,2 0 0,0 7,9A2,2 0 0,0 9,7A2,2 0 0,0 7,5Z',
    'file-sign': 'M19.7 12.9L14 18.6H11.7V16.3L17.4 10.6L19.7 12.9M23.1 12.1C23.1 12.4 22.8 12.7 22.5 13L20 15.5L19.1 14.6L21.7 12L21.1 11.4L20.4 12.1L18.1 9.8L20.3 7.7C20.5 7.5 20.9 7.5 21.2 7.7L22.6 9.1C22.8 9.3 22.8 9.7 22.6 10C22.4 10.2 22.2 10.4 22.2 10.6C22.2 10.8 22.4 11 22.6 11.2C22.9 11.5 23.2 11.8 23.1 12.1M3 20V4H10V9H15V10.5L17 8.5V8L11 2H3C1.9 2 1 2.9 1 4V20C1 21.1 1.9 22 3 22H15C16.1 22 17 21.1 17 20H3M11 17.1C10.8 17.1 10.6 17.2 10.5 17.2L10 15H8.5L6.4 16.7L7 14H5.5L4.5 19H6L8.9 16.4L9.5 18.7H10.5L11 18.6V17.1Z',
    'close-circle-outline': 'M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2C6.47,2 2,6.47 2,12C2,17.53 6.47,22 12,22C17.53,22 22,17.53 22,12C22,6.47 17.53,2 12,2M14.59,8L12,10.59L9.41,8L8,9.41L10.59,12L8,14.59L9.41,16L12,13.41L14.59,16L16,14.59L13.41,12L16,9.41L14.59,8Z',
    'link-variant': 'M10.59,13.41C11,13.8 11,14.44 10.59,14.83C10.2,15.22 9.56,15.22 9.17,14.83C7.22,12.88 7.22,9.71 9.17,7.76V7.76L12.71,4.22C14.66,2.27 17.83,2.27 19.78,4.22C21.73,6.17 21.73,9.34 19.78,11.29L18.29,12.78C18.3,11.96 18.17,11.14 17.89,10.36L18.36,9.88C19.54,8.71 19.54,6.81 18.36,5.64C17.19,4.46 15.29,4.46 14.12,5.64L10.59,9.17C9.41,10.34 9.41,12.24 10.59,13.41M13.41,9.17C13.8,8.78 14.44,8.78 14.83,9.17C16.78,11.12 16.78,14.29 14.83,16.24V16.24L11.29,19.78C9.34,21.73 6.17,21.73 4.22,19.78C2.27,17.83 2.27,14.66 4.22,12.71L5.71,11.22C5.7,12.04 5.83,12.86 6.11,13.65L5.64,14.12C4.46,15.29 4.46,17.19 5.64,18.36C6.81,19.54 8.71,19.54 9.88,18.36L13.41,14.83C14.59,13.66 14.59,11.76 13.41,10.59C13,10.2 13,9.56 13.41,9.17Z',
    'clock-alert-outline': 'M11 7V13L16.2 16.1L17 14.9L12.5 12.2V7H11M20 12V18H22V12H20M20 20V22H22V20H20M18 20C16.3 21.3 14.3 22 12 22C6.5 22 2 17.5 2 12S6.5 2 12 2C16.8 2 20.9 5.4 21.8 10H19.7C18.8 6.6 15.7 4 12 4C7.6 4 4 7.6 4 12S7.6 20 12 20C14.4 20 16.5 18.9 18 17.3V20Z',
    'chevron-down': 'M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z',
    'chevron-left': 'M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z',
    'chevron-right': 'M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z',
    'plus': 'M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z',
    'delete-outline': 'M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19M8,9H16V19H8V9M15.5,4L14.5,3H9.5L8.5,4H5V6H19V4H15.5Z',
    'cancel': 'M12 2C17.5 2 22 6.5 22 12S17.5 22 12 22 2 17.5 2 12 6.5 2 12 2M12 4C10.1 4 8.4 4.6 7.1 5.7L18.3 16.9C19.3 15.5 20 13.8 20 12C20 7.6 16.4 4 12 4M16.9 18.3L5.7 7.1C4.6 8.4 4 10.1 4 12C4 16.4 7.6 20 12 20C13.9 20 15.6 19.4 16.9 18.3Z',
    'file-certificate-outline': 'M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14M14 2H7A2 2 0 0 0 5 4V18A2 2 0 0 0 7 20H8V18H7V4H13V8H17V18H16V20H17A2 2 0 0 0 19 18V7M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14M10 23L12 22L14 23V18H10M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14Z',
    'apple': 'M18.71,19.5C17.88,20.74 17,21.95 15.66,21.97C14.32,22 13.89,21.18 12.37,21.18C10.84,21.18 10.37,21.95 9.1,22C7.79,22.05 6.8,20.68 5.96,19.47C4.25,17 2.94,12.45 4.7,9.39C5.57,7.87 7.13,6.91 8.82,6.88C10.1,6.86 11.32,7.75 12.11,7.75C12.89,7.75 14.37,6.68 15.92,6.84C16.57,6.87 18.39,7.1 19.56,8.82C19.47,8.88 17.39,10.1 17.41,12.63C17.44,15.65 20.06,16.66 20.09,16.67C20.06,16.74 19.67,18.11 18.71,19.5M13,3.5C13.73,2.67 14.94,2.04 15.94,2C16.07,3.17 15.6,4.35 14.9,5.19C14.21,6.04 13.07,6.7 11.95,6.61C11.8,5.46 12.36,4.26 13,3.5Z',
    'cellphone': 'M17,19H7V5H17M17,1H7C5.89,1 5,1.89 5,3V21A2,2 0 0,0 7,23H17A2,2 0 0,0 19,21V3C19,1.89 18.1,1 17,1Z',
    'wifi-lock': 'M12 6C8.62 6 5.5 7.12 3 9L1.2 6.6C4.21 4.34 7.95 3 12 3S19.79 4.34 22.8 6.6L21 9C18.5 7.12 15.38 6 12 6M17.4 10.29C15.77 9.47 13.94 9 12 9C9.3 9 6.81 9.89 4.8 11.4L6.6 13.8C8.1 12.67 9.97 12 12 12C12.97 12 13.9 12.16 14.78 12.44C15.34 11.45 16.27 10.68 17.4 10.29M8.4 16.2L12 21L13 19.67V17.2C13 16.5 13.27 15.81 13.7 15.26C13.16 15.1 12.59 15 12 15C10.65 15 9.4 15.45 8.4 16.2M23 17.3V20.8C23 21.4 22.4 22 21.7 22H16.2C15.6 22 15 21.4 15 20.7V17.2C15 16.6 15.6 16 16.2 16V14.5C16.2 13.1 17.6 12 19 12S21.8 13.1 21.8 14.5V16C22.4 16 23 16.6 23 17.3M20.5 14.5C20.5 13.7 19.8 13.2 19 13.2S17.5 13.7 17.5 14.5V16H20.5V14.5Z',
    'server-security': 'M3,1H19A1,1 0 0,1 20,2V6A1,1 0 0,1 19,7H3A1,1 0 0,1 2,6V2A1,1 0 0,1 3,1M3,9H19A1,1 0 0,1 20,10V10.67L17.5,9.56L11,12.44V15H3A1,1 0 0,1 2,14V10A1,1 0 0,1 3,9M3,17H11C11.06,19.25 12,21.4 13.46,23H3A1,1 0 0,1 2,22V18A1,1 0 0,1 3,17M8,5H9V3H8V5M8,13H9V11H8V13M8,21H9V19H8V21M4,3V5H6V3H4M4,11V13H6V11H4M4,19V21H6V19H4M17.5,12L22,14V17C22,19.78 20.08,22.37 17.5,23C14.92,22.37 13,19.78 13,17V14L17.5,12M17.5,13.94L15,15.06V17.72C15,19.26 16.07,20.7 17.5,21.06V13.94Z',
    'check': 'M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z',
    'file-download-outline': 'M14,2L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2H14M18,20V9H13V4H6V20H18M12,19L8,15H10.5V12H13.5V15H16L12,19Z',
    'upload': 'M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z',
    'account-group': 'M12,5.5A3.5,3.5 0 0,1 15.5,9A3.5,3.5 0 0,1 12,12.5A3.5,3.5 0 0,1 8.5,9A3.5,3.5 0 0,1 12,5.5M5,8C5.56,8 6.08,8.15 6.53,8.42C6.38,9.85 6.8,11.27 7.66,12.38C7.16,13.34 6.16,14 5,14A3,3 0 0,1 2,11A3,3 0 0,1 5,8M19,8A3,3 0 0,1 22,11A3,3 0 0,1 19,14C17.84,14 16.84,13.34 16.34,12.38C17.2,11.27 17.62,9.85 17.47,8.42C17.92,8.15 18.44,8 19,8M5.5,18.25C5.5,16.18 8.41,14.5 12,14.5C15.59,14.5 18.5,16.18 18.5,18.25V20H5.5V18.25M0,20V18.5C0,17.11 1.89,15.94 4.45,15.6C3.86,16.28 3.5,17.22 3.5,18.25V20H0M24,20H20.5V18.25C20.5,17.22 20.14,16.28 19.55,15.6C22.11,15.94 24,17.11 24,18.5V20Z',
    'pencil': 'M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z',
    'restart': 'M12,4C14.1,4 16.1,4.8 17.6,6.3C20.7,9.4 20.7,14.5 17.6,17.6C15.8,19.5 13.3,20.2 10.9,19.9L11.4,17.9C13.1,18.1 14.9,17.5 16.2,16.2C18.5,13.9 18.5,10.1 16.2,7.7C15.1,6.6 13.5,6 12,6V10.6L7,5.6L12,0.6V4M6.3,17.6C3.7,15 3.3,11 5.1,7.9L6.6,9.4C5.5,11.6 5.9,14.4 7.8,16.2C8.3,16.7 8.9,17.1 9.6,17.4L9,19.4C8,19 7.1,18.4 6.3,17.6Z',
    'cog': 'M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z',
    'menu-down': 'M7,10L12,15L17,10H7Z',
    'close': 'M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z',
}


def esc(value):
    return html.escape(str(value), quote=True)


def icon(name, cls=""):
    return (f'<svg class="mdi {cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            f'<path d="{ICONS[name]}"/></svg>')


def chip(kind, text):
    """Status chip; kind is ok, warn, bad, info, or neutral."""
    return f'<span class="chip {kind}">{esc(text)}</span>'


ALERT_ICONS = {"info": "information-outline", "warning": "alert", "error": "alert-circle-outline",
               "success": "check-circle-outline"}


def alert(kind, body, title=""):
    """Home Assistant style alert banner; body is HTML."""
    role = ' role="alert"' if kind == "error" else ""
    head = f'<b class="alert-title">{esc(title)}</b>' if title else ""
    return (f'<div class="alert {kind}"{role}>{icon(ALERT_ICONS[kind], "alert-icon")}'
            f'<div class="alert-body">{head}{body}</div></div>')


def copy_button(value, what):
    return (f'<button type="button" class="icon-btn js-only" data-copy="{esc(value)}" '
            f'aria-label="Copy {esc(what)}" title="Copy {esc(what)}">{icon("content-copy")}</button>')


def kv_row(label, value, button=""):
    """A valid definition-list group; its action belongs to the definition."""
    return (f'<div class="kv"><dt>{label}</dt><dd class="kv-value">'
            f'<span class="kv-content">{value}</span>{button}</dd></div>')


def copy_field(value, what, cls=""):
    """A value shown in full with a copy action, e.g. a link or a password."""
    return (f'<div class="copy-field {cls}"><span class="mono">{esc(value)}</span>'
            f"{copy_button(value, what)}</div>")


def empty_state(icon_name, title, body=""):
    return (f'<div class="empty">{icon(icon_name)}<p class="empty-title">{esc(title)}</p>'
            f"{f'<p class=muted>{body}</p>' if body else ''}</div>")


def relative(when, now=None):
    """'in 23 days', '3 hours ago', and so on."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    seconds = (when - now).total_seconds()
    future = seconds >= 0
    seconds = abs(seconds)
    for unit, size in (("year", 31536000), ("month", 2592000), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            count = int(seconds // size)
            text = f"{count} {unit}{'s' if count != 1 else ''}"
            return f"in {text}" if future else f"{text} ago"
    return "now"


def when(value, now=None):
    """A date with its relative time, updated in the browser."""
    iso = value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f'<time datetime="{iso}" title="{value:%Y-%m-%d %H:%M} UTC">{value:%Y-%m-%d}</time>'
            f' <span class="rel" data-rel="{iso}">{relative(value, now)}</span>')


DIRECTION = """<!--
THESIS: Certificate setup stays understandable from the network choice through installation.
OWN-WORLD: The established Home Assistant theme, outlined surfaces, MDI icons, regular headings, and shared controls.
STORY: Match the network, choose how the device authenticates, verify server trust, then install a fresh profile.
FIRST VIEWPORT: A compact saved-network list and setup guide beside a wider editor; mobile puts the editor first.
FORM: Established Settings-page world extended with task sections; no replacement identity or generated comp.
SIGNATURE: Changing authentication reveals only its credentials and updates a readable profile summary.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->"""

STYLE = """
:root {
  color-scheme: light;
  --primary-color: #03a9f4;
  --primary-background-color: #fafafa;
  --secondary-background-color: #e5e5e5;
  --card-background-color: #ffffff;
  --primary-text-color: #212121;
  --secondary-text-color: #616161;
  --divider-color: rgba(0, 0, 0, .12);
  --success-color: #4caf50;
  --warning-color: #ff9800;
  --error-color: #db4437;
  --info-color: #039be5;
  --app-header-background-color: var(--primary-background-color);
  --app-header-text-color: var(--primary-text-color);
  --ha-card-border-radius: 12px;
  --mix-ink: #000;
  --ink-amount: 66%;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --primary-background-color: #111111;
    --secondary-background-color: #282828;
    --card-background-color: #1c1c1c;
    --primary-text-color: #e1e1e1;
    --secondary-text-color: #9b9b9b;
    --divider-color: rgba(225, 225, 225, .12);
    --mix-ink: #fff;
    --ink-amount: 82%;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --primary-background-color: #111111;
  --secondary-background-color: #282828;
  --card-background-color: #1c1c1c;
  --primary-text-color: #e1e1e1;
  --secondary-text-color: #9b9b9b;
  --divider-color: rgba(225, 225, 225, .12);
  --mix-ink: #fff;
  --ink-amount: 82%;
}
:root {
  /* Theme colors drawn as text or behind white text, kept at 4.5:1 or better. */
  --accent-ink: color-mix(in srgb, var(--primary-color) var(--ink-amount), var(--mix-ink));
  --accent-fill: color-mix(in srgb, var(--primary-color) 68%, #000);
  --ok-ink: color-mix(in srgb, var(--success-color) var(--ink-amount), var(--mix-ink));
  --warn-ink: color-mix(in srgb, var(--warning-color) 58%, var(--mix-ink));
  --bad-ink: color-mix(in srgb, var(--error-color) var(--ink-amount), var(--mix-ink));
  --info-ink: color-mix(in srgb, var(--info-color) var(--ink-amount), var(--mix-ink));
  --focus-color: var(--accent-ink);
  --danger-fill: color-mix(in srgb, var(--error-color) 86%, #000);
  --hover: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  --outline: color-mix(in srgb, var(--primary-text-color) 54%, transparent);
  --radius: var(--ha-card-border-radius, 12px);
  --ease-out: cubic-bezier(.16, 1, .3, 1);
  --mono: ui-monospace, "SF Mono", "Roboto Mono", Menlo, Consolas, monospace;
}
:root[data-theme="dark"] {
  --warn-ink: color-mix(in srgb, var(--warning-color) 90%, #fff);
  --bad-ink: color-mix(in srgb, var(--error-color) 70%, #fff);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --warn-ink: color-mix(in srgb, var(--warning-color) 90%, #fff);
    --bad-ink: color-mix(in srgb, var(--error-color) 70%, #fff);
  }
}
* { box-sizing: border-box; }
html { scrollbar-color: var(--scrollbar-thumb-color, var(--outline)) transparent; }
body {
  margin: 0; min-height: 100vh;
  font: 14px/20px Roboto, "Noto Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  letter-spacing: .01em;
  background: var(--primary-background-color); color: var(--primary-text-color);
  -webkit-font-smoothing: antialiased;
}
::selection { background: color-mix(in srgb, var(--primary-color) 32%, transparent); }
input, textarea { caret-color: var(--primary-color); }
:focus-visible { outline: 2px solid var(--focus-color); outline-offset: 2px; }
a { color: var(--accent-ink); text-decoration: none; text-underline-offset: 3px; }
a:hover { text-decoration: underline; }
b { font-weight: 500; }
h1, h2, h3 { font-weight: 400; margin: 0; text-wrap: balance; }
p { margin: 0 0 12px; }
p:last-child { margin-bottom: 0; }
.muted { color: var(--secondary-text-color); }
.mono { font-family: var(--mono); font-size: 13px; overflow-wrap: anywhere; }
.num, time, td { font-variant-numeric: tabular-nums; }
.mdi { width: 24px; height: 24px; fill: currentColor; flex: none; display: block; }
html:not(.js) .js-only { display: none !important; }

/* Toolbar and tabs, after hass-tabs-subpage */
.toolbar {
  position: sticky; top: 0; z-index: 4; height: 56px; display: flex; align-items: center; gap: 4px;
  padding: 0 12px 0 16px; background: var(--app-header-background-color); color: var(--app-header-text-color);
  border-bottom: 1px solid var(--divider-color);
}
.toolbar-title { font-size: 20px; line-height: 24px; font-weight: 400; margin: 0 24px 0 0; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.tabs { display: flex; height: 100%; }
.tab {
  display: flex; align-items: center; gap: 8px; padding: 0 20px; height: 100%; position: relative;
  color: var(--secondary-text-color); font-weight: 500; white-space: nowrap;
}
.tab .mdi { width: 20px; height: 20px; }
.tab:hover { color: var(--primary-text-color); text-decoration: none; background: var(--hover); }
.tab[aria-current="page"], .tab.current { color: var(--accent-ink); }
.tab[aria-current="page"]::after, .tab.current::after {
  content: ""; position: absolute; left: 12px; right: 12px; bottom: 0; height: 2px;
  border-radius: 2px 2px 0 0; background: var(--primary-color);
}
/* The Tools tab is a menu: a <details> that works without the script. */
.tab-menu { position: relative; height: 100%; }
.tab-menu > summary { list-style: none; cursor: pointer; user-select: none; }
.tab-menu > summary::-webkit-details-marker { display: none; }
.tab-menu > summary .caret { width: 18px; height: 18px; margin-left: -4px; transition: transform .2s var(--ease-out); }
.tab-menu[open] > summary .caret { transform: rotate(180deg); }
.tab-menu > summary:focus-visible { outline: 2px solid var(--focus-color); outline-offset: -2px; }
.menu {
  position: absolute; top: calc(100% + 4px); right: 0; z-index: 6; min-width: 260px; padding: 8px 0;
  background: var(--card-background-color); color: var(--primary-text-color); border-radius: 12px;
  border: 1px solid var(--divider-color); box-shadow: 0 8px 24px rgba(0, 0, 0, .18);
}
.menu a { display: flex; align-items: center; gap: 16px; padding: 10px 16px; color: inherit; min-height: 48px; }
.menu a:hover, .menu a:focus-visible { background: var(--hover); text-decoration: none; outline: none; }
.menu a[aria-current="page"] { color: var(--accent-ink); background: color-mix(in srgb, var(--primary-color) 10%, transparent); }
.menu a .mdi { color: var(--secondary-text-color); }
.menu a[aria-current="page"] .mdi { color: var(--accent-ink); }
.menu-text { display: flex; flex-direction: column; min-width: 0; }
.menu-sub { font-size: 12px; color: var(--secondary-text-color); }
.back { margin-left: -8px; color: inherit; }
.content { max-width: 1120px; margin: 0 auto; padding: 24px 24px 48px; }
.content.narrow { max-width: 760px; }
.page-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.page-head h1 { font-size: 24px; line-height: 32px; margin-right: auto; }

/* Cards, after ha-card */
.card {
  background: var(--card-background-color); border-radius: var(--radius);
  border: 1px solid var(--ha-card-border-color, var(--divider-color)); margin-bottom: 16px;
}
.card { container-type: inline-size; }
.card-header { padding: 16px 16px 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
.card-header h2 { font-size: 20px; line-height: 28px; margin-right: auto; }
.card-header > p { flex-basis: 100%; margin: 0; max-width: 72ch; }
.card-content { padding: 0 16px 16px; }
.card-content.flush { padding: 0; }
.card-actions {
  border-top: 1px solid var(--divider-color); padding: 8px 12px; display: flex; gap: 8px;
  justify-content: flex-end; align-items: center; flex-wrap: wrap;
}
.card-actions .spacer { margin-right: auto; }
.grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 16px; align-items: start; }
.grid > div > .card:last-child { margin-bottom: 0; }
.grid + .card, .grid + .grid { margin-top: 16px; }

/* Buttons, after ha-button */
.btn, button.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 40px;
  padding: 0 20px; border-radius: 20px; border: 0; font: 500 14px/1 inherit; letter-spacing: .02em;
  background: var(--accent-fill); color: #fff; cursor: pointer; text-decoration: none; white-space: nowrap;
  transition: box-shadow .15s, background-color .15s;
}
.btn .mdi { width: 18px; height: 18px; }
.btn:hover { text-decoration: none; background: color-mix(in srgb, var(--accent-fill) 88%, #000);
  box-shadow: 0 1px 3px rgba(0, 0, 0, .24); }
.btn.text { background: transparent; color: var(--accent-ink); padding: 0 12px; }
.btn.text:hover { background: color-mix(in srgb, var(--primary-color) 10%, transparent); box-shadow: none; }
.btn.danger { background: var(--danger-fill); }
.btn.danger:hover { background: color-mix(in srgb, var(--danger-fill) 86%, #000); }
.btn.text.danger { background: transparent; color: var(--bad-ink); }
.btn.text.danger:hover { background: color-mix(in srgb, var(--error-color) 10%, transparent); }
.btn:disabled { background: var(--hover); color: var(--secondary-text-color); cursor: default; box-shadow: none; }
.icon-btn {
  display: inline-grid; place-items: center; width: 36px; height: 36px; flex: none; border-radius: 50%;
  border: 0; background: transparent; color: var(--secondary-text-color); cursor: pointer; padding: 0;
}
.icon-btn .mdi { width: 20px; height: 20px; }
.icon-btn:hover { background: var(--hover); color: var(--primary-text-color); }
a.icon-btn:hover { text-decoration: none; }

/* Shared navigation and task forms */
.settings-intro { max-width:72ch; margin-bottom:24px; }
.settings-layout { display:grid; grid-template-columns:240px minmax(0,1fr); gap:32px; align-items:start; }
.settings-content { min-width:0; }
.settings-menu { position:sticky; top:80px; }
.settings-menu > summary { display:none; }
.settings-menu nav { display:flex; flex-direction:column; }
.settings-menu nav a { display:flex; align-items:center; min-height:44px; padding:10px 12px;
  color:var(--primary-text-color); overflow-wrap:anywhere; border-radius:8px; }
.settings-menu nav a:hover { background:var(--hover); text-decoration:none; }
.settings-menu nav a[aria-current=page], .settings-menu .selected-category {
  color:var(--accent-ink); background:color-mix(in srgb,var(--primary-color) 10%,transparent); }
.settings-menu .settings-submenu { margin-top:16px; padding-top:16px; border-top:1px solid var(--divider-color); }
.settings-breadcrumb { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:16px; font-size:14px; }
.settings-breadcrumb a { min-height:44px; display:inline-flex; align-items:center; }
.settings-breadcrumb > span { overflow-wrap:anywhere; min-width:0; }
.settings-title { font-size:24px; line-height:32px; margin-bottom:24px; font-weight:400; }
.settings-row .row-text { overflow-wrap:anywhere; }
.settings-row .row-sub { line-height:20px; }
.settings-value { overflow-wrap:anywhere; }
.settings-content > .btn { min-height:44px; height:auto; padding-block:10px; white-space:normal; }
.settings-content > .hint { margin-block:16px 24px; max-width:72ch; }
@media (max-width:900px) {
  .settings-layout { grid-template-columns:minmax(0,1fr); gap:24px; }
  .settings-menu { position:static; border-bottom:1px solid var(--divider-color); }
  .settings-menu > summary { display:flex; align-items:center; justify-content:space-between; gap:12px;
    min-height:48px; padding:12px 0; cursor:pointer; list-style:none; }
  .settings-menu > summary::-webkit-details-marker { display:none; }
  .settings-menu nav { padding-block:8px 16px; }
  .settings-title { font-size:22px; line-height:28px; margin-bottom:20px; }
}
[hidden] { display: none !important; }
.skip-link { position: fixed; top: -100px; left: 16px; z-index: 20; padding: 12px 16px;
  background: var(--card-background-color); color: var(--accent-ink); border-radius: 8px; }
.skip-link:focus { top: 8px; }
.tool-nav { display: flex; flex-wrap: wrap; gap: 4px 8px; margin-bottom: 24px; padding-bottom: 12px;
  border-bottom: 1px solid var(--divider-color); }
.tool-nav a { padding: 10px 12px; min-height: 44px; border-radius: 8px; color: var(--secondary-text-color); }
.tool-nav a:hover { background: var(--hover); text-decoration: none; }
.tool-nav a[aria-current=page] { color: var(--accent-ink); font-weight: 500;
  background: color-mix(in srgb, var(--primary-color) 10%, transparent); }
.network-layout { display: grid; grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr); gap: 24px; align-items: start; }
.network-layout > aside { grid-column: 1; grid-row: 1; }
.network-layout > div { grid-column: 2; grid-row: 1; }
.page-jumps { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-bottom: 16px; }
.page-jumps a { min-height: 44px; display: inline-flex; align-items: center; }
[id] { scroll-margin-top: 72px; }
.network-layout .row { flex-wrap: wrap; }
.network-layout .row-actions { margin-left: auto; }
.network-layout .row-sub { overflow-wrap: anywhere; }
.network-fields { padding: 0 !important; }
.form-section { border-top: 1px solid var(--divider-color); }
.form-section > summary { list-style: none; display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 16px 20px; min-height: 56px; cursor: pointer; }
.form-section > summary::-webkit-details-marker { display: none; }
.form-section > summary:hover { background: var(--hover); }
.form-section .chev { width: 20px; height: 20px; color: var(--secondary-text-color); transition: transform .2s var(--ease-out); }
.form-section[open] > summary .chev { transform: rotate(180deg); }
.section-body { padding: 0 20px 20px; }
.network-summary { padding: 12px 20px; display: flex; flex-wrap: wrap; gap: 8px 16px;
  background: var(--hover); color: var(--secondary-text-color); min-height: 44px; }
.network-summary:empty { display: none; }
.network-summary b { color: var(--primary-text-color); }
.method-row { display: grid; gap: 2px; padding: 10px 0; }
.method-row + .method-row { border-top: 1px solid var(--divider-color); }
.secret-input { display: flex; align-items: center; gap: 8px; }
.secret-input input { min-width: 0; flex: 1; }
input:disabled, select:disabled, textarea:disabled { background: var(--hover); color: var(--secondary-text-color); cursor: default; }
form[aria-busy=true] { cursor: progress; }
@media (max-width: 860px) {
  .network-layout { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .network-layout > aside, .network-layout > div { grid-column: auto; grid-row: auto; }
}
@media (max-width: 640px) {
  .tool-nav { gap: 4px; margin-bottom: 16px; }
  .tool-nav a { padding: 8px 10px; }
  .section-body { padding: 0 16px 16px; }
  .form-section > summary { padding: 14px 16px; }
}

/* Form fields */
.field { margin-bottom: 16px; }
.field:last-child { margin-bottom: 0; }
details.field > summary { cursor: pointer; width: fit-content; color: var(--accent-ink); font-weight: 500; }
details.field[open] > summary { margin-bottom: 12px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
label, .label { display: block; font-weight: 500; margin-bottom: 6px; }
fieldset { border: 0; margin: 0 0 16px; padding: 0; min-width: 0; }
legend { padding: 0; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.mdm-form { padding: 16px; border-top: 1px solid var(--divider-color); }
.mdm-form h3 { font-size: 16px; line-height: 24px; font-weight: 500; margin-bottom: 4px; }
.mdm-form > .muted { margin-bottom: 16px; }
input:where(:not([type=radio], [type=checkbox], [type=file])), select, textarea {
  width: 100%; min-height: 44px; padding: 10px 12px; font: inherit; color: var(--primary-text-color);
  background: var(--card-background-color); border: 1px solid var(--outline); border-radius: 8px;
  transition: border-color .15s, box-shadow .15s;
}
textarea { font-family: var(--mono); font-size: 13px; resize: vertical; min-height: 96px; }
input:hover, select:hover, textarea:hover { border-color: var(--primary-text-color); }
input:focus, select:focus, textarea:focus { outline: none; border-color: var(--focus-color);
  box-shadow: 0 0 0 1px var(--focus-color); }
input::placeholder, textarea::placeholder { color: var(--secondary-text-color); opacity: 1; }
input[type=file] { font: inherit; color: var(--secondary-text-color); max-width: 100%; }
input[type=file]::file-selector-button {
  font: 500 14px inherit; height: 36px; padding: 0 16px; margin-right: 12px; border-radius: 18px; cursor: pointer;
  border: 1px solid var(--outline); background: transparent; color: var(--accent-ink);
}
input[type=radio], input[type=checkbox] { accent-color: var(--accent-fill); width: 18px; height: 18px; margin: 0; flex: none; }
.hint { color: var(--secondary-text-color); font-size: 12px; line-height: 16px; margin-top: 6px; }
.check { display: flex; gap: 12px; align-items: center; font-weight: 400; margin: 0; }
/* A text input with a button beside it, e.g. a challenge and Generate. */
.input-action { display: flex; gap: 8px; align-items: center; }
.alert-action { margin-top: 8px; }
span.alert-action { display: flex; flex-wrap: wrap; gap: 8px; }
.input-action > input { flex: 1; min-width: 0; }
/* A menu of known values above the text input it fills ("Custom..." shows the input). */
.preset + input { margin-top: 8px; }
html.js .preset + input.preset-hidden { display: none; }

/* Choice cards */
.choices { display: grid; gap: 12px; }
.choice {
  display: flex; gap: 16px; align-items: flex-start; padding: 16px; margin: 0; font-weight: 400; cursor: pointer;
  border: 1px solid var(--outline); border-radius: var(--radius); transition: border-color .15s, background-color .15s;
}
.choice:hover { background: var(--hover); }
.choice:has(input:checked) { border-color: var(--primary-color); box-shadow: inset 0 0 0 1px var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 6%, transparent); }
.choice input { margin-top: 3px; }
.choice-icon { color: var(--accent-ink); }
.choice-title { display: block; font-weight: 500; font-size: 16px; line-height: 24px; }
.choice .muted { display: block; margin-top: 2px; }

/* Filter chips and status chips */
.filters { display: flex; flex-wrap: wrap; gap: 8px; }
.filter {
  display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px; border-radius: 8px;
  border: 1px solid var(--outline); color: var(--primary-text-color); font-weight: 500;
}
.filter:hover { background: var(--hover); text-decoration: none; }
.filter .mdi { width: 18px; height: 18px; }
.filter[aria-current="true"] { background: color-mix(in srgb, var(--primary-color) 16%, transparent);
  border-color: transparent; color: var(--primary-text-color); }
.filter .count { color: var(--secondary-text-color); font-weight: 400; }
.chip {
  display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 10px 0 8px; border-radius: 12px;
  font-size: 12px; font-weight: 500; white-space: nowrap; letter-spacing: .02em;
  color: var(--chip-ink); background: color-mix(in srgb, var(--chip) 14%, transparent);
}
.chip::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--chip); }
.chip.ok { --chip: var(--success-color); --chip-ink: var(--ok-ink); }
.chip.warn { --chip: var(--warning-color); --chip-ink: var(--warn-ink); }
.chip.bad { --chip: var(--error-color); --chip-ink: var(--bad-ink); }
.chip.info { --chip: var(--info-color); --chip-ink: var(--info-ink); }
.chip.neutral { --chip: var(--secondary-text-color); --chip-ink: var(--secondary-text-color); }
.rel { color: var(--secondary-text-color); }
.rel.warn { color: var(--warn-ink); font-weight: 500; }
.rel.bad { color: var(--bad-ink); }

/* Alerts, after ha-alert */
.alert {
  display: flex; gap: 12px; align-items: flex-start; padding: 10px 12px; border-radius: 8px; margin-bottom: 16px;
  background: color-mix(in srgb, var(--alert) 12%, transparent); color: var(--primary-text-color);
}
.card .alert:last-child { margin-bottom: 0; }
.alert-icon { color: var(--alert-ink); margin-top: -2px; }
.alert-body { flex: 1; min-width: 0; }
.alert-title { display: block; margin-bottom: 2px; }
.alert.info { --alert: var(--info-color); --alert-ink: var(--info-ink); }
.alert.warning { --alert: var(--warning-color); --alert-ink: var(--warn-ink); }
.alert.error { --alert: var(--error-color); --alert-ink: var(--bad-ink); }
.alert.success { --alert: var(--success-color); --alert-ink: var(--ok-ink); }

/* Health summary, after the tile card */
.health { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.tile { display: flex; gap: 12px; align-items: center; padding: 16px; color: inherit; min-width: 0; }
.tile + .tile { border-left: 1px solid var(--divider-color); }
a.tile:hover { background: var(--hover); text-decoration: none; }
.tile-icon {
  width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; flex: none;
  color: var(--tile-ink); background: color-mix(in srgb, var(--tile) 16%, transparent);
}
.tile-icon .mdi { width: 22px; height: 22px; }
.tile-text { min-width: 0; }
.tile-primary { display: block; font-size: 16px; line-height: 24px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile-secondary { display: block; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.tile.ok { --tile: var(--success-color); --tile-ink: var(--ok-ink); }
.tile.warn { --tile: var(--warning-color); --tile-ink: var(--warn-ink); }
.tile.bad { --tile: var(--error-color); --tile-ink: var(--bad-ink); }
.tile.info { --tile: var(--primary-color); --tile-ink: var(--accent-ink); }
.tile.neutral { --tile: var(--secondary-text-color); --tile-ink: var(--secondary-text-color); }

/* Search */
.search { position: relative; flex: 1; min-width: 220px; }
.search .mdi { position: absolute; left: 12px; top: 12px; width: 20px; height: 20px; color: var(--secondary-text-color);
  pointer-events: none; }
.search input { padding-left: 42px; border-radius: 22px; }
.list-tools { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 16px; }

/* Data table, after ha-data-table */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; font-weight: 500; color: var(--secondary-text-color); height: 48px; padding: 0 16px;
  border-bottom: 1px solid var(--divider-color); white-space: nowrap;
}
td { padding: 12px 16px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; }
tbody tr:last-child td { border-bottom: 0; }
tr.link-row { position: relative; }
tr.link-row:hover td { background: var(--hover); }
tr.link-row a.row-link { color: var(--primary-text-color); font-weight: 500; }
tr.link-row a.row-link::after { content: ""; position: absolute; inset: 0; }
tr.link-row a.row-link:focus-visible { outline: none; }
tr.link-row:has(a.row-link:focus-visible) td { background: var(--hover); box-shadow: inset 0 1px var(--focus-color), inset 0 -1px var(--focus-color); }
td .sub { display: block; color: var(--secondary-text-color); font-size: 13px; line-height: 18px; margin-top: 2px;
  overflow-wrap: anywhere; }
td.actions { text-align: right; width: 1%; white-space: nowrap; }
td.actions form { margin: 0; position: relative; z-index: 1; }
.list-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px;
  padding: 0 16px 16px; }
.list-bar form { margin: 0; }
.pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 8px 16px 16px;
  color: var(--secondary-text-color); }
.nowrap { white-space: nowrap; }
.only-mobile, td .sub.only-mobile { display: none; }
.empty { text-align: center; padding: 40px 16px; color: var(--secondary-text-color); }
.empty .mdi { width: 48px; height: 48px; margin: 0 auto 12px; opacity: .6; }
.empty-title { font-size: 16px; color: var(--primary-text-color); margin-bottom: 4px; }

/* Rows, after ha-settings-row */
.rows { margin: 0; }
.row { display: flex; align-items: center; gap: 16px; padding: 12px 16px; min-height: 64px; }
.row + .row { border-top: 1px solid var(--divider-color); }
.row-icon { color: var(--secondary-text-color); }
.row-text { flex: 1; min-width: 0; }
.row-title { display: block; overflow-wrap: anywhere; }
.row-sub { display: block; color: var(--secondary-text-color); overflow-wrap: anywhere; }
.row-actions { display: flex; gap: 4px; align-items: center; flex: none; }
.row-actions form { margin: 0; }
a.row { color: inherit; }
a.row:hover { background: var(--hover); text-decoration: none; }
dl.rows dt { color: var(--secondary-text-color); }
.kv { display: grid; grid-template-columns: minmax(120px, 180px) minmax(0, 1fr) auto; align-items: center;
  gap: 4px 16px; padding: 10px 16px; min-height: 48px; }
.kv + .kv { border-top: 1px solid var(--divider-color); }
.kv dt { color: var(--secondary-text-color); }
.kv dd { margin: 0; overflow-wrap: anywhere; }
.kv dd.kv-value { grid-column: 2 / -1; display: grid;
  grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 16px; }
.kv-content { min-width: 0; }
.kv .icon-btn { margin: -8px 0; }
@container (max-width: 520px) {
  .kv { grid-template-columns: minmax(0, 1fr) auto; }
  .kv dt { grid-column: 1 / -1; margin-bottom: -2px; font-size: 12px; }
  .kv dd.kv-value { grid-column: 1 / -1; }
}

/* Expansion panels, after ha-expansion-panel */
details.expand { border-top: 1px solid var(--divider-color); }
.card > details.expand:first-child { border-top: 0; }
.card > details.expand:first-child > summary { border-radius: var(--radius) var(--radius) 0 0; }
.card > details.expand:last-child:not([open]) > summary { border-radius: 0 0 var(--radius) var(--radius); }
.card > details.expand:only-child:not([open]) > summary { border-radius: var(--radius); }
details.expand > summary:focus-visible, .row :focus-visible, .card > .table-wrap :focus-visible { outline-offset: -2px; }
.card > .table-wrap:last-child { border-radius: 0 0 var(--radius) var(--radius); }
.health > .tile:first-child { border-radius: var(--radius) 0 0 var(--radius); }
.health > .tile:last-child { border-radius: 0 var(--radius) var(--radius) 0; }
.subhead { padding: 16px 16px 4px; color: var(--secondary-text-color); font-size: 14px; font-weight: 500;
  border-top: 1px solid var(--divider-color); }
.choice-detail { display: none; margin-top: 8px; }
.choice:has(input:checked) .choice-detail { display: block; }
.choice-detail .kv { padding: 4px 0; min-height: 0; grid-template-columns: minmax(0, 1fr); gap: 0; }
.choice-detail .kv dt { grid-column: 1; margin: 0; font-size: 12px; }
.choice-detail .kv + .kv { border-top: 0; }
.expand-note { padding: 0 16px 8px; }
.form-submit { margin-top: 16px; }
.step-action { margin-top: 12px; }
.steps-gap { margin-top: 20px; }
.input-short { max-width: 160px; }
.card > .filters { padding: 0 16px 16px; }
.inline-alert { padding: 0 16px; }
.inline-alert .alert { margin: 0 0 8px; }
details.expand > summary {
  list-style: none; display: flex; align-items: center; gap: 12px; padding: 12px 16px; min-height: 56px; cursor: pointer;
}
details.expand > summary::-webkit-details-marker { display: none; }
details.expand > summary:hover { background: var(--hover); }
details.expand > summary .chev { margin-left: auto; color: var(--secondary-text-color); transition: transform .2s var(--ease-out); }
details.expand[open] > summary .chev { transform: rotate(180deg); }
details.expand > .expand-body { padding: 4px 16px 16px; }
details.expand > .expand-body.flush { padding: 0 0 4px; }
.summary-text { min-width: 0; }
.summary-title { display: block; font-size: 16px; line-height: 24px; }
.summary-sub { display: block; color: var(--secondary-text-color); }

/* Certificate detail */
.cert-head { padding: 20px 16px 16px; }
.cert-head h2 { font-size: 24px; line-height: 32px; overflow-wrap: anywhere; margin-bottom: 8px; }
.cert-meta { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.validity { margin-top: 20px; }
.validity-track { position: relative; height: 6px; border-radius: 3px; background: var(--secondary-background-color); }
.validity-fill { position: absolute; inset: 0 auto 0 0; border-radius: 3px; background: var(--bar, var(--primary-color)); }
.validity-now { position: absolute; top: -4px; width: 2px; height: 14px; margin-left: -1px; border-radius: 1px;
  background: var(--primary-text-color); }
.validity-labels { display: flex; justify-content: space-between; gap: 16px; margin-top: 8px; color: var(--secondary-text-color);
  font-variant-numeric: tabular-nums; }
.danger-zone .card-header h2 { color: var(--bad-ink); }
.revoke-form { display: grid; grid-template-columns: minmax(0, 220px) minmax(0, 1fr) auto; gap: 12px; align-items: end; }

/* One-time secrets */
.copy-field {
  display: flex; align-items: center; gap: 8px; padding: 6px 6px 6px 14px; min-height: 48px; border-radius: 8px;
  background: var(--secondary-background-color);
}
.copy-field .mono { flex: 1; min-width: 0; }
.copy-field.secret .mono { font-size: 22px; line-height: 32px; letter-spacing: .08em; }
.qr { background: #fff; padding: 12px; border-radius: var(--radius); display: block; width: fit-content; margin: 0 auto 16px; }
.qr svg { width: 232px; height: 232px; display: block; }
.result { text-align: center; }
.result .copy-field { text-align: left; margin-bottom: 12px; }

/* Steps */
ol.steps { list-style: none; counter-reset: step; margin: 0; padding: 0; }
ol.steps li { counter-increment: step; position: relative; padding: 2px 0 16px 44px; }
ol.steps li:last-child { padding-bottom: 0; }
ol.steps li::before {
  content: counter(step); position: absolute; left: 0; top: 0; width: 28px; height: 28px; border-radius: 50%;
  display: grid; place-items: center; font-weight: 500; font-size: 13px;
  background: color-mix(in srgb, var(--primary-color) 16%, transparent); color: var(--accent-ink);
}

/* Public pages, after Home Assistant's sign-in page */
.public { max-width: 520px; margin: 0 auto; padding: 32px 16px 48px; }
.brand { display: flex; align-items: center; gap: 12px; margin: 0 4px 20px; color: var(--secondary-text-color); font-size: 16px; }
.brand-mark { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
  background: color-mix(in srgb, var(--primary-color) 16%, transparent); color: var(--accent-ink); }
.public .card-header h1 { font-size: 24px; line-height: 32px; }

/* Dialog and toast: the panel's one authored motion */
dialog {
  border: 0; border-radius: 28px; padding: 24px; width: min(440px, calc(100vw - 32px)); color: var(--primary-text-color);
  background: var(--card-background-color); box-shadow: 0 12px 32px rgba(0, 0, 0, .28);
}
dialog::backdrop { background: rgba(0, 0, 0, .4); }
dialog[open] { animation: dialog-in .28s var(--ease-out); }
dialog h2 { font-size: 22px; line-height: 28px; margin-bottom: 12px; }
dialog .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }
@keyframes dialog-in { from { opacity: 0; transform: scale(.94); } }
.toast {
  position: fixed; left: 50%; bottom: 24px; z-index: 10; transform: translate(-50%, 24px); opacity: 0;
  padding: 14px 20px; border-radius: 8px; background: #323232; color: #f1f1f1; box-shadow: 0 4px 12px rgba(0, 0, 0, .3);
  pointer-events: none; transition: transform .4s var(--ease-out), opacity .25s var(--ease-out);
}
.toast.show { transform: translate(-50%, 0); opacity: 1; }
@media (prefers-reduced-motion: reduce) {
  dialog[open] { animation: none; }
  .toast, details.expand > summary .chev, .form-section .chev { transition: none; }
}

@media (max-width: 860px) {
  .grid { grid-template-columns: 1fr; gap: 0; }
  .grid > div > .card:last-child { margin-bottom: 16px; }
  .grid + .card, .grid + .grid { margin-top: 0; }
  .health { grid-template-columns: 1fr 1fr; }
  .tile:nth-child(3) { border-left: 0; }
  .tile:nth-child(n+3) { border-top: 1px solid var(--divider-color); }
  .tile { gap: 10px; padding: 12px; align-items: flex-start; }
  .tile-icon { width: 36px; height: 36px; }
  .tile-primary, .tile-secondary { white-space: normal; overflow-wrap: anywhere; }
}
@media (max-width: 640px) {
  body.has-tabs { padding-bottom: 64px; }
  .tabs {
    position: fixed; left: 0; right: 0; bottom: 0; height: 56px; z-index: 4;
    background: var(--app-header-background-color); border-top: 1px solid var(--divider-color);
  }
  .tab { flex: 1; flex-direction: column; justify-content: center; gap: 2px; padding: 0 4px; font-size: 12px; }
  .tab-menu { flex: 1; position: static; }
  .tab-menu > summary { height: 100%; }
  .tab-menu > summary .caret { display: none; }
  .menu { position: fixed; top: auto; bottom: 64px; right: 8px; left: 8px; min-width: 0; }
  .tab[aria-current="page"]::after, .tab.current::after { top: 0; bottom: auto; border-radius: 0 0 2px 2px; left: 25%; right: 25%; }
  .content { padding: 16px 12px 32px; }
  .field-row, .revoke-form { grid-template-columns: 1fr; }
  .hide-mobile { display: none; }
  .only-mobile, td .sub.only-mobile { display: block; }
  td, th { padding-left: 12px; padding-right: 12px; }
  .kv { grid-template-columns: minmax(0, 1fr) auto; }
  .kv dt { grid-column: 1 / -1; margin-bottom: -2px; font-size: 12px; }
  .toast { bottom: 76px; max-width: calc(100vw - 32px); }
  .copy-field.secret .mono { font-size: 18px; }
  .public { padding-top: 20px; }
  .kv dd.kv-value { grid-column: 1 / -1; }
  .row:has(.row-actions > :nth-child(3)) { flex-wrap: wrap; }
  .row:has(.row-actions > :nth-child(3)) > .row-actions { flex-basis: 100%; justify-content: flex-end; }
  input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea { font-size: 16px; }
  .btn, .icon-btn, .filter { min-height: 44px; }
  .icon-btn { min-width: 44px; }
}
/* Inline links remain recognizable without color; controls keep their own shape. */
:where(p, .hint, small, dd) a:not(.btn):not(.icon-btn) { text-decoration: underline; text-underline-offset: .15em; }
.btn, .icon-btn, .filter { min-height: 44px; }
.icon-btn { min-width: 44px; }

/* Resident progress, validation and bounded inventory navigation. */
.onboarding-progress { margin-block:0 24px; }
.onboarding-progress ol { display:flex; flex-wrap:wrap; gap:8px 16px; list-style:none; padding:0; margin:0; counter-reset:connection-step; }
.onboarding-progress li { counter-increment:connection-step; color:var(--secondary-text-color); }
.onboarding-progress li::before { content:counter(connection-step) ". "; font-variant-numeric:tabular-nums; }
.onboarding-progress li[aria-current=step] { color:var(--primary-text-color); font-weight:600; text-decoration:underline; text-underline-offset:5px; }
.field-error { color:var(--bad-ink); margin-block:8px 16px; }
[aria-invalid=true] { border-color:var(--bad-ink); }
.pagination { display:flex; flex-wrap:wrap; align-items:center; gap:8px 16px; padding:16px; }
.pagination span { color:var(--secondary-text-color); }
.resident-help { margin-block-start:24px; border-block-start:1px solid var(--divider-color); }
.setup-state { margin-block:8px 16px; }
.mobile-tool-navigation { display:none; }
@media (max-width:640px) {
  .desktop-tool-navigation { display:none; }
  .mobile-tool-navigation { display:block; margin-block-end:16px; }
  .mobile-tool-navigation summary { min-height:44px; padding:12px; cursor:pointer; }
}
"""

SCRIPT = r"""
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  // Keep the settings hierarchy available without JavaScript; fold it on phones.
  var settingsMenu = document.querySelector(".settings-menu");
  if (settingsMenu) {
    var settingsNarrow = window.matchMedia("(max-width:900px)");
    function settingsLayout() { settingsMenu.open = !settingsNarrow.matches; }
    settingsLayout();
    settingsNarrow.addEventListener("change", settingsLayout);
  }
  // iPadOS Safari says it is a Mac; touch tells them apart.
  document.querySelectorAll("input[data-touch]").forEach(function (input) {
    input.value = navigator.maxTouchPoints > 1 ? "1" : "";
  });

  // Wear the user's Home Assistant theme when shown inside Home Assistant.
  var NAMES = ["--primary-color", "--primary-background-color", "--secondary-background-color",
    "--card-background-color", "--primary-text-color", "--secondary-text-color", "--divider-color",
    "--success-color", "--warning-color", "--error-color", "--info-color", "--ha-card-border-radius",
    "--ha-card-border-color", "--app-header-background-color", "--app-header-text-color",
    "--scrollbar-thumb-color"];
  function luminance(color) {
    var probe = document.createElement("i");
    probe.style.color = color;
    document.body.appendChild(probe);
    var rgb = getComputedStyle(probe).color.match(/[\d.]+/g) || [];
    probe.remove();
    if (rgb.length < 3) return null;
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
  }
  function adopt() {
    var parentRoot;
    try {
      if (window.parent === window) return;
      parentRoot = window.parent.document.documentElement;
    } catch (e) { return; }
    var cs = window.parent.getComputedStyle(parentRoot);
    var bg = cs.getPropertyValue("--primary-background-color").trim();
    if (!bg) return;
    NAMES.forEach(function (name) {
      var value = cs.getPropertyValue(name).trim();
      if (value) root.style.setProperty(name, value); else root.style.removeProperty(name);
    });
    var lum = luminance(bg);
    if (lum !== null) root.setAttribute("data-theme", lum < 0.5 ? "dark" : "light");
    if (!adopt.watching) {
      adopt.watching = true;
      new MutationObserver(adopt).observe(parentRoot, { attributes: true, attributeFilter: ["style", "class"] });
      var head = window.parent.document.head;
      if (head) new MutationObserver(adopt).observe(head, { childList: true, subtree: true, characterData: true });
    }
  }
  try { adopt(); } catch (e) { /* the page's own light and dark themes still apply */ }

  // Copy buttons with a Home Assistant style toast.
  var toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  document.body.appendChild(toast);
  var timer;
  function say(text) {
    toast.textContent = text;
    toast.classList.add("show");
    clearTimeout(timer);
    timer = setTimeout(function () { toast.classList.remove("show"); }, 2400);
  }
  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }
  // Open the panel a link or redirect points at, such as /ca#sign.
  function openTarget() {
    var target = location.hash.length > 1 && document.getElementById(location.hash.slice(1));
    if (target && target.tagName === "DETAILS") target.open = true;
  }
  openTarget();
  window.addEventListener("hashchange", openTarget);
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;
    var text = button.getAttribute("data-copy");
    var what = (button.getAttribute("aria-label") || "Copy").replace(/^Copy /, "");
    var done = function () { say("Copied " + what); };
    var fail = function () { say(fallbackCopy(text) ? "Copied " + what : "Copy failed; select the text instead"); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fail);
    } else {
      fail();
    }
  });

  // Confirm before an irreversible form is sent. Several forms may share one
  // dialog; data-confirm-name fills its [data-confirm-name] slot.
  document.querySelectorAll("dialog").forEach(function (dialog) {
    var yes = dialog.querySelector("[data-confirm-yes]"), no = dialog.querySelector("[data-confirm-no]");
    if (yes) yes.addEventListener("click", function () {
      var form = dialog.pendingForm;
      dialog.close();
      if (form) { markSubmitting(form); form.submit(); }
    });
    if (no) no.addEventListener("click", function () { dialog.close(); });
  });
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    var dialog = document.getElementById(form.getAttribute("data-confirm"));
    if (!dialog || !dialog.showModal) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var slot = dialog.querySelector("[data-confirm-name]");
      if (slot && form.hasAttribute("data-confirm-name")) slot.textContent = form.getAttribute("data-confirm-name");
      dialog.pendingForm = form;
      dialog.showModal();
    });
  });

  // The Tools menu closes on a click elsewhere, on Escape, or when another opens.
  var menus = Array.prototype.slice.call(document.querySelectorAll("details.tab-menu"));
  document.addEventListener("click", function (event) {
    menus.forEach(function (menu) { if (menu.open && !menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    menus.forEach(function (menu) {
      if (menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
  });

  // Menus of known values: <select class="preset" data-for="id"> fills the
  // text input with that id, which is what the form sends. "Custom..." (an
  // empty data-custom option) shows the input for any other value.
  function syncPreset(select, fromInput) {
    var input = document.getElementById(select.getAttribute("data-for"));
    if (!input) return;
    var options = Array.prototype.slice.call(select.options).filter(function (o) { return !o.hidden && !o.disabled; });
    if (fromInput) {
      var match = options.filter(function (o) { return !o.hasAttribute("data-custom") && o.value === input.value; })[0];
      var custom = options.filter(function (o) { return o.hasAttribute("data-custom"); })[0];
      if (match) select.value = match.value;
      else if (custom && input.value) custom.selected = true;
      else if (options[0]) { select.value = options[0].value; input.value = options[0].hasAttribute("data-custom") ? input.value : options[0].value; }
    }
    var chosen = select.options[select.selectedIndex];
    var isCustom = chosen && chosen.hasAttribute("data-custom");
    if (!fromInput && !isCustom && chosen) input.value = chosen.value;
    input.classList.toggle("preset-hidden", !isCustom);
    if (!fromInput && isCustom) input.focus();
  }
  document.querySelectorAll("select.preset").forEach(function (select) {
    syncPreset(select, true);
    select.addEventListener("change", function () { syncPreset(select, false); });
  });

  // "Your MDM" shows only that MDM's variables in the menus below it.
  document.querySelectorAll("select[data-mdm-switch]").forEach(function (picker) {
    var form = picker.form;
    function apply(keepValues) {
      form.querySelectorAll("select.preset option[data-mdm]").forEach(function (option) {
        var other = option.getAttribute("data-mdm") !== picker.value;
        option.hidden = other;
        option.disabled = other;
      });
      form.querySelectorAll("select.preset").forEach(function (select) {
        if (!keepValues) {
          var first = Array.prototype.slice.call(select.options).filter(function (o) { return !o.disabled; })[0];
          var input = document.getElementById(select.getAttribute("data-for"));
          if (first && input) input.value = first.hasAttribute("data-custom") ? "" : first.value;
        }
        syncPreset(select, true);
      });
      try { localStorage.setItem("mdm", picker.value); } catch (e) { /* not remembered */ }
    }
    var saved = null;
    try { saved = localStorage.getItem("mdm"); } catch (e) { saved = null; }
    if (saved && picker.querySelector('option[value="' + saved + '"]')) picker.value = saved;
    apply(false);
    picker.addEventListener("change", function () { apply(false); });
  });

  // Fields shown only for one choice of a menu (or a ticked checkbox): data-show-when="id=value".
  document.querySelectorAll("[data-show-when]").forEach(function (block) {
    var rules = block.getAttribute("data-show-when").split(";").map(function (rule) {
      var pair = rule.split("=");
      return { control: document.getElementById(pair[0]), values: (pair[1] || "").split("|") };
    }).filter(function (rule) { return rule.control; });
    if (!rules.length) return;
    function apply() {
      block.hidden = !rules.some(function (rule) {
        var select = rule.control;
        var value = select.type === "checkbox" ? (select.checked ? select.value : "") : select.value;
        return rule.values.indexOf(value) !== -1;
      });
      if (block.hasAttribute("data-control-when-visible")) {
        block.querySelectorAll("input, select, textarea").forEach(function (control) {
          control.disabled = block.hidden;
          if (control.hasAttribute("data-required-when-visible")) control.required = !block.hidden;
        });
      }
    }
    apply();
    rules.forEach(function (rule) { rule.control.addEventListener("change", apply); });
  });

  // Search only the already permitted resident choices; no directory requests.
  document.querySelectorAll("[data-choice-filter]").forEach(function (group) {
    var input = group.querySelector("[data-filter-input]");
    var select = group.querySelector("select");
    var status = group.querySelector("[data-filter-status]");
    var controls = group.querySelector("[data-filter-controls]");
    if (!input || !select) return;
    if (controls) controls.hidden = false;
    var options = Array.from(select.options);
    input.addEventListener("input", function () {
      var term = input.value.trim().toLocaleLowerCase();
      var selected = select.value;
      var matches = options.filter(function (option) {
        return !option.value || option.textContent.toLocaleLowerCase().indexOf(term) !== -1;
      });
      select.replaceChildren.apply(select, matches);
      select.value = matches.some(function (option) { return option.value === selected; }) ? selected : "";
      if (status) status.textContent = matches.length > 1
        ? (matches.length - 1) + (matches.length === 2 ? " matching account" : " matching accounts") : "No matching accounts. Clear or change the search.";
    });
  });

  var pageError = document.querySelector(".alert.error");
  if (pageError) { pageError.setAttribute("tabindex", "-1"); pageError.focus(); }

  // All forms share help associations, validation visibility, and secret controls.
  document.querySelectorAll(".field").forEach(function (field, index) {
    var hint = field.querySelector(":scope > .hint");
    if (!hint) return;
    hint.id = hint.id || "field-help-" + index;
    field.querySelectorAll("input:not([type=hidden]), select, textarea").forEach(function (control) {
      var ids = (control.getAttribute("aria-describedby") || "").split(" ").filter(Boolean);
      if (ids.indexOf(hint.id) === -1) ids.push(hint.id);
      control.setAttribute("aria-describedby", ids.join(" "));
    });
  });
  document.addEventListener("invalid", function (event) {
    var control = event.target;
    if (control.matches("input, select, textarea") && control.validationMessage) {
      control.id = control.id || "invalid-field-" + Array.from(control.form ? control.form.elements : document.querySelectorAll("input, select, textarea")).indexOf(control);
      var errorId = control.id + "-error";
      var message = document.getElementById(errorId);
      if (!message) {
        message = document.createElement("p"); message.id = errorId; message.className = "field-error";
        control.insertAdjacentElement("afterend", message);
      }
      message.hidden = false; message.textContent = control.validationMessage;
      control.setAttribute("aria-invalid", "true");
      var described = (control.getAttribute("aria-describedby") || "").split(" ").filter(Boolean);
      if (described.indexOf(errorId) === -1) described.push(errorId);
      control.setAttribute("aria-describedby", described.join(" "));
    }
    var parent = event.target.parentElement;
    while (parent) {
      if (parent.tagName === "DETAILS") parent.open = true;
      parent = parent.parentElement;
    }
  }, true);
  document.querySelectorAll("input, select, textarea").forEach(function (control) {
    function clearOldError() {
      control.removeAttribute("aria-invalid");
      var message = document.getElementById(control.id + "-error");
      if (message) message.hidden = true;
    }
    control.addEventListener("input", clearOldError);
    control.addEventListener("change", clearOldError);
  });
  document.querySelectorAll('input[type="password"]').forEach(function (input, index) {
    input.id = input.id || "secret-field-" + index;
    var label = Array.from(input.labels || [])[0];
    var labelCopy = label ? label.cloneNode(true) : null;
    if (labelCopy) labelCopy.querySelectorAll("input, button, select, textarea, .hint, small").forEach(function (node) { node.remove(); });
    var name = labelCopy ? labelCopy.textContent.trim() : (input.getAttribute("aria-label") || "password");
    // Keep the wrapping label's name stable when the Show/Hide button is added.
    if (label && label.contains(input)) input.setAttribute("aria-label", name);
    var wrap = document.createElement("div");
    wrap.className = "secret-input";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn text";
    toggle.textContent = "Show";
    toggle.setAttribute("aria-controls", input.id);
    toggle.setAttribute("aria-pressed", "false");
    toggle.setAttribute("aria-label", "Show " + name);
    toggle.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      toggle.textContent = show ? "Hide" : "Show";
      toggle.setAttribute("aria-pressed", String(show));
      toggle.setAttribute("aria-label", (show ? "Hide " : "Show ") + name);
    });
    wrap.appendChild(toggle);
  });
  document.querySelectorAll(".table-wrap").forEach(function (region) {
    region.tabIndex = 0;
    region.setAttribute("role", "region");
    var card = region.closest(".card");
    var heading = card ? card.querySelector("h2") : null;
    region.setAttribute("aria-label", heading ? heading.textContent.trim() : "Table");
  });
  function markSubmitting(form, submitter) {
    if (form.method.toLowerCase() !== "post" && !form.hasAttribute("data-readiness-check")) return;
    if (submitter && submitter.name) {
      var submitted = document.createElement("input");
      submitted.type = "hidden";
      submitted.name = submitter.name;
      submitted.value = submitter.value;
      form.appendChild(submitted);
    }
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll('button:not([type="button"])').forEach(function (button) {
      button.disabled = true;
      button.textContent = form.hasAttribute("data-readiness-check") ? "Checking…" : "Working…";
    });
  }
  document.addEventListener("submit", function (event) {
    if (!event.defaultPrevented) markSubmitting(event.target, event.submitter);
  });
  window.addEventListener("pageshow", function () {
    document.querySelectorAll('form[aria-busy="true"]').forEach(function (form) {
      form.removeAttribute("aria-busy");
      // Restoring the back/forward cache must restore the original button text.
      window.location.reload();
    });
  });
  var summary = document.querySelector("[data-network-summary]");
  if (summary) {
    var networkForm = summary.closest("form");
    function updateSummary() {
      var auth = networkForm.elements.authentication;
      var security = networkForm.elements.security;
      var inclusion = networkForm.elements.include_by_default.checked ? "Every enrollment profile" : "Separate MDM profile";
      summary.replaceChildren();
      var method = document.createElement("b");
      method.textContent = auth.options[auth.selectedIndex].textContent.split(" — ")[0];
      [method, document.createTextNode(security.value), document.createTextNode(inclusion)].forEach(function (part) {
        var span = document.createElement("span"); span.appendChild(part); summary.appendChild(span);
      });
    }
    updateSummary();
    networkForm.addEventListener("change", updateSummary);
  }

  // Groups that require an email address make the email field required.
  document.querySelectorAll("select[name=group]").forEach(function (select) {
    var input = select.form && select.form.querySelector("[data-email-field]");
    if (!input) return;
    function apply() {
      var option = select.options[select.selectedIndex];
      input.required = !!(option && option.hasAttribute("data-require-email"));
    }
    apply();
    select.addEventListener("change", apply);
  });

  // Generate a random challenge.
  document.querySelectorAll("[data-generate]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById(button.getAttribute("data-generate"));
      var bytes = new Uint8Array(24);
      crypto.getRandomValues(bytes);
      var text = btoa(String.fromCharCode.apply(null, bytes)).replace(/\+/g, "-").replace(/\//g, "_");
      input.value = text;
      input.dispatchEvent(new Event("input"));
      say("Generated a new challenge");
    });
  });

  // Instant search over the certificate table.
  var search = document.querySelector("[data-filter-table]");
  if (search) {
    var table = document.getElementById(search.getAttribute("data-filter-table"));
    var rows = table ? Array.prototype.slice.call(table.querySelectorAll("tbody tr[data-search]")) : [];
    var none = table && table.querySelector("tr.no-match");
    search.addEventListener("input", function () {
      var needle = search.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var hit = !needle || row.getAttribute("data-search").indexOf(needle) !== -1;
        row.hidden = !hit;
        if (hit) shown++;
      });
      if (none) none.hidden = shown !== 0 || rows.length === 0;
    });
  }

  // Keep relative times current.
  function rel(iso) {
    var seconds = (Date.parse(iso) - Date.now()) / 1000, future = seconds >= 0;
    seconds = Math.abs(seconds);
    var units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
    for (var i = 0; i < units.length; i++) {
      if (seconds >= units[i][1]) {
        var n = Math.floor(seconds / units[i][1]), text = n + " " + units[i][0] + (n === 1 ? "" : "s");
        return future ? "in " + text : text + " ago";
      }
    }
    return "now";
  }
  function tick() {
    document.querySelectorAll("[data-rel]").forEach(function (el) { el.textContent = rel(el.getAttribute("data-rel")); });
  }
  setInterval(tick, 30000);
})();
"""
