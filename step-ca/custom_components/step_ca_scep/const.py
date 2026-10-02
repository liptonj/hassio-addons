"""Constants for the Step CA SCEP integration."""

import re

DOMAIN = "step_ca_scep"

CONF_ROOT_PEM = "root_pem"
CONF_ENROLL_PORT = "enroll_port"
CONF_PORTAL_PORT = "portal_port"

URL_BASE = f"/api/{DOMAIN}"

# Provisioner names allowed by the add-on schema.
PROVISIONER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# SCEP PKIOperation messages are a few kilobytes; cap what we forward.
MAX_BODY_BYTES = 256 * 1024
UPSTREAM_TIMEOUT = 30

# One-time enrollment links: /enroll/<token>[/file/<id> | /root_ca.crt]
ENROLL_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
ENROLL_SUBPATH_RE = re.compile(r"^(file/[A-Za-z0-9_-]{20,64}|root_ca\.crt|device)$")
MAX_FORM_BYTES = 4096
# Signed device attributes (serial number) an Apple device posts to the profile service.
MAX_DEVICE_BYTES = 65536
# Headers passed back from the add-on's enrollment pages.
ENROLL_RESPONSE_HEADERS = (
    "Content-Type",
    "Content-Disposition",
    "Cache-Control",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Location",
)
