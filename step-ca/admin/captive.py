"""Meraki captive portal context and conservative device-address checks."""

import re
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class DeviceAddressError(ValueError):
    """The device cannot register using the address in the splash redirect."""


def hardware_mac(value):
    """Reject invalid, multicast and locally administered (often private) MACs.

    The local bit is a conservative policy signal, not proof of randomization.
    This does not authenticate unsigned Meraki redirect parameters.
    """
    value = str(value or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{12}", value):
        raw = value
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        raw = value.replace(":", "")
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}", value):
        raw = value.replace("-", "")
    elif re.fullmatch(r"(?:[0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}", value):
        raw = value.replace(".", "")
    else:
        raise DeviceAddressError("Reconnect to the setup Wi-Fi so the portal can read your device address.")
    first = int(raw[:2], 16)
    if raw == "000000000000" or first & 1:
        raise DeviceAddressError("This device address is invalid. Reconnect to the setup Wi-Fi and try again.")
    if first & 2:
        raise DeviceAddressError("Turn off Private Wi-Fi Address or Randomized MAC for this network, then reconnect.")
    return ":".join(raw[i:i + 2].lower() for i in range(0, 12, 2))


def grant_url(base, continuation=""):
    """Accept only Meraki's HTTPS click-through grant endpoint, without fetching it."""
    try:
        parsed = urlsplit(base)
        host = parsed.hostname or ""
        valid = (
            parsed.scheme == "https" and host.endswith(".network-auth.com")
            and re.fullmatch(r"[a-zA-Z0-9.-]+", host)
            and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and parsed.path.rstrip("/") == "/splash/grant" and not parsed.fragment
            and len(base) <= 2048 and not any(ord(c) < 33 for c in base)
        )
        if not valid:
            raise ValueError
        query = [(k, v) for k, v in parse_qsl(parsed.query)
                 if k not in ("continue_url", "duration")]
        if continuation:
            target = urlsplit(continuation)
            if (target.scheme not in ("http", "https") or not target.hostname
                    or target.username or target.password or len(continuation) > 2048
                    or any(ord(c) < 33 for c in continuation)):
                raise ValueError
            query.append(("continue_url", continuation))
        # The bootstrap key is only for setup; grant a short completion window.
        query.append(("duration", "300"))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    except (ValueError, TypeError):
        raise ValueError("Reconnect to the setup Wi-Fi to open a fresh captive portal.") from None


@dataclass(frozen=True)
class CaptiveContext:
    mac: str
    grant: str
    expires_at: float


class CaptiveSessions:
    """Keep the captured MAC on the server, bound to a short-lived browser token."""

    def __init__(self, ttl=900, capacity=1000, clock=time.monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self, mac, base_grant_url, continuation=""):
        mac = hardware_mac(mac)
        grant = grant_url(base_grant_url, continuation)
        with self._lock:
            now = self.clock()
            self._sessions = {k: v for k, v in self._sessions.items() if v.expires_at > now}
            if len(self._sessions) >= self.capacity:
                raise RuntimeError("The portal is busy. Reconnect and try again in a few minutes.")
            token = secrets.token_urlsafe(32)
            self._sessions[token] = CaptiveContext(mac, grant, now + self.ttl)
            return token

    def get(self, token):
        with self._lock:
            context = self._sessions.get(token)
            if context and context.expires_at > self.clock():
                return context
            self._sessions.pop(token, None)
            return None

    def discard(self, token):
        with self._lock:
            self._sessions.pop(token, None)
