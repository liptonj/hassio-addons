"""API routers for Meraki WPN Portal."""

from app.api import admin, auth, devices, ipsk, registration

__all__ = [
    "auth",
    "registration",
    "ipsk",
    "devices",
    "admin",
]
