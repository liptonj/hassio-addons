"""Cloudflare DNS integration for Let's Encrypt DNS-01 challenge.

Uses the Cloudflare API to manage DNS records for:
1. RADIUS server hostname (A/AAAA record)
2. Let's Encrypt DNS-01 challenge (_acme-challenge TXT record)

This allows certificate management without exposing port 80.
Credentials are synced from the portal's Cloudflare configuration.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class CloudflareError(Exception):
    """Cloudflare API error."""
    pass


class CloudflareDNSManager:
    """Manages DNS records via Cloudflare API for RADIUS server.
    
    Supports:
    - Creating/updating A records for RADIUS hostname
    - DNS-01 challenge for Let's Encrypt (no port 80 needed)
    - Certificate automation with certbot DNS plugin
    """
    
    CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"
    
    def __init__(
        self,
        api_token: str,
        zone_id: str,
        account_id: Optional[str] = None,
    ):
        """Initialize Cloudflare DNS manager.
        
        Args:
            api_token: Cloudflare API token with DNS edit permissions
            zone_id: Zone ID for the domain
            account_id: Optional account ID
        """
        self.api_token = api_token
        self.zone_id = zone_id
        self.account_id = account_id
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def verify_token(self) -> bool:
        """Verify API token is valid.
        
        Returns:
            True if token is valid
        """
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.CLOUDFLARE_API_BASE}/user/tokens/verify")
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                logger.info("Cloudflare API token verified")
                return True
            return False
            
        except httpx.HTTPError as e:
            logger.error(f"Cloudflare token verification failed: {e}")
            return False
    
    async def get_zone_name(self) -> str:
        """Get zone name for the configured zone ID.
        
        Returns:
            Zone name (domain)
        """
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}"
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return data["result"]["name"]
            raise CloudflareError(f"Failed to get zone: {data.get('errors')}")
            
        except httpx.HTTPError as e:
            raise CloudflareError(f"Failed to get zone: {e}") from e
    
    async def create_a_record(
        self,
        hostname: str,
        ip_address: str,
        proxied: bool = False,
        ttl: int = 300,
    ) -> dict:
        """Create or update an A record for the RADIUS server.
        
        Args:
            hostname: Full hostname (e.g., radius.example.com)
            ip_address: IPv4 address
            proxied: Whether to proxy through Cloudflare (usually False for RADIUS)
            ttl: TTL in seconds (1 = auto)
            
        Returns:
            Created/updated record info
        """
        client = await self._get_client()
        
        # Check if record exists
        existing = await self._find_record(hostname, "A")
        
        record_data = {
            "type": "A",
            "name": hostname,
            "content": ip_address,
            "proxied": proxied,
            "ttl": ttl if not proxied else 1,  # Auto TTL if proxied
        }
        
        try:
            if existing:
                # Update existing record
                response = await client.patch(
                    f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records/{existing['id']}",
                    json=record_data,
                )
            else:
                # Create new record
                response = await client.post(
                    f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records",
                    json=record_data,
                )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                action = "Updated" if existing else "Created"
                logger.info(f"{action} A record: {hostname} -> {ip_address}")
                return data["result"]
            raise CloudflareError(f"Failed to create A record: {data.get('errors')}")
            
        except httpx.HTTPError as e:
            raise CloudflareError(f"Failed to create A record: {e}") from e
    
    async def create_acme_challenge(
        self,
        hostname: str,
        challenge_token: str,
    ) -> dict:
        """Create TXT record for ACME DNS-01 challenge.
        
        Args:
            hostname: Base hostname (e.g., radius.example.com)
            challenge_token: ACME challenge token
            
        Returns:
            Created record info
        """
        challenge_name = f"_acme-challenge.{hostname}"
        
        client = await self._get_client()
        
        # Delete existing challenge record if present
        existing = await self._find_record(challenge_name, "TXT")
        if existing:
            await self._delete_record(existing["id"])
        
        record_data = {
            "type": "TXT",
            "name": challenge_name,
            "content": challenge_token,
            "ttl": 120,  # Short TTL for challenge
        }
        
        try:
            response = await client.post(
                f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records",
                json=record_data,
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                logger.info(f"Created ACME challenge record: {challenge_name}")
                return data["result"]
            raise CloudflareError(f"Failed to create challenge: {data.get('errors')}")
            
        except httpx.HTTPError as e:
            raise CloudflareError(f"Failed to create challenge: {e}") from e
    
    async def delete_acme_challenge(self, hostname: str) -> bool:
        """Delete ACME challenge record after validation.
        
        Args:
            hostname: Base hostname
            
        Returns:
            True if deleted
        """
        challenge_name = f"_acme-challenge.{hostname}"
        
        existing = await self._find_record(challenge_name, "TXT")
        if existing:
            await self._delete_record(existing["id"])
            logger.info(f"Deleted ACME challenge record: {challenge_name}")
            return True
        return False
    
    async def _find_record(self, name: str, record_type: str) -> Optional[dict]:
        """Find a DNS record by name and type.
        
        Args:
            name: Record name
            record_type: Record type (A, AAAA, TXT, etc.)
            
        Returns:
            Record dict if found, None otherwise
        """
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records",
                params={"name": name, "type": record_type},
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") and data["result"]:
                return data["result"][0]
            return None
            
        except httpx.HTTPError:
            return None
    
    async def _delete_record(self, record_id: str) -> bool:
        """Delete a DNS record.
        
        Args:
            record_id: Record ID to delete
            
        Returns:
            True if deleted
        """
        client = await self._get_client()
        
        try:
            response = await client.delete(
                f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records/{record_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
    
    async def list_records(self, record_type: Optional[str] = None) -> list[dict]:
        """List all DNS records in the zone.
        
        Args:
            record_type: Optional filter by type
            
        Returns:
            List of DNS records
        """
        client = await self._get_client()
        
        params = {}
        if record_type:
            params["type"] = record_type
        
        try:
            response = await client.get(
                f"{self.CLOUDFLARE_API_BASE}/zones/{self.zone_id}/dns_records",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return data["result"]
            return []
            
        except httpx.HTTPError:
            return []


class LetsEncryptDNS01:
    """Let's Encrypt certificate management using DNS-01 challenge.
    
    Uses Cloudflare DNS for challenge validation - no port 80 needed.
    This is the recommended approach when you have Cloudflare DNS.
    """
    
    def __init__(
        self,
        cloudflare_token: str,
        zone_id: str,
        cert_dir: Optional[Path] = None,
    ):
        """Initialize Let's Encrypt DNS-01 manager.
        
        Args:
            cloudflare_token: Cloudflare API token
            zone_id: Cloudflare zone ID
            cert_dir: Directory to store certificates
        """
        self.cloudflare = CloudflareDNSManager(cloudflare_token, zone_id)
        
        if cert_dir is None:
            from radius_app.config import get_settings
            settings = get_settings()
            cert_dir = Path(settings.radius_certs_path) / "letsencrypt"
        
        self.cert_dir = cert_dir
        self.cert_dir.mkdir(parents=True, exist_ok=True)
    
    async def obtain_certificate(
        self,
        domain: str,
        email: str,
        staging: bool = False,
    ) -> dict:
        """Obtain Let's Encrypt certificate using DNS-01 challenge.
        
        Args:
            domain: Domain name (e.g., radius.example.com)
            email: Email for Let's Encrypt notifications
            staging: Use staging environment for testing
            
        Returns:
            Dictionary with certificate paths
        """
        logger.info(f"Obtaining Let's Encrypt certificate for {domain}")
        
        # Create credentials file for certbot cloudflare plugin
        credentials_file = self.cert_dir / "cloudflare.ini"
        credentials_file.write_text(
            f"dns_cloudflare_api_token = {self.cloudflare.api_token}\n"
        )
        credentials_file.chmod(0o600)
        
        # Build certbot command
        cmd = [
            "certbot", "certonly",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials", str(credentials_file),
            "--dns-cloudflare-propagation-seconds", "30",
            "-d", domain,
            "--email", email,
            "--agree-tos",
            "--non-interactive",
            "--config-dir", str(self.cert_dir / "config"),
            "--work-dir", str(self.cert_dir / "work"),
            "--logs-dir", str(self.cert_dir / "logs"),
        ]
        
        if staging:
            cmd.append("--staging")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                logger.error(f"Certbot failed: {result.stderr}")
                raise CloudflareError(f"Certbot failed: {result.stderr}")
            
            # Find certificate files
            live_dir = self.cert_dir / "config" / "live" / domain
            
            cert_path = live_dir / "fullchain.pem"
            key_path = live_dir / "privkey.pem"
            
            if not cert_path.exists():
                raise CloudflareError(f"Certificate not found at {cert_path}")
            
            logger.info(f"✅ Certificate obtained for {domain}")
            
            return {
                "success": True,
                "domain": domain,
                "certificate": str(cert_path),
                "private_key": str(key_path),
                "chain": str(live_dir / "chain.pem"),
                "fullchain": str(cert_path),
            }
            
        except subprocess.TimeoutExpired:
            raise CloudflareError("Certbot timed out")
        except FileNotFoundError:
            raise CloudflareError("Certbot not installed")
        finally:
            # Clean up credentials file
            if credentials_file.exists():
                credentials_file.unlink()
    
    async def renew_certificate(self) -> dict:
        """Renew existing certificates.
        
        Returns:
            Renewal result
        """
        # Create credentials file
        credentials_file = self.cert_dir / "cloudflare.ini"
        credentials_file.write_text(
            f"dns_cloudflare_api_token = {self.cloudflare.api_token}\n"
        )
        credentials_file.chmod(0o600)
        
        cmd = [
            "certbot", "renew",
            "--dns-cloudflare-credentials", str(credentials_file),
            "--config-dir", str(self.cert_dir / "config"),
            "--work-dir", str(self.cert_dir / "work"),
            "--logs-dir", str(self.cert_dir / "logs"),
            "--non-interactive",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode == 0:
                logger.info("✅ Certificate renewal completed")
                return {"success": True, "message": "Certificates renewed"}
            else:
                return {"success": False, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Renewal timed out"}
        except FileNotFoundError:
            return {"success": False, "error": "Certbot not installed"}
        finally:
            if credentials_file.exists():
                credentials_file.unlink()
    
    async def close(self):
        """Clean up resources."""
        await self.cloudflare.close()


async def sync_cloudflare_config_from_portal(portal_api_url: str, portal_token: str) -> dict:
    """Sync Cloudflare configuration from the portal server.
    
    Uses the dedicated /admin/radius/cloudflare-credentials endpoint which
    returns unmasked credentials for RADIUS certificate provisioning.
    
    Retrieves:
    - API token (unmasked)
    - Zone ID
    - Account ID
    - Configured hostname
    - Certificate source preference
    
    Args:
        portal_api_url: Portal API URL (e.g., http://localhost:8080/api)
        portal_token: Portal API authentication token
        
    Returns:
        Cloudflare configuration from portal
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Use the dedicated RADIUS endpoint that returns unmasked credentials
            response = await client.get(
                f"{portal_api_url}/admin/radius/cloudflare-credentials",
                headers={"Authorization": f"Bearer {portal_token}"},
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return {
                    "cloudflare_enabled": data.get("cloudflare_enabled", False),
                    "cloudflare_api_token": data.get("cloudflare_api_token", ""),
                    "cloudflare_zone_id": data.get("cloudflare_zone_id", ""),
                    "cloudflare_zone_name": data.get("cloudflare_zone_name", ""),
                    "cloudflare_account_id": data.get("cloudflare_account_id", ""),
                    "radius_hostname": data.get("radius_hostname", ""),
                    "radius_cert_source": data.get("radius_cert_source", "selfsigned"),
                }
            else:
                logger.error(f"Portal returned error: {data}")
                return {}
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to sync Cloudflare config from portal: {e}")
            return {}
