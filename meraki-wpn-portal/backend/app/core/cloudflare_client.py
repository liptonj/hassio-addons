"""Cloudflare Zero Trust tunnel client for HTTP traffic tunneling.

Uses Cloudflare API to manage tunnels and ingress rules for the portal.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareClient:
    """Client for Cloudflare Zero Trust API."""

    def __init__(self, api_token: str, account_id: str | None = None):
        """Initialize Cloudflare client.

        Parameters
        ----------
        api_token : str
            Cloudflare API token with tunnel permissions
        account_id : str | None
            Optional account ID for account-scoped tokens
        """
        self.api_token = api_token
        self._account_id: str | None = account_id
        self._client = httpx.AsyncClient(
            base_url=CLOUDFLARE_API_BASE,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict:
        """Make an API request.

        Parameters
        ----------
        method : str
            HTTP method
        path : str
            API path
        **kwargs
            Additional request parameters

        Returns
        -------
        dict
            API response

        Raises
        ------
        Exception
            If the API returns an error
        """
        response = await self._client.request(method, path, **kwargs)
        data = response.json()

        if not data.get("success", False):
            errors = data.get("errors", [])
            error_msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise Exception(f"Cloudflare API error: {error_msg}")

        return data.get("result", {})

    async def verify_token(self) -> dict:
        """Verify the API token is valid.

        Tries account-scoped endpoint first if account_id is set,
        then falls back to user-scoped endpoint.

        Returns
        -------
        dict
            Token verification result with account info
        """
        # Try account-scoped verification first if we have an account ID
        if self._account_id:
            try:
                result = await self._request(
                    "GET",
                    f"/accounts/{self._account_id}/tokens/verify"
                )
                logger.info("Cloudflare API token verified (account-scoped)")
                return result
            except Exception as e:
                logger.debug(f"Account-scoped verify failed: {e}, trying user-scoped")

        # Fall back to user-scoped verification
        result = await self._request("GET", "/user/tokens/verify")
        logger.info("Cloudflare API token verified (user-scoped)")
        return result

    async def get_accounts(self) -> list[dict]:
        """Get all accounts accessible with this token.

        Returns
        -------
        list[dict]
            List of accounts
        """
        result = await self._request("GET", "/accounts")
        return result if isinstance(result, list) else [result]

    async def get_account_id(self) -> str:
        """Get the first account ID for this token.

        Returns
        -------
        str
            Account ID
        """
        if self._account_id:
            return self._account_id

        accounts = await self.get_accounts()
        if not accounts:
            raise Exception("No Cloudflare accounts found for this token")

        self._account_id = accounts[0]["id"]
        return self._account_id

    async def list_tunnels(self, account_id: str | None = None) -> list[dict]:
        """List all Cloudflare tunnels.

        Parameters
        ----------
        account_id : str | None
            Account ID (uses default if not provided)

        Returns
        -------
        list[dict]
            List of tunnels with id, name, status
        """
        if not account_id:
            account_id = await self.get_account_id()

        result = await self._request(
            "GET",
            f"/accounts/{account_id}/cfd_tunnel",
        )

        tunnels = result if isinstance(result, list) else []

        return [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
                "connections": len(t.get("connections", [])),
            }
            for t in tunnels
        ]

    async def get_tunnel(
        self,
        tunnel_id: str,
        account_id: str | None = None,
    ) -> dict:
        """Get tunnel details.

        Parameters
        ----------
        tunnel_id : str
            Tunnel ID
        account_id : str | None
            Account ID

        Returns
        -------
        dict
            Tunnel details
        """
        if not account_id:
            account_id = await self.get_account_id()

        return await self._request(
            "GET",
            f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}",
        )

    async def get_tunnel_config(
        self,
        tunnel_id: str,
        account_id: str | None = None,
    ) -> dict:
        """Get tunnel configuration including ingress rules.

        Parameters
        ----------
        tunnel_id : str
            Tunnel ID
        account_id : str | None
            Account ID

        Returns
        -------
        dict
            Tunnel configuration
        """
        if not account_id:
            account_id = await self.get_account_id()

        return await self._request(
            "GET",
            f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        )

    async def update_tunnel_config(
        self,
        tunnel_id: str,
        config: dict,
        account_id: str | None = None,
    ) -> dict:
        """Update tunnel configuration.

        Parameters
        ----------
        tunnel_id : str
            Tunnel ID
        config : dict
            New configuration
        account_id : str | None
            Account ID

        Returns
        -------
        dict
            Updated configuration
        """
        if not account_id:
            account_id = await self.get_account_id()

        return await self._request(
            "PUT",
            f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
            json={"config": config},
        )

    async def add_ingress_rule(
        self,
        tunnel_id: str,
        hostname: str,
        service: str,
        path: str = "",
        account_id: str | None = None,
    ) -> dict:
        """Add an ingress rule to a tunnel.

        Parameters
        ----------
        tunnel_id : str
            Tunnel ID
        hostname : str
            Public hostname (e.g., portal.example.com)
        service : str
            Local service URL (e.g., http://localhost:8080)
        path : str
            Optional path prefix
        account_id : str | None
            Account ID

        Returns
        -------
        dict
            Updated configuration
        """
        if not account_id:
            account_id = await self.get_account_id()

        # Get current config
        current_config = await self.get_tunnel_config(tunnel_id, account_id)
        ingress = current_config.get("config", {}).get("ingress", [])

        # Build new rule
        new_rule: dict[str, Any] = {
            "hostname": hostname,
            "service": service,
        }
        if path:
            new_rule["path"] = path

        # Check if rule already exists
        for rule in ingress:
            if rule.get("hostname") == hostname:
                # Update existing rule
                rule["service"] = service
                if path:
                    rule["path"] = path
                break
        else:
            # Insert before the catch-all rule (last rule)
            if ingress and ingress[-1].get("service") == "http_status:404":
                ingress.insert(-1, new_rule)
            else:
                ingress.append(new_rule)
                # Ensure catch-all rule exists
                ingress.append({"service": "http_status:404"})

        # Update config
        new_config = current_config.get("config", {})
        new_config["ingress"] = ingress

        result = await self.update_tunnel_config(tunnel_id, new_config, account_id)
        logger.info(f"Added ingress rule: {hostname} -> {service}")
        return result

    async def remove_ingress_rule(
        self,
        tunnel_id: str,
        hostname: str,
        account_id: str | None = None,
    ) -> dict:
        """Remove an ingress rule from a tunnel.

        Parameters
        ----------
        tunnel_id : str
            Tunnel ID
        hostname : str
            Hostname to remove
        account_id : str | None
            Account ID

        Returns
        -------
        dict
            Updated configuration
        """
        if not account_id:
            account_id = await self.get_account_id()

        # Get current config
        current_config = await self.get_tunnel_config(tunnel_id, account_id)
        ingress = current_config.get("config", {}).get("ingress", [])

        # Remove the rule
        ingress = [r for r in ingress if r.get("hostname") != hostname]

        # Update config
        new_config = current_config.get("config", {})
        new_config["ingress"] = ingress

        result = await self.update_tunnel_config(tunnel_id, new_config, account_id)
        logger.info(f"Removed ingress rule for: {hostname}")
        return result

    async def list_zones(self) -> list[dict]:
        """List all DNS zones (domains) accessible with this token.

        Returns
        -------
        list[dict]
            List of zones with id, name, status
        """
        result = await self._request("GET", "/zones")
        zones = result if isinstance(result, list) else []

        return [
            {
                "id": z.get("id"),
                "name": z.get("name"),
                "status": z.get("status"),
            }
            for z in zones
        ]

    async def list_dns_records(self, zone_id: str) -> list[dict]:
        """List DNS records for a zone.

        Parameters
        ----------
        zone_id : str
            Zone ID

        Returns
        -------
        list[dict]
            List of DNS records
        """
        result = await self._request("GET", f"/zones/{zone_id}/dns_records")
        records = result if isinstance(result, list) else []

        return [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("type"),
                "content": r.get("content"),
                "proxied": r.get("proxied"),
            }
            for r in records
        ]

    async def create_tunnel_dns_record(
        self,
        zone_id: str,
        tunnel_id: str,
        subdomain: str,
    ) -> dict:
        """Create a CNAME DNS record pointing to a tunnel.

        Parameters
        ----------
        zone_id : str
            Zone ID
        tunnel_id : str
            Tunnel ID
        subdomain : str
            Subdomain name (e.g., "portal" for portal.example.com)

        Returns
        -------
        dict
            Created DNS record
        """
        # Get zone name
        zones = await self.list_zones()
        zone = next((z for z in zones if z["id"] == zone_id), None)
        if not zone:
            raise Exception(f"Zone {zone_id} not found")

        zone_name = zone["name"]
        full_hostname = f"{subdomain}.{zone_name}" if subdomain else zone_name

        # Create CNAME record pointing to tunnel
        tunnel_cname = f"{tunnel_id}.cfargotunnel.com"

        result = await self._request(
            "POST",
            f"/zones/{zone_id}/dns_records",
            json={
                "type": "CNAME",
                "name": full_hostname,
                "content": tunnel_cname,
                "proxied": True,
            },
        )

        logger.info(f"Created DNS record: {full_hostname} -> {tunnel_cname}")
        return result

    async def get_tunnel_options(self) -> dict:
        """Get available tunnels and zones for dropdown selection.

        Returns
        -------
        dict
            Dictionary with tunnels, zones, and suggested settings
        """
        tunnels = await self.list_tunnels()
        zones = await self.list_zones()

        return {
            "tunnels": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "status": t["status"],
                    "label": f"{t['name']} ({t['status']})",
                }
                for t in tunnels
            ],
            "zones": [
                {
                    "id": z["id"],
                    "name": z["name"],
                    "label": z["name"],
                }
                for z in zones
            ],
        }
