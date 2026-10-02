"""Stateless iPSK operations using the configured Meraki HA SDK clients.

Credentials remain in Meraki HA; resident attribution and key history remain
in Step CA's MariaDB database. Never persist passphrases here.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import re

ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")


def scope(network_id, ssid_number):
    if not isinstance(network_id, str) or not ID.fullmatch(network_id):
        raise ValueError("Choose a valid Meraki network.")
    if type(ssid_number) is not int or not 0 <= ssid_number <= 14:
        raise ValueError("Choose an SSID number from 0 to 14.")
    return network_id, ssid_number


def key_id(network_id, ssid_number, remote_id):
    scope(network_id, ssid_number)
    if not isinstance(remote_id, str) or not ID.fullmatch(remote_id):
        raise ValueError("Meraki returned an invalid key identifier.")
    return f"{network_id}:{ssid_number}:{remote_id}"


def key_scope(value, network_id="", ssid_number=0):
    if not isinstance(value, str):
        raise ValueError("Choose a valid Wi-Fi key.")
    parts = value.split(":")
    if len(parts) == 3:
        network_id, number, value = parts
        if not number.isdigit():
            raise ValueError("Choose a valid Wi-Fi key.")
        ssid_number = int(number)
    elif len(parts) != 1:
        raise ValueError("Choose a valid Wi-Fi key.")
    scope(network_id, ssid_number)
    if not ID.fullmatch(value):
        raise ValueError("Choose a valid Wi-Fi key.")
    return network_id, ssid_number, value


def normalize(key, network_id, ssid):
    expires = key.get("expiresAt")
    status = "active"
    if expires:
        try:
            when = dt.datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if when.tzinfo is None:
                raise ValueError
            if when <= dt.datetime.now(dt.timezone.utc):
                status = "expired"
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Meraki returned an invalid key expiry.") from None
    return {"id": key_id(network_id, ssid["number"], str(key.get("id") or "")),
            "remote_id": str(key["id"]), "network_id": network_id,
            "ssid_number": ssid["number"], "ssid_name": ssid["name"],
            "name": str(key.get("name") or ""), "status": status,
            "expires_at": expires, "group_policy_id": key.get("groupPolicyId")}


class MerakiIpsk:
    """Resolve every network to exactly one authenticated organization client."""

    def __init__(self, clients):
        self.clients = clients

    async def networks(self):
        result = {}
        for client in self.clients:
            await client.async_ensure_token_valid()
            rows = await client.dashboard.organizations.getOrganizationNetworks(
                client.organization_id, total_pages="all")
            for row in rows:
                if "wireless" not in row.get("productTypes", []):
                    continue
                ident = str(row["id"])
                if ident in result and result[ident][0] is not client:
                    raise ValueError("This network is configured in multiple Meraki integrations. Remove the duplicate connection.")
                result[ident] = (client, row)
        return result

    async def target(self, network_id):
        candidates = await self.networks()
        if network_id not in candidates:
            raise ValueError("This wireless network is unavailable in Meraki HA.")
        return candidates[network_id][0]

    async def options(self, network_id=""):
        candidates = await self.networks()
        result = {"networks": [{"id": ident, "name": row.get("name", ident)}
                               for ident, (_, row) in candidates.items()],
                  "ssids": [], "group_policies": [], "network_id": network_id}
        if not network_id:
            return result
        if network_id not in candidates:
            raise ValueError("This wireless network is unavailable in Meraki HA.")
        dashboard = candidates[network_id][0].dashboard
        ssids, policies = await asyncio.gather(
            dashboard.wireless.getNetworkWirelessSsids(network_id),
            dashboard.networks.getNetworkGroupPolicies(network_id))
        result["ssids"] = [{"number": s["number"], "name": s["name"], "network_id": network_id}
                           for s in ssids if s.get("enabled") and s.get("authMode") == "ipsk-without-radius"]
        result["group_policies"] = [{"id": str(p["groupPolicyId"]), "name": p["name"], "network_id": network_id}
                                    for p in policies]
        return result

    async def ssid(self, client, network_id, number, creating=False):
        row = await client.dashboard.wireless.getNetworkWirelessSsid(network_id, number)
        if creating and (not row.get("enabled") or row.get("authMode") != "ipsk-without-radius"):
            raise ValueError("Use an enabled SSID with Identity PSK without RADIUS.")
        if not row.get("name") or row.get("number") != number:
            raise ValueError("Meraki returned inconsistent SSID details.")
        return row

    async def list(self, scopes):
        if not isinstance(scopes, list) or len(scopes) > 50:
            raise ValueError("Choose at most 50 Wi-Fi scopes.")
        candidates = await self.networks()
        result = []
        for item in scopes:
            network_id, number = scope(item.get("network_id"), item.get("ssid_number"))
            if network_id not in candidates:
                raise ValueError("A saved wireless network is unavailable in Meraki HA.")
            client = candidates[network_id][0]
            ssid = await self.ssid(client, network_id, number)
            keys = await client.dashboard.wireless.getNetworkWirelessSsidIdentityPsks(network_id, number)
            result.extend(normalize(k, network_id, ssid) for k in keys)
        return result

    async def create(self, msg):
        network_id, number = scope(msg.get("network_id"), msg.get("ssid_number"))
        name, policy = msg.get("name"), msg.get("group_policy_id")
        if not isinstance(name, str) or not name or len(name) > 100 or not name.isprintable():
            raise ValueError("Enter a key name of 1 to 100 printable characters.")
        hours = msg.get("duration_hours", 0)
        if type(hours) is not int or not 0 <= hours <= 87600:
            raise ValueError("Choose a duration between 0 and 87,600 hours.")
        password = msg.get("passphrase", "")
        if not isinstance(password, str) or password and not (
                8 <= len(password) <= 63 and password.isascii() and password.isprintable()
                or re.fullmatch(r"[0-9a-fA-F]{64}", password)):
            raise ValueError("Enter a valid Wi-Fi passphrase.")
        if not isinstance(policy, str) or not policy:
            raise ValueError("Choose the Meraki group policy for this key.")
        client = await self.target(network_id)
        ssid = await self.ssid(client, network_id, number, creating=True)
        policies = await client.dashboard.networks.getNetworkGroupPolicies(network_id)
        if not any(str(p.get("groupPolicyId")) == policy for p in policies):
            raise ValueError("Choose a group policy belonging to this network.")
        args = {"name": name, "groupPolicyId": policy}
        if password:
            args["passphrase"] = password
        if hours:
            args["expiresAt"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).isoformat()
        key = await client.dashboard.wireless.createNetworkWirelessSsidIdentityPsk(network_id, number, **args)
        try:
            result = normalize(key, network_id, ssid)
            result["passphrase"] = key.get("passphrase") or ""
            return result
        except Exception:
            # If the response is malformed but includes an ID, do not leave a
            # provisioned key behind when the portal cannot record it.
            if isinstance(key, dict) and key.get("id"):
                await client.dashboard.wireless.deleteNetworkWirelessSsidIdentityPsk(network_id, number, str(key["id"]))
            raise

    async def key(self, action, ident, network_id="", ssid_number=0):
        network_id, number, remote_id = key_scope(ident, network_id, ssid_number)
        client = await self.target(network_id)
        wireless = client.dashboard.wireless
        if action == "delete":
            await wireless.deleteNetworkWirelessSsidIdentityPsk(network_id, number, remote_id)
            return {"id": ident, "status": "deleted"}
        if action == "revoke":
            # Dashboard has no revoked flag: expire the key now. Step CA records
            # the administrator's revoked state in its own MariaDB history.
            await wireless.updateNetworkWirelessSsidIdentityPsk(network_id, number, remote_id,
                expiresAt=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat())
            return {"id": ident, "status": "revoked"}
        ssid = await self.ssid(client, network_id, number)
        key = await wireless.getNetworkWirelessSsidIdentityPsk(network_id, number, remote_id)
        result = normalize(key, network_id, ssid)
        if action == "reveal_passphrase":
            if result["status"] != "active":
                raise ValueError("Only an active Wi-Fi key can be shared.")
            result = {"passphrase": key.get("passphrase") or ""}
        return result
