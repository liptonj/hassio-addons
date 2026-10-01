"""Serve the Step CA SCEP add-on through Home Assistant's own HTTP port.

SCEP clients cannot authenticate to Home Assistant, so add-on ingress is not
usable. Instead this integration registers unauthenticated views that forward
only SCEP traffic, the public root certificate, the CRL, and one-time device
enrollment pages to the add-on on the internal Supervisor network.
"""

from __future__ import annotations

import logging
from http import HTTPStatus

import aiohttp
from aiohttp import web
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENROLL_PORT,
    CONF_ROOT_PEM,
    DOMAIN,
    ENROLL_RESPONSE_HEADERS,
    ENROLL_SUBPATH_RE,
    ENROLL_TOKEN_RE,
    MAX_BODY_BYTES,
    MAX_DEVICE_BYTES,
    MAX_FORM_BYTES,
    PROVISIONER_RE,
    UPSTREAM_TIMEOUT,
    URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

_VIEWS_REGISTERED = f"{DOMAIN}_views_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Point the SCEP views at the add-on described by this entry."""
    hass.data[DOMAIN] = entry.data

    # Views cannot be unregistered from aiohttp, so register them once and let
    # them read the current target from hass.data on each request.
    if not hass.data.get(_VIEWS_REGISTERED):
        hass.http.register_view(ScepView())
        hass.http.register_view(RootCertificateView())
        hass.http.register_view(CrlView())
        hass.http.register_view(EnrollView())
        hass.data[_VIEWS_REGISTERED] = True

    _LOGGER.info(
        "SCEP available at %s/scep/<provisioner>, forwarding to %s:%s",
        URL_BASE,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop forwarding; the views answer 503 until an entry is set up again."""
    hass.data.pop(DOMAIN, None)
    return True


class ScepView(HomeAssistantView):
    """Forward SCEP GET and POST operations to the add-on."""

    url = URL_BASE + "/scep/{provisioner}"
    name = f"api:{DOMAIN}:scep"
    requires_auth = False

    async def get(self, request: web.Request, provisioner: str) -> web.Response:
        """Handle GetCACaps, GetCACert and GET PKIOperation."""
        return await self._forward(request, provisioner, None)

    async def post(self, request: web.Request, provisioner: str) -> web.Response:
        """Handle POST PKIOperation."""
        if (request.content_length or 0) > MAX_BODY_BYTES:
            return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        body = await request.content.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        return await self._forward(request, provisioner, body)

    async def _forward(
        self, request: web.Request, provisioner: str, body: bytes | None
    ) -> web.Response:
        if not PROVISIONER_RE.fullmatch(provisioner):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        hass: HomeAssistant = request.app["hass"]
        target = hass.data.get(DOMAIN)
        if target is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        # Pass the query string through untouched: GET PKIOperation carries a
        # base64 message whose '+' and '/' must not be re-encoded.
        upstream = URL.build(
            scheme="http",
            host=target[CONF_HOST],
            port=target[CONF_PORT],
            path=f"/scep/{provisioner}",
            query_string=request.rel_url.raw_query_string,
            encoded=True,
        )
        headers = {}
        if body is not None and request.content_type:
            headers["Content-Type"] = request.content_type

        session = async_get_clientsession(hass)
        try:
            async with session.request(
                request.method,
                upstream,
                data=body,
                headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=UPSTREAM_TIMEOUT),
            ) as resp:
                payload = await resp.read()
                response_headers = {}
                if content_type := resp.headers.get("Content-Type"):
                    response_headers["Content-Type"] = content_type
                return web.Response(
                    body=payload, status=resp.status, headers=response_headers
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("SCEP request to the add-on failed: %s", err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)


class RootCertificateView(HomeAssistantView):
    """Serve the CA root certificate so clients and servers can trust it."""

    url = URL_BASE + "/roots.pem"
    name = f"api:{DOMAIN}:roots"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the root certificate reported by the add-on."""
        hass: HomeAssistant = request.app["hass"]
        target = hass.data.get(DOMAIN)
        if target is None or not target.get(CONF_ROOT_PEM):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.Response(
            text=target[CONF_ROOT_PEM], content_type="application/x-pem-file"
        )


class CrlView(HomeAssistantView):
    """Serve the certificate revocation list published by step-ca."""

    url = URL_BASE + "/crl"
    name = f"api:{DOMAIN}:crl"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the CRL as DER, or as PEM when requested with ?pem."""
        hass: HomeAssistant = request.app["hass"]
        target = hass.data.get(DOMAIN)
        if target is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)
        upstream = URL.build(
            scheme="http",
            host=target[CONF_HOST],
            port=target[CONF_PORT],
            path="/crl",
            query_string="pem" if "pem" in request.query else "",
        )
        session = async_get_clientsession(hass)
        try:
            async with session.get(
                upstream,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=UPSTREAM_TIMEOUT),
            ) as resp:
                headers = {
                    key: value
                    for key in ("Content-Type", "Content-Disposition")
                    if (value := resp.headers.get(key))
                }
                return web.Response(
                    body=await resp.read(), status=resp.status, headers=headers
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("CRL request to the add-on failed: %s", err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)


class EnrollView(HomeAssistantView):
    """Forward one-time device enrollment pages to the add-on.

    The unguessable token in the path is the credential; the add-on checks it
    and only accepts connections from Home Assistant.
    """

    url = URL_BASE + "/enroll/{token}"
    extra_urls = [URL_BASE + "/enroll/{token}/{subpath:.+}"]
    name = f"api:{DOMAIN}:enroll"
    requires_auth = False

    async def get(
        self, request: web.Request, token: str, subpath: str = ""
    ) -> web.Response:
        """Show the enrollment form or download an issued file."""
        return await self._forward(request, token, subpath, None)

    async def post(
        self, request: web.Request, token: str, subpath: str = ""
    ) -> web.Response:
        """Submit the enrollment form, or an Apple device's signed attributes."""
        if subpath not in ("", "device"):
            return web.Response(status=HTTPStatus.METHOD_NOT_ALLOWED)
        limit = MAX_DEVICE_BYTES if subpath else MAX_FORM_BYTES
        if (request.content_length or 0) > limit:
            return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        body = await request.content.read(limit + 1)
        if len(body) > limit:
            return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        return await self._forward(request, token, subpath, body)

    async def _forward(
        self, request: web.Request, token: str, subpath: str, body: bytes | None
    ) -> web.Response:
        if not ENROLL_TOKEN_RE.fullmatch(token) or (
            subpath and not ENROLL_SUBPATH_RE.fullmatch(subpath)
        ):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        hass: HomeAssistant = request.app["hass"]
        target = hass.data.get(DOMAIN)
        if target is None or not target.get(CONF_ENROLL_PORT):
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        path = f"/enroll/{token}" + (f"/{subpath}" if subpath else "")
        upstream = URL.build(
            scheme="http",
            host=target[CONF_HOST],
            port=target[CONF_ENROLL_PORT],
            path=path,
        )
        headers = {}
        if user_agent := request.headers.get("User-Agent"):
            headers["User-Agent"] = user_agent
        if body is not None:
            headers["Content-Type"] = (
                "application/pkcs7-signature"
                if subpath
                else "application/x-www-form-urlencoded"
            )

        session = async_get_clientsession(hass)
        try:
            async with session.request(
                request.method,
                upstream,
                data=body,
                headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=UPSTREAM_TIMEOUT * 3),
            ) as resp:
                if subpath == "device" and resp.status >= 400:
                    _LOGGER.warning(
                        "The add-on refused an Apple device's enrollment reply (HTTP %s); "
                        "see the add-on log",
                        resp.status,
                    )
                response_headers = {
                    key: value
                    for key in ENROLL_RESPONSE_HEADERS
                    if (value := resp.headers.get(key))
                }
                return web.Response(
                    body=await resp.read(), status=resp.status, headers=response_headers
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Enrollment request to the add-on failed: %s", err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
