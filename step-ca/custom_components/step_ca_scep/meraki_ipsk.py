"""Stateless iPSK operations using the configured Meraki HA SDK clients.

Credentials remain in Meraki HA; resident attribution and key history remain
in Step CA's MariaDB database. Never persist passphrases here.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import re
from urllib.parse import urlsplit

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
            raise ValueError("This wireless network is unavailable in the Meraki connection.")
        return candidates[network_id][0]

    async def options(self, network_id=""):
        candidates = await self.networks()
        result = {"networks": [{"id": ident, "name": row.get("name", ident),
                                "organization_id": str(client.organization_id)}
                               for ident, (client, row) in candidates.items()],
                  "ssids": [], "active_ssids": [], "group_policies": [], "network_id": network_id}
        if not network_id:
            return result
        if network_id not in candidates:
            raise ValueError("This wireless network is unavailable in the Meraki connection.")
        dashboard = candidates[network_id][0].dashboard
        ssids, policies = await asyncio.gather(
            dashboard.wireless.getNetworkWirelessSsids(network_id),
            dashboard.networks.getNetworkGroupPolicies(network_id))
        result["ssids"] = [{"number": s["number"], "name": s["name"], "network_id": network_id}
                           for s in ssids if s.get("enabled") and s.get("authMode") == "ipsk-without-radius"]
        result["active_ssids"] = [{"number": s["number"], "name": s["name"], "network_id": network_id,
                                   "auth_mode": s.get("authMode", "unknown"),
                                   "splash_page": s.get("splashPage", "unknown"),
                                   "ip_assignment_mode": s.get("ipAssignmentMode", "unknown")}
                                  for s in ssids if s.get("enabled")]
        result["group_policies"] = [{"id": str(p["groupPolicyId"]), "name": p["name"], "network_id": network_id}
                                    for p in policies]
        return result

    @staticmethod
    def revision(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    async def configuration_plan(self, msg):
        """Read current settings and build an allowlisted, secret-free SSID change."""
        network, number = scope(msg.get("network_id"), msg.get("ssid_number"))
        client = await self.target(network)
        wireless = client.dashboard.wireless
        current = await self.ssid(client, network, number)
        if not current.get("enabled"):
            raise ValueError("Choose an enabled SSID. Enable unused SSID slots in Dashboard first.")
        role = msg.get("portal_type", "external")
        mode = msg.get("auth_mode", "preserve")
        if role not in ("resident", "external", "guest", "none") or mode not in ("preserve", "ipsk-without-radius", "ipsk-with-nac", "8021x-nac"):
            raise ValueError("Choose a supported portal and authentication mode.")
        if role == "resident" and mode == "ipsk-with-nac":
            raise ValueError("The Step CA resident issuer uses iPSK without RADIUS. Access Manager client keys are managed separately.")
        no_portal = role in ("guest", "none")
        changes = {"splashPage": "None" if no_portal else "Click-through splash page"}
        if mode != "preserve":
            changes["authMode"] = mode
            changes["wpaEncryptionMode"] = "WPA2 only"
            changes["dot11r"] = {"enabled": False}
        effective_mode = changes.get("authMode", current.get("authMode"))
        if role == "resident" and effective_mode != "ipsk-without-radius":
            raise ValueError("Configure the resident SSID for iPSK without RADIUS.")
        manual = []
        if msg.get("prepare_wpn", False):
            if effective_mode != "ipsk-without-radius":
                raise ValueError("This WPN preparation flow requires iPSK without RADIUS. Use Dashboard for RADIUS-based WPN.")
            changes["ipAssignmentMode"] = "Bridge mode"
            changes["wpaEncryptionMode"] = "WPA2 only"
            changes["dot11r"] = {"enabled": False}
            manual.append("Enable WPN in Meraki Dashboard after creating at least one iPSK; verify supported AP models and firmware. The public API has no WPN enable switch.")
        if "vlan_id" in msg and msg["vlan_id"] is not None:
            vlan = msg["vlan_id"]
            if type(vlan) is not int or not 1 <= vlan <= 4094:
                raise ValueError("Choose a VLAN ID from 1 to 4094, or leave it blank to retain the current VLAN.")
            changes.update(ipAssignmentMode="Bridge mode", useVlanTagging=True, defaultVlanId=vlan)
        splash = await wireless.getNetworkWirelessSsidSplashSettings(network, number)
        splash_changes = {"useSplashUrl": not no_portal}
        if not no_portal:
            public_url = str(msg.get("portal_url") or "")
            try:
                parsed = urlsplit(public_url)
                port = parsed.port
            except ValueError:
                raise ValueError("Enter a public HTTPS portal URL.") from None
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.fragment or port is not None and not 1 <= port <= 65535
                    or len(public_url) > 2048 or any(ord(c) < 33 for c in public_url)):
                raise ValueError("Enter a public HTTPS portal URL without credentials or a fragment.")
            splash_changes["splashUrl"] = public_url
            ranges = msg.get("walled_garden_ranges", [])
            if not isinstance(ranges, list) or len(ranges) > 100 or any(not isinstance(r, str) or len(r) > 253 or not r or any(c.isspace() for c in r) for r in ranges):
                raise ValueError("Enter at most 100 walled-garden hosts or CIDR ranges, one per line.")
            # Preserve existing entries and add the portal host. The admin can
            # include the identity provider's documented required resources.
            existing = current.get("walledGardenRanges") or []
            combined = list(dict.fromkeys([*existing, parsed.hostname, *ranges]))
            if len(combined) > 100:
                raise ValueError("The combined walled garden exceeds 100 entries. Edit it in Dashboard first.")
            changes.update(walledGardenEnabled=True, walledGardenRanges=combined)
        if mode in ("ipsk-with-nac", "8021x-nac"):
            await self.access_manager(network)
            if mode == "8021x-nac":
                manual.append("For EAP-TLS, Access Manager must trust Step CA's enabled intermediate/root chain as a trusted anchor and have matching certificate rules. Keep existing working Access Manager profiles. Replace a device profile only if its SSID, authentication method or trust settings change. SSID configuration alone does not establish certificate trust.")
            else:
                manual.append("Configure matching Access Manager rules and client groups. Per-client iPSK needs its organization feature enabled and a rule using Client iPSK only or Client iPSK with fallback.")
        before = {key: current.get(key) for key in changes}
        before["splash_settings"] = {key: splash.get(key) for key in splash_changes}
        # Include managed values in the revision; secrets and unrelated SSID
        # settings are never copied into the preview or update body.
        return {"network_id": network, "ssid_number": number, "ssid_name": current["name"],
                "organization_id": str(client.organization_id), "revision": self.revision({"organization": str(client.organization_id), "network": network, "ssid": number, "before": before}),
                "before": before, "ssid_changes": changes, "splash_changes": splash_changes,
                "manual_steps": manual}

    async def configure(self, msg):
        plan = await self.configuration_plan(msg)
        if msg.get("expected_revision") != plan["revision"]:
            raise ValueError("Meraki settings changed since the preview. Review a fresh preview before applying.")
        client = await self.target(plan["network_id"])
        wireless = client.dashboard.wireless
        done = []
        for name, method, payload in (
                ("SSID authentication and network settings", wireless.updateNetworkWirelessSsid, plan["ssid_changes"]),
                ("Captive portal URL", wireless.updateNetworkWirelessSsidSplashSettings, plan["splash_changes"])):
            try:
                await method(plan["network_id"], plan["ssid_number"], **payload)
                done.append(name)
            except Exception:
                return {"complete": False, "applied": done, "failed": name,
                        "manual_steps": plan["manual_steps"], "message": "Meraki did not confirm this step. Check Dashboard before retrying; earlier steps may have applied."}
        try:
            verified = await self.configuration_plan(msg)
            def matches_value(actual, desired):
                if isinstance(desired, dict):
                    return isinstance(actual, dict) and all(matches_value(actual.get(k), v) for k, v in desired.items())
                return actual == desired
            matches = all(matches_value(verified["before"].get(k), v) for k, v in plan["ssid_changes"].items())
            matches = matches and all(verified["before"]["splash_settings"].get(k) == v for k, v in plan["splash_changes"].items())
        except Exception:
            matches = False
        return {"complete": matches, "applied": done, "failed": "" if matches else "Read-back verification",
                "manual_steps": plan["manual_steps"], "message": "Settings applied and read back." if matches else "Writes returned, but the settings could not be verified. Check Dashboard before retrying."}

    @staticmethod
    async def nac_call(client, method, resource, body=None, params=None):
        """Use the authenticated SDK transport for documented beta NAC paths.

        The stable SDK does not generate NAC methods. Reusing its transport
        preserves the integration's OAuth refresh, API region and retry rules.
        """
        metadata = {"tags": ["nac", "configure"], "operation": "stepCaAccessManager"}
        session = client.dashboard._session
        if method == "GET":
            return await session.get(metadata, resource, params or {})
        return await getattr(session, method.lower())(metadata, resource, body or {})

    @staticmethod
    def nac_items(value):
        if isinstance(value, dict):
            rows = value.get("items") or []
            meta = value.get("meta") or {}
            if meta.get("filteredCount", meta.get("totalCount", len(rows))) > len(rows):
                raise ValueError("This Access Manager result has more pages. Narrow the search or use Dashboard.")
            return rows
        if isinstance(value, list):
            if len(value) == 1 and isinstance(value[0], dict) and "items" in value[0]:
                return MerakiIpsk.nac_items(value[0])
            return value
        raise ValueError("Access Manager returned an unexpected response.")

    async def access_manager(self, network_id):
        client = await self.target(network_id)
        org = str(client.organization_id)
        if not ID.fullmatch(org):
            raise ValueError("Meraki returned an invalid organization identifier.")
        policies = await self.nac_call(client, "GET", f"/organizations/{org}/nac/authorization/policies")
        groups = await self.nac_call(client, "GET", f"/organizations/{org}/nac/clients/groups", params={"perPage": 1000})
        # Policy passphrases are masked today, but never rely on that to keep
        # secrets out of Home Assistant, the panel or logs.
        safe_policies = []
        for policy in self.nac_items(policies):
            safe_policies.append({"id": str(policy.get("policyId") or ""), "name": str(policy.get("name") or ""),
                                  "version": str(policy.get("version") or ""),
                                  "enabled": bool(policy.get("enabled")),
                                  "rules": [{"name": str(r.get("name") or ""), "enabled": bool(r.get("enabled")),
                                             "result": str(r.get("authorizationProfile", {}).get("result") or ""),
                                             "ipsk_mode": str(r.get("authorizationProfile", {}).get("ipsk", {}).get("mode") or "rule key")}
                                            for r in policy.get("rules") or []]})
        return {"organization_id": org, "policies": safe_policies,
                "groups": [{"id": str(g.get("id") or ""), "name": str(g.get("name") or "")}
                           for g in self.nac_items(groups)]}

    async def client_key_plan(self, msg):
        network, number = scope(msg.get("network_id"), msg.get("ssid_number"))
        client = await self.target(network)
        ssid = await self.ssid(client, network, number)
        if not ssid.get("enabled") or ssid.get("authMode") != "ipsk-with-nac":
            raise ValueError("Choose an enabled SSID configured for Access Manager iPSK (ipsk-with-nac).")
        mac = str(msg.get("mac") or "").lower().replace("-", ":")
        if not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", mac) or int(mac[:2], 16) & 3 or mac == "00:00:00:00:00:00":
            raise ValueError("Enter the device's unicast hardware MAC address; turn private addressing off first.")
        password = msg.get("passphrase", "")
        if not isinstance(password, str) or not 8 <= len(password) <= 63 or not password.isascii() or not password.isprintable():
            raise ValueError("Enter a client iPSK of 8 to 63 printable ASCII characters.")
        owner = str(msg.get("owner") or "").strip()
        if not owner or len(owner) > 100 or not owner.isprintable():
            raise ValueError("Enter an owner name of 1 to 100 printable characters.")
        info = await self.access_manager(network)
        group = next((g for g in info["groups"] if g["id"] == msg.get("group_id")), None)
        if group is None:
            raise ValueError("Choose an available Access Manager client group.")
        if not any(p["enabled"] and any(r["enabled"] and r["result"] == "PERMIT" and r["ipsk_mode"] in ("clientIpskOnly", "clientIpskWithDefaultFallback") for r in p["rules"]) for p in info["policies"]):
            raise ValueError("Configure an enabled Access Manager PERMIT rule using per-client iPSK before assigning client keys.")
        org = info["organization_id"]
        found = await self.nac_call(client, "GET", f"/organizations/{org}/nac/clients", params={"search": mac, "perPage": 1000})
        matches = [r for r in self.nac_items(found) if str(r.get("mac") or "").lower().replace("-", ":") == mac]
        if len(matches) > 1:
            raise ValueError("Multiple Access Manager clients have this MAC. Resolve them in Dashboard first.")
        existing = matches[0] if matches else None
        if existing and not ID.fullmatch(str(existing.get("id") or "")):
            raise ValueError("Access Manager returned an invalid client identifier.")
        revision = self.revision({"organization": org, "network": network, "ssid": ssid,
                                  "client": existing, "group": group, "policies": info["policies"]})
        return {"organization_id": org, "network_id": network, "ssid_number": number, "ssid_name": ssid["name"],
                "mac": mac, "owner": owner, "group": group, "client_id": str(existing["id"]) if existing else "",
                "operation": "Update existing client" if existing else "Create client", "revision": revision,
                "manual_steps": ["The organization must have per-client iPSK enabled. Confirm that the selected client group and SSID match the intended Access Manager rule. This client key applies across the organization and has no automatic expiry."]}

    async def assign_client_key(self, msg):
        plan = await self.client_key_plan(msg)
        if msg.get("expected_revision") != plan["revision"]:
            raise ValueError("Access Manager changed since the preview. Review a fresh preview before applying.")
        client = await self.target(plan["network_id"])
        body = {"mac": plan["mac"], "owner": plan["owner"], "ipsk": msg["passphrase"]}
        base = f'/organizations/{plan["organization_id"]}/nac/clients'
        group = {"value": plan["group"]["id"], "display": plan["group"]["name"]}
        if plan["client_id"]:
            body["groups"] = {"addList": [group]}
            await self.nac_call(client, "PUT", base + "/" + plan["client_id"], body)
        else:
            body.update(type="BYOD", groups=[group])
            await self.nac_call(client, "POST", base, body)
        # Responses may contain a key; return only explicit non-secret fields.
        return {"mac": plan["mac"], "organization_id": plan["organization_id"],
                "message": "Access Manager accepted the client iPSK. Test association on the device; rule matching is not verified by this write."}

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
                raise ValueError("A saved wireless network is unavailable in the Meraki connection.")
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
