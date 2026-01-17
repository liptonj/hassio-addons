"""Meraki Dashboard API client for standalone mode using official Meraki SDK."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, Optional

import meraki  # type: ignore[import-untyped]

from app.config import get_settings
from app.core.security import generate_passphrase

logger = logging.getLogger(__name__)


class MerakiClientError(Exception):
    """Exception raised for Meraki API errors."""


class MerakiDashboardClient:
    """Client for direct Meraki Dashboard API integration using official SDK.

    This client uses the official Meraki Python SDK which provides:
    - Proper authentication handling
    - Built-in rate limiting and retry logic
    - Better error messages
    - Type hints and auto-completion
    - Maintained by Cisco/Meraki
    """

    def __init__(self, api_key: str):
        """Initialize the Meraki Dashboard client.

        Args:
            api_key: Meraki Dashboard API key
        """
        self.api_key = api_key
        self._dashboard: meraki.DashboardAPI | None = None
        self._connected = False

    async def connect(self) -> None:
        """Initialize the Meraki SDK client."""
        # Run SDK initialization in executor since it's synchronous
        loop = asyncio.get_running_loop()
        self._dashboard = await loop.run_in_executor(
            None,
            partial(
                meraki.DashboardAPI,
                api_key=self.api_key,
                print_console=False,
                output_log=False,
                suppress_logging=True,
                wait_on_rate_limit=True,
            )
        )
        self._connected = True
        logger.info("Meraki Dashboard SDK client initialized")

    async def disconnect(self) -> None:
        """Close the Meraki SDK client."""
        self._dashboard = None
        self._connected = False
        logger.info("Meraki Dashboard SDK client disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._dashboard is not None

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous SDK method in an executor.

        Parameters
        ----------
        func : callable
            SDK method to call
        *args
            Positional arguments
        **kwargs
            Keyword arguments

        Returns
        -------
        Any
            Result from the SDK method

        Raises
        ------
        MerakiClientError
            If the SDK call fails
        """
        if not self._dashboard:
            raise MerakiClientError("Client not connected")

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, partial(func, *args, **kwargs))
        except meraki.APIError as e:
            raise MerakiClientError(f"API error: {e}") from e
        except Exception as e:
            raise MerakiClientError(f"Request failed: {e}") from e

    # =========================================================================
    # Organization & Network
    # =========================================================================

    async def get_organizations(self) -> list[dict]:
        """Get all organizations the API key has access to."""
        return await self._run_sync(self._dashboard.organizations.getOrganizations)

    async def get_networks(self, organization_id: str) -> list[dict]:
        """Get all networks in an organization."""
        return await self._run_sync(
            self._dashboard.organizations.getOrganizationNetworks,
            organization_id
        )

    async def get_network(self, network_id: str) -> dict:
        """Get network details."""
        return await self._run_sync(self._dashboard.networks.getNetwork, network_id)

    async def get_network_devices(self, network_id: str) -> list[dict]:
        """Get all devices in a network (APs, switches, MXs, etc).
        
        Args:
            network_id: Network ID
            
        Returns:
            List of device dictionaries with keys: serial, name, model, lanIp, mac, tags, networkId
        """
        return await self._run_sync(
            self._dashboard.networks.getNetworkDevices,
            network_id
        )

    # =========================================================================
    # SSID Management
    # =========================================================================

    async def get_ssids(self, network_id: str) -> list[dict]:
        """Get all SSIDs for a network."""
        return await self._run_sync(
            self._dashboard.wireless.getNetworkWirelessSsids,
            network_id
        )

    async def get_ssid(self, network_id: str, ssid_number: int) -> dict:
        """Get SSID details."""
        return await self._run_sync(
            self._dashboard.wireless.getNetworkWirelessSsid,
            network_id,
            str(ssid_number)
        )

    async def get_ssid_wpn_status(self, network_id: str, ssid_number: int) -> dict:
        """Get SSID configuration status for WPN.

        Returns details about whether SSID is properly configured for iPSK + WPN.
        Checks:
        1. SSID is enabled
        2. Auth mode is "ipsk-without-radius"
        3. Wi-Fi Personal Network (WPN) is enabled
        """
        ssid = await self.get_ssid(network_id, ssid_number)

        auth_mode = ssid.get("authMode", "")
        is_enabled = ssid.get("enabled", False)

        # Check if configured for Identity PSK without RADIUS
        is_ipsk = auth_mode == "ipsk-without-radius"

        # Check if WPN is enabled (wifiPersonalNetworkEnabled field)
        wpn_enabled = ssid.get("wifiPersonalNetworkEnabled", False)

        # Configuration complete (everything done via API)
        configuration_complete = is_enabled and is_ipsk
        
        # Fully ready for WPN means: SSID enabled + iPSK auth + WPN enabled
        ready_for_wpn = configuration_complete and wpn_enabled

        # Build status messages
        issues = []
        warnings = []
        
        if not is_enabled:
            issues.append("SSID is disabled")
        if not is_ipsk:
            issues.append(f"Auth mode is '{auth_mode}' (needs 'ipsk-without-radius')")
        if not wpn_enabled and configuration_complete:
            warnings.append("WPN must be enabled manually in Meraki Dashboard (API limitation)")

        return {
            "name": ssid.get("name", f"SSID-{ssid_number}"),
            "number": ssid_number,
            "enabled": is_enabled,
            "auth_mode": auth_mode,
            "is_ipsk_configured": is_ipsk,
            "wpn_enabled": wpn_enabled,
            "configuration_complete": configuration_complete,  # All API-configurable items done
            "encryption_mode": ssid.get("wpaEncryptionMode", ""),
            "ip_assignment_mode": ssid.get("ipAssignmentMode", ""),
            "ready_for_wpn": ready_for_wpn,  # Fully ready (including manual WPN enable)
            "issues": issues,
            "warnings": warnings,
            "raw_config": ssid,
        }

    async def configure_ssid_for_wpn(
        self,
        network_id: str,
        ssid_number: int,
        ssid_name: str | None = None,
        group_policy_name: str = "WPN-Users",
        splash_url: str | None = None,
    ) -> dict:
        """Configure an SSID for Identity PSK without RADIUS (WPN-ready).

        This sets up the SSID with the correct authentication mode for WPN:
        1. Creates a group policy with splash bypass for registered users
        2. Enables the SSID
        3. Sets auth mode to "ipsk-without-radius"
        4. Sets WPA2 encryption
        5. Uses Bridge mode (required for WPN per Meraki docs)
        6. Enables click-through splash page (redirects to registration)

        Flow:
        - New users (no iPSK): See splash page → redirected to registration
        - Registered users (with iPSK): Bypass splash → direct internet access

        NOTE: WPN enablement is NOT supported via the Meraki API as of 2024.
        WPN must be enabled manually in Meraki Dashboard:
        Wireless > Access Control > [SSID] > Wi-Fi Personal Network (WPN) > Enabled

        Parameters
        ----------
        network_id : str
            Meraki network ID
        ssid_number : int
            SSID number (0-14)
        ssid_name : str | None
            Optional new name for the SSID
        group_policy_name : str
            Name for the group policy (created with splash bypass if doesn't exist)
        splash_url : str | None
            Custom splash page URL (defaults to portal registration page)

        Returns
        -------
        dict
            Updated SSID configuration with group policy info
        """
        # Step 1: Ensure a group policy exists
        existing_policies = await self.get_group_policies(network_id)
        policy_exists = any(p["name"] == group_policy_name for p in existing_policies)

        group_policy = None
        if not policy_exists:
            logger.info(f"Creating group policy '{group_policy_name}' for WPN")
            group_policy = await self.create_group_policy(network_id, group_policy_name)
        else:
            group_policy = next(
                p for p in existing_policies if p["name"] == group_policy_name
            )
            logger.info(f"Using existing group policy '{group_policy_name}'")

        # Get group policy ID for setting as default
        group_policy_id = group_policy.get("groupPolicyId") if group_policy else None

        # Step 2: Configure the SSID with Identity PSK and Splash Page
        # Note: wifiPersonalNetworkEnabled is NOT supported via API
        # See: https://community.meraki.com/t5/Wireless/Enable-WPN-via-API/m-p/244636
        update_params: dict[str, Any] = {
            "enabled": True,
            "authMode": "ipsk-without-radius",
            "wpaEncryptionMode": "WPA2 only",
            "ipAssignmentMode": "Bridge mode",
            # Enable click-through splash page for new connections
            "splashPage": "Click-through splash page",
        }

        # Set a default group policy for the SSID if available
        if group_policy_id:
            update_params["defaultVlanId"] = 1  # Default VLAN
            logger.info(f"Group policy {group_policy_id} will be used for new iPSKs")
            logger.info("Group policy has splash bypass enabled for registered users")

        if ssid_name:
            update_params["name"] = ssid_name

        result = await self._run_sync(
            self._dashboard.wireless.updateNetworkWirelessSsid,
            network_id,
            str(ssid_number),
            **update_params
        )

        logger.info(
            f"Configured SSID {ssid_number} for iPSK on network {network_id}. "
            f"Group Policy: {group_policy_name} (ID: {group_policy_id})"
        )

        # Save group policy ID to settings for future iPSK creation
        try:
            import os
            from cryptography.fernet import Fernet
            from app.core.db_settings import DatabaseSettingsManager
            from app.db.database import get_session_local
            
            if group_policy_id:
                # Get encryption key from environment
                key_env = os.getenv("SETTINGS_ENCRYPTION_KEY")
                if key_env:
                    db_mgr = DatabaseSettingsManager(key_env.encode())
                    SessionLocal = get_session_local()
                    with SessionLocal() as db:
                        db_mgr.bulk_update_settings(
                            db=db,
                            settings_dict={"default_group_policy_id": group_policy_id},
                        )
                    logger.info(f"Saved default group policy ID: {group_policy_id}")
                else:
                    logger.warning("SETTINGS_ENCRYPTION_KEY not set, skipping settings save")
        except Exception as e:
            logger.warning(f"Could not save group policy to settings: {e}")

        # Step 3: Configure splash page settings if URL provided
        splash_configured = False
        if splash_url:
            try:
                await self.configure_splash_page(
                    network_id=network_id,
                    ssid_number=ssid_number,
                    splash_url=splash_url,
                )
                splash_configured = True
                logger.info(f"Configured splash page URL: {splash_url}")
            except Exception as e:
                logger.warning(f"Could not configure splash page: {e}")

        # Return combined result
        return {
            "ssid": {
                "number": ssid_number,
                "name": result.get("name"),
                "enabled": result.get("enabled"),
                "authMode": result.get("authMode"),
                "wpaEncryptionMode": result.get("wpaEncryptionMode"),
                "ipAssignmentMode": result.get("ipAssignmentMode"),
                "splashPage": result.get("splashPage"),
            },
            "group_policy": group_policy,
            "group_policy_id": group_policy_id,
            "splash_configured": splash_configured,
            "splash_url": splash_url,
            "manual_step_required": True,
            "message": (
                f"SSID configured for Identity PSK with splash page. "
                f"Group Policy: {group_policy_name} (bypasses splash). "
                "⚠️ MANUAL STEP: Enable WPN in Meraki Dashboard → "
                "Wireless → Access Control → Wi-Fi Personal Network → Enabled"
            ),
        }

    async def configure_splash_page(
        self,
        network_id: str,
        ssid_number: int,
        splash_url: str,
        welcome_message: str = "Welcome! Please register to get your personal WiFi credentials.",
        splash_timeout: int = 1440,
        redirect_url: Optional[str] = None,
    ) -> dict:
        """Configure splash page settings for an SSID.

        Uses official Meraki API:
        https://developer.cisco.com/meraki/api-v1/update-network-wireless-ssid-splash-settings/

        Parameters
        ----------
        network_id : str
            Meraki network ID
        ssid_number : int
            SSID number (0-14)
        splash_url : str
            URL for the custom splash page (your portal URL)
        welcome_message : str
            Welcome message shown on splash page
        splash_timeout : int
            Splash timeout in minutes (default 1440 = 24 hours)
            Valid values: 30, 60, 120, 240, 480, 720, 1080, 1440, 2880, 5760, 
                         7200, 10080, 20160, 43200, 86400, 129600
        redirect_url : str | None
            Optional redirect URL after splash page

        Returns
        -------
        dict
            Updated splash settings
        """
        # Validate splash timeout against Meraki's allowed values
        valid_timeouts = [30, 60, 120, 240, 480, 720, 1080, 1440, 2880, 5760, 
                         7200, 10080, 20160, 43200, 86400, 129600]
        if splash_timeout not in valid_timeouts:
            # Find closest valid timeout
            splash_timeout = min(valid_timeouts, key=lambda x: abs(x - splash_timeout))
            logger.warning(f"Adjusted splash_timeout to nearest valid value: {splash_timeout}")
        
        params = {
            "splashUrl": splash_url,
            "useSplashUrl": True,
            "splashTimeout": splash_timeout,
            "welcomeMessage": welcome_message,
            "blockAllTrafficBeforeSignOn": False,  # Allow non-HTTP traffic before splash
            "allowSimultaneousLogins": True,  # Allow multiple devices per user
        }
        
        # Add redirect URL if provided
        if redirect_url:
            params["redirectUrl"] = redirect_url
            params["useRedirectUrl"] = True
        
        result = await self._run_sync(
            self._dashboard.wireless.updateNetworkWirelessSsidSplashSettings,
            network_id,
            str(ssid_number),
            **params
        )

        logger.info(
            f"Configured splash page for SSID {ssid_number}: {splash_url}"
        )
        return result

    # =========================================================================
    # Group Policy Management
    # =========================================================================

    async def get_group_policies(self, network_id: str) -> list[dict]:
        """Get all group policies for a network."""
        policies = await self._run_sync(
            self._dashboard.networks.getNetworkGroupPolicies,
            network_id
        )
        return [
            {
                "id": p.get("groupPolicyId"),
                "name": p.get("name"),
                "scheduling": p.get("scheduling"),
                "bandwidth": p.get("bandwidth"),
                "firewall_and_traffic_shaping": p.get("firewallAndTrafficShaping"),
            }
            for p in policies
        ]

    async def create_group_policy(
        self,
        network_id: str,
        name: str,
        bypass_splash: bool = True,
        scheduling: dict | None = None,
        bandwidth: dict | None = None,
    ) -> dict:
        """Create a new group policy.

        Parameters
        ----------
        network_id : str
            Meraki network ID
        name : str
            Name for the group policy
        bypass_splash : bool
            If True, devices with this policy bypass splash page (default True)
        scheduling : dict | None
            Scheduling settings (optional)
        bandwidth : dict | None
            Bandwidth settings (optional)

        Returns
        -------
        dict
            Created group policy
        """
        params: dict[str, Any] = {"name": name}

        # Set splash page behavior - bypass for registered users
        if bypass_splash:
            params["splashAuthSettings"] = "bypass"
        else:
            params["splashAuthSettings"] = "network default"

        if scheduling:
            params["scheduling"] = scheduling
        if bandwidth:
            params["bandwidth"] = bandwidth

        result = await self._run_sync(
            self._dashboard.networks.createNetworkGroupPolicy,
            network_id,
            **params
        )

        logger.info(
            f"Created group policy '{name}' on network {network_id} "
            f"(splash bypass: {bypass_splash})"
        )
        return {
            "id": result.get("groupPolicyId"),
            "name": result.get("name"),
        }

    async def update_group_policy(
        self,
        network_id: str,
        group_policy_id: str,
        name: str | None = None,
        bypass_splash: bool | None = None,
        scheduling: dict | None = None,
        bandwidth: dict | None = None,
    ) -> dict:
        """Update an existing group policy.

        Parameters
        ----------
        network_id : str
            Meraki network ID
        group_policy_id : str
            ID of the group policy to update
        name : str | None
            Optional new name for the group policy
        bypass_splash : bool | None
            If True, devices with this policy bypass splash page
        scheduling : dict | None
            Scheduling settings (optional)
        bandwidth : dict | None
            Bandwidth settings (optional)

        Returns
        -------
        dict
            Updated group policy
        """
        params: dict[str, Any] = {}

        if name:
            params["name"] = name

        # Set splash page behavior - bypass for registered users
        if bypass_splash is not None:
            if bypass_splash:
                params["splashAuthSettings"] = "bypass"
            else:
                params["splashAuthSettings"] = "network default"

        if scheduling:
            params["scheduling"] = scheduling
        if bandwidth:
            params["bandwidth"] = bandwidth

        result = await self._run_sync(
            self._dashboard.networks.updateNetworkGroupPolicy,
            network_id,
            group_policy_id,
            **params
        )

        logger.info(
            f"Updated group policy '{group_policy_id}' on network {network_id} "
            f"(splash bypass: {bypass_splash})"
        )
        return {
            "id": result.get("groupPolicyId"),
            "name": result.get("name"),
        }

    # =========================================================================
    # NAC Authorization Policies (RADIUS-based WPN)
    # =========================================================================

    async def get_nac_policies(self, organization_id: str) -> list[dict]:
        """Get all NAC authorization policies for an organization.

        These policies can assign iPSK + Group Policy for RADIUS-based WPN.

        See Meraki API docs: get-organization-nac-authorization-policies
        """
        try:
            policies = await self._run_sync(
                self._dashboard.organizations.getOrganizationNacAuthorizationPolicies,
                organization_id
            )
            return [
                {
                    "id": p.get("policyId"),
                    "name": p.get("name"),
                    "enabled": p.get("enabled", False),
                    "rank": p.get("rank"),
                    "hits": p.get("counts", {}).get("hits", 0),
                    "rules": [
                        {
                            "id": r.get("ruleId"),
                            "name": r.get("name"),
                            "enabled": r.get("enabled", False),
                            "hits": r.get("counts", {}).get("hits", 0),
                            "authorization": {
                                "result": r.get("authorizationProfile", {}).get(
                                    "result"
                                ),
                                "ipsk": r.get("authorizationProfile", {}).get(
                                    "ipsk", {}
                                ).get("value"),
                                "group_policy": r.get("authorizationProfile", {}).get(
                                    "groupPolicy", {}
                                ).get("value"),
                                "vlan": r.get("authorizationProfile", {}).get(
                                    "vlan", {}
                                ).get("value"),
                            }
                        }
                        for r in p.get("rules", [])
                    ],
                    "condition_tags": p.get("conditionTags", []),
                }
                for p in policies
            ]
        except Exception as e:
            logger.error(f"Failed to get NAC policies: {e}")
            raise MerakiClientError(f"Failed to get NAC policies: {e}") from e

    async def create_nac_policy(
        self,
        organization_id: str,
        name: str,
        ipsk_passphrase: str,
        group_policy_name: str,
        enabled: bool = True,
    ) -> dict:
        """Create a NAC authorization policy for WPN.

        This creates a policy that assigns an iPSK and Group Policy
        for RADIUS-based WPN authentication.

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        name : str
            Name for the policy
        ipsk_passphrase : str
            Identity PSK passphrase (8-63 chars)
        group_policy_name : str
            Name of the group policy to assign
        enabled : bool
            Whether the policy is enabled

        Returns
        -------
        dict
            Created NAC policy
        """
        try:
            policy_data = {
                "name": name,
                "enabled": enabled,
                "rules": [
                    {
                        "name": f"{name}-rule",
                        "enabled": True,
                        "authorizationProfile": {
                            "result": "PERMIT",
                            "ipsk": {
                                "value": ipsk_passphrase,
                                "type": "CONSTANT"
                            },
                            "groupPolicy": {
                                "value": group_policy_name,
                                "type": "CONSTANT"
                            }
                        }
                    }
                ]
            }

            result = await self._run_sync(
                self._dashboard.organizations.createOrganizationNacAuthorizationPolicy,
                organization_id,
                **policy_data
            )

            logger.info(f"Created NAC policy '{name}' for RADIUS-based WPN")
            return {
                "id": result.get("policyId"),
                "name": result.get("name"),
                "enabled": result.get("enabled"),
            }
        except Exception as e:
            logger.error(f"Failed to create NAC policy: {e}")
            raise MerakiClientError(f"Failed to create NAC policy: {e}") from e

    # =========================================================================
    # Identity PSK Management
    # =========================================================================

    async def list_ipsks(
        self,
        network_id: str | None = None,
        ssid_number: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List all Identity PSKs for a network/SSID.

        Parameters
        ----------
        network_id : str | None
            Meraki network ID
        ssid_number : int | None
            SSID number (0-14)
        status : str | None
            Filter by status (not natively supported, filtered locally)

        Returns
        -------
        list[dict]
            List of IPSK dictionaries
        """
        settings = get_settings()
        network_id = network_id or settings.default_network_id
        ssid_num = (
            ssid_number
            if ssid_number is not None
            else settings.default_ssid_number
        )

        if not network_id:
            logger.warning("No network_id configured")
            return []

        ipsks = await self._run_sync(
            self._dashboard.wireless.getNetworkWirelessSsidIdentityPsks,
            network_id,
            str(ssid_num)
        )

        # Get group policies for name lookup
        group_policies_map = {}
        try:
            policies = await self.get_group_policies(network_id)
            group_policies_map = {
                str(p.get("groupPolicyId", p.get("id", ""))): p.get("name", "")
                for p in policies
            }
        except Exception as e:
            logger.debug(f"Could not fetch group policies for name lookup: {e}")

        # Add computed fields
        for ipsk in ipsks:
            ipsk["status"] = self._compute_ipsk_status(ipsk)
            ipsk["ssid_number"] = ssid_num
            ipsk["network_id"] = network_id
            
            # Normalize field names for frontend
            ipsk["group_policy_id"] = ipsk.get("groupPolicyId", ipsk.get("group_policy_id"))
            ipsk["psk_group_id"] = ipsk.get("wifiPersonalNetworkId") or ipsk.get("pskGroupId")
            ipsk["expires_at"] = ipsk.get("expiresAt")
            ipsk["created_at"] = ipsk.get("createdAt")
            
            # Lookup group policy name
            policy_id = ipsk.get("group_policy_id")
            if policy_id and policy_id in group_policies_map:
                ipsk["group_policy_name"] = group_policies_map[policy_id]
            else:
                ipsk["group_policy_name"] = None

        # Filter by status if requested
        if status:
            ipsks = [i for i in ipsks if i.get("status") == status]

        return ipsks

    def _compute_ipsk_status(self, ipsk: dict) -> str:
        """Compute IPSK status based on expiration."""
        expires_at = ipsk.get("expiresAt")
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(
                    expires_at.replace("Z", "+00:00")
                )
                if exp_time < datetime.now(UTC):
                    return "expired"
            except Exception:
                pass
        return "active"

    async def create_ipsk(
        self,
        name: str,
        network_id: str,
        ssid_number: int,
        passphrase: str | None = None,
        duration_hours: int | None = None,
        group_policy_id: str | None = None,
        associated_device_id: str | None = None,
        associated_area_id: str | None = None,
        associated_user: str | None = None,
        associated_unit: str | None = None,
    ) -> dict:
        """Create a new Identity PSK.

        Parameters
        ----------
        name : str
            Name for the IPSK
        network_id : str
            Meraki network ID
        ssid_number : int
            SSID number (0-14)
        passphrase : str | None
            Custom passphrase (auto-generated if not provided)
        duration_hours : int | None
            Expiration in hours (None = permanent)
        group_policy_id : str | None
            Group policy ID to apply
        associated_device_id : str | None
            Metadata field for tracking
        associated_area_id : str | None
            Metadata field for tracking
        associated_user : str | None
            Metadata field for tracking
        associated_unit : str | None
            Metadata field for tracking

        Returns
        -------
        dict
            Created IPSK dictionary with passphrase
        """
        settings = get_settings()

        if not passphrase:
            passphrase = generate_passphrase(settings.passphrase_length)

        # groupPolicyId is required by Meraki API
        # Use provided ID, or fall back to default, or "101" (Normal policy)
        policy_id = group_policy_id or settings.default_group_policy_id or "101"
        kwargs = {
            "name": name,
            "passphrase": passphrase,
            "groupPolicyId": policy_id,
        }

        if duration_hours and duration_hours > 0:
            # Calculate expiration timestamp
            expires_at = datetime.now(UTC) + timedelta(hours=duration_hours)
            kwargs["expiresAt"] = expires_at.isoformat()

        result = await self._run_sync(
            self._dashboard.wireless.createNetworkWirelessSsidIdentityPsk,
            network_id,
            str(ssid_number),
            **kwargs
        )

        # Get SSID name for the response
        try:
            ssid_info = await self.get_ssid(network_id, ssid_number)
            result["ssid_name"] = ssid_info.get("name", f"SSID-{ssid_number}")
        except Exception:
            result["ssid_name"] = f"SSID-{ssid_number}"

        # Add passphrase to response (Meraki API returns it on create)
        result["passphrase"] = passphrase
        result["status"] = "active"
        result["network_id"] = network_id
        result["ssid_number"] = ssid_number

        # Store association metadata (would need local DB in production)
        result["associated_device_id"] = associated_device_id
        result["associated_area_id"] = associated_area_id
        result["associated_user"] = associated_user
        result["associated_unit"] = associated_unit

        logger.info(f"Created IPSK: {name} (ID: {result.get('id')})")
        return result

    async def get_ipsk(
        self,
        ipsk_id: str,
        include_passphrase: bool = False,
        network_id: str | None = None,
        ssid_number: int | None = None,
    ) -> dict:
        """Get IPSK details.

        Parameters
        ----------
        ipsk_id : str
            IPSK identifier
        include_passphrase : bool
            Whether to include passphrase (requires re-fetch)
        network_id : str | None
            Network ID (uses default if not provided)
        ssid_number : int | None
            SSID number (uses default if not provided)

        Returns
        -------
        dict
            IPSK dictionary
        """
        # Note: Meraki API doesn't expose passphrase after creation
        _ = include_passphrase  # Reserved for future local passphrase storage
        settings = get_settings()
        network_id = network_id or settings.default_network_id
        ssid_num = (
            ssid_number
            if ssid_number is not None
            else settings.default_ssid_number
        )

        result = await self._run_sync(
            self._dashboard.wireless.getNetworkWirelessSsidIdentityPsk,
            network_id,
            str(ssid_num),
            ipsk_id
        )

        result["status"] = self._compute_ipsk_status(result)
        result["network_id"] = network_id
        result["ssid_number"] = ssid_num

        # Get SSID name
        try:
            ssid_info = await self.get_ssid(network_id, ssid_num)
            result["ssid_name"] = ssid_info.get("name", f"SSID-{ssid_num}")
        except Exception:
            result["ssid_name"] = f"SSID-{ssid_num}"

        return result

    async def update_ipsk(
        self,
        ipsk_id: str,
        name: str | None = None,
        group_policy_id: str | None = None,
        associated_device_id: str | None = None,
        associated_area_id: str | None = None,
        network_id: str | None = None,
        ssid_number: int | None = None,
    ) -> dict:
        """Update an existing IPSK.

        Parameters
        ----------
        ipsk_id : str
            IPSK identifier
        name : str | None
            New name
        group_policy_id : str | None
            New group policy
        associated_device_id : str | None
            HA device association (stored locally)
        associated_area_id : str | None
            HA area association (stored locally)
        network_id : str | None
            Network ID
        ssid_number : int | None
            SSID number

        Returns
        -------
        dict
            Updated IPSK dictionary
        """
        # Note: associations are stored locally, not in Meraki API
        _ = associated_device_id, associated_area_id
        settings = get_settings()
        network_id = network_id or settings.default_network_id
        ssid_num = (
            ssid_number
            if ssid_number is not None
            else settings.default_ssid_number
        )

        kwargs = {}
        if name:
            kwargs["name"] = name
        if group_policy_id:
            kwargs["groupPolicyId"] = group_policy_id

        if kwargs:
            result = await self._run_sync(
                self._dashboard.wireless
                .updateNetworkWirelessSsidIdentityPsk,
                network_id,
                str(ssid_num),
                ipsk_id,
                **kwargs
            )
        else:
            result = await self.get_ipsk(
                ipsk_id, network_id=network_id, ssid_number=ssid_num
            )

        logger.info(f"Updated IPSK: {ipsk_id}")
        return result

    async def revoke_ipsk(
        self,
        ipsk_id: str,
        network_id: str | None = None,
        ssid_number: int | None = None,
    ) -> None:
        """Revoke an IPSK by deleting it.

        Note: Meraki doesn't have a 'revoke' status - we delete the IPSK.

        Args:
            ipsk_id: IPSK identifier
            network_id: Network ID
            ssid_number: SSID number
        """
        await self.delete_ipsk(ipsk_id, network_id, ssid_number)
        logger.info(f"Revoked IPSK: {ipsk_id}")

    async def delete_ipsk(
        self,
        ipsk_id: str,
        network_id: str | None = None,
        ssid_number: int | None = None,
    ) -> None:
        """Delete an IPSK.

        Args:
            ipsk_id: IPSK identifier
            network_id: Network ID
            ssid_number: SSID number
        """
        settings = get_settings()
        network_id = network_id or settings.default_network_id
        ssid_num = (
            ssid_number
            if ssid_number is not None
            else settings.default_ssid_number
        )

        await self._run_sync(
            self._dashboard.wireless.deleteNetworkWirelessSsidIdentityPsk,
            network_id,
            str(ssid_num),
            ipsk_id
        )
        logger.info(f"Deleted IPSK: {ipsk_id}")

    async def reveal_passphrase(
        self,
        ipsk_id: str,
        network_id: str | None = None,
        ssid_number: int | None = None,
    ) -> str:
        """Get the passphrase for an IPSK.

        Note: Meraki API doesn't return passphrase after creation.
        This would require storing passphrases locally.

        Parameters
        ----------
        ipsk_id : str
            IPSK identifier (would be used for local DB lookup)
        network_id : str | None
            Network ID (for future implementation)
        ssid_number : int | None
            SSID number (for future implementation)

        Returns
        -------
        str
            Empty string (Meraki doesn't expose passphrase after creation)
        """
        # These would be used for local passphrase storage lookup
        _ = ipsk_id, network_id, ssid_number
        logger.warning("Meraki API doesn't expose passphrase after IPSK creation")
        return ""

    async def get_ipsk_options(self) -> dict[str, list[dict[str, Any]]]:
        """Get available networks, SSIDs, and group policies."""
        settings = get_settings()
        result: dict[str, list[dict[str, Any]]] = {
            "networks": [],
            "ssids": [],
            "group_policies": [],
        }

        try:
            # Get organizations first
            orgs = await self.get_organizations()
            first_network_id = None

            for org in orgs:
                networks = await self.get_networks(org["id"])
                for net in networks:
                    result["networks"].append({
                        "id": net["id"],
                        "name": net["name"],
                    })
                    # Remember first network for fetching SSIDs
                    if first_network_id is None:
                        first_network_id = net["id"]

            # Get SSIDs for default network OR first network found
            target_network = settings.default_network_id or first_network_id

            if target_network:
                logger.info(f"Fetching SSIDs for network: {target_network}")
                ssids = await self.get_ssids(target_network)
                for ssid in ssids:
                    if ssid.get("enabled"):
                        result["ssids"].append({
                            "number": ssid["number"],
                            "name": ssid["name"],
                        })

                # Get group policies
                policies = await self._run_sync(
                    self._dashboard.networks.getNetworkGroupPolicies,
                    target_network
                )
                for policy in policies:
                    result["group_policies"].append({
                        "id": policy["groupPolicyId"],
                        "name": policy["name"],
                    })
            else:
                logger.warning("No networks found for fetching SSIDs")

        except Exception as e:
            logger.exception(f"Failed to fetch IPSK options: {e}")

        return result

    # =========================================================================
    # Device/Area stubs (not applicable in standalone mode)
    # =========================================================================

    async def get_devices(self) -> list[dict]:
        """Get devices - returns empty in standalone mode."""
        return []

    async def get_areas(self) -> list[dict]:
        """Get areas - returns configured manual units in standalone mode."""
        settings = get_settings()
        return [
            {"area_id": unit, "name": unit}
            for unit in settings.get_manual_units_list()
        ]

    async def get_entities(self) -> list[dict]:
        """Get entities - returns empty in standalone mode."""
        return []

    async def get_states(self) -> list[dict]:
        """Get states - returns empty in standalone mode."""
        return []

    async def get_splash_settings(
        self,
        network_id: str,
        ssid_number: int,
    ) -> dict:
        """Get splash page settings for an SSID.

        Uses official Meraki API:
        https://developer.cisco.com/meraki/api-v1/get-network-wireless-ssid-splash-settings/

        Parameters
        ----------
        network_id : str
            Meraki network ID
        ssid_number : int
            SSID number (0-14)

        Returns
        -------
        dict
            Current splash settings
        """
        result = await self._run_sync(
            self._dashboard.wireless.getNetworkWirelessSsidSplashSettings,
            network_id,
            str(ssid_number),
        )
        
        logger.info(f"Retrieved splash settings for SSID {ssid_number}")
        return result

    async def upload_radsec_ca_certificate(
        self,
        organization_id: str,
        cert_contents: str,
    ) -> dict:
        """Upload CA certificate to Meraki for RadSec.

        This uploads your RADIUS server's CA certificate to Meraki so that
        access points can trust your FreeRADIUS server.

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        cert_contents : str
            PEM-encoded CA certificate contents

        Returns
        -------
        dict
            Certificate upload result with certificate ID
        """
        try:
            result = await self._run_sync(
                self._dashboard.organizations.createOrganizationCertificatesRadSecServerCaCertificate,
                organization_id,
                contents=cert_contents,
            )
            
            logger.info(f"Uploaded RadSec CA certificate to organization {organization_id}")
            return {
                "certificate_id": result.get("id"),
                "contents": result.get("contents"),
                "not_valid_before": result.get("notValidBefore"),
                "not_valid_after": result.get("notValidAfter"),
            }
        except Exception as e:
            logger.error(f"Failed to upload RadSec CA certificate: {e}")
            raise MerakiClientError(f"Failed to upload CA certificate: {e}") from e

    async def get_radsec_ca_certificates(
        self,
        organization_id: str,
    ) -> list[dict]:
        """Get all RadSec CA certificates for an organization.

        Parameters
        ----------
        organization_id : str
            Meraki organization ID

        Returns
        -------
        list[dict]
            List of uploaded CA certificates
        """
        try:
            certs = await self._run_sync(
                self._dashboard.organizations.getOrganizationCertificatesRadSecServerCaCertificates,
                organization_id,
            )
            
            return [
                {
                    "id": cert.get("id"),
                    "contents": cert.get("contents"),
                    "not_valid_before": cert.get("notValidBefore"),
                    "not_valid_after": cert.get("notValidAfter"),
                }
                for cert in certs
            ]
        except Exception as e:
            logger.error(f"Failed to get RadSec CA certificates: {e}")
            raise MerakiClientError(f"Failed to get CA certificates: {e}") from e

    async def delete_radsec_ca_certificate(
        self,
        organization_id: str,
        certificate_id: str,
    ) -> None:
        """Delete a RadSec CA certificate from Meraki.

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        certificate_id : str
            Certificate ID to delete
        """
        try:
            await self._run_sync(
                self._dashboard.organizations.deleteOrganizationCertificatesRadSecServerCaCertificate,
                organization_id,
                certificate_id,
            )
            logger.info(f"Deleted RadSec CA certificate {certificate_id}")
        except Exception as e:
            logger.error(f"Failed to delete RadSec CA certificate: {e}")
            raise MerakiClientError(f"Failed to delete CA certificate: {e}") from e

    async def create_radsec_device_certificate_authority(
        self,
        organization_id: str,
    ) -> dict:
        """Create Meraki's RADSEC device Certificate Authority (CA).

        Call this endpoint when turning on RADSEC for the first time. This starts
        an asynchronous process to generate the CA. The CA is generated and controlled
        by Meraki. Subsequent calls will not generate a new CA.

        Uses official Meraki API:
        https://developer.cisco.com/meraki/api-v1/create-organization-wireless-devices-radsec-certificates-authority/

        Parameters
        ----------
        organization_id : str
            Meraki organization ID

        Returns
        -------
        dict
            Created certificate authority with ID, status, and contents (if ready)
            
        Notes
        -----
        - Returns 202 Accepted (async operation)
        - Contents may be None initially while CA is being generated
        - Call get_radsec_device_certificate_authorities() afterwards to retrieve contents
        """
        try:
            result = await self._run_sync(
                self._dashboard.wireless.createOrganizationWirelessDevicesRadsecCertificatesAuthority,
                organization_id,
            )
            
            ca_id = result.get("certificateAuthorityId")
            status = result.get("status")
            contents = result.get("contents")
            
            logger.info(
                f"Created RadSec device CA for org {organization_id} "
                f"(ID: {ca_id}, Status: {status})"
            )
            
            if not contents:
                logger.warning(
                    "CA contents not yet available - generation in progress. "
                    "Call get_radsec_device_certificate_authorities() to retrieve."
                )
            
            return {
                "certificate_authority_id": ca_id,
                "status": status,
                "contents": contents,  # May be None if still generating
                "ready": contents is not None,
            }
        except Exception as e:
            logger.error(f"Failed to create RadSec device CA: {e}")
            raise MerakiClientError(f"Failed to create device CA: {e}") from e

    async def get_radsec_device_certificate_authorities(
        self,
        organization_id: str,
        certificate_authority_ids: list[str] | None = None,
    ) -> list[dict]:
        """Get organization's RADSEC device Certificate Authority certificates (CAs).

        The primary CA signs all certificates that devices present when establishing
        a secure connection to RADIUS servers via RADSEC protocol. An organization
        will have at most one CA unless the CA is being rotated.

        Uses official Meraki API:
        https://developer.cisco.com/meraki/api-v1/get-organization-wireless-devices-radsec-certificates-authorities/

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        certificate_authority_ids : list[str] | None
            Optional filter by specific CA IDs

        Returns
        -------
        list[dict]
            List of device certificate authorities with id, status, and contents
        """
        try:
            # Build kwargs
            kwargs = {}
            if certificate_authority_ids:
                kwargs['certificateAuthorityIds'] = certificate_authority_ids
            
            result = await self._run_sync(
                self._dashboard.wireless.getOrganizationWirelessDevicesRadsecCertificatesAuthorities,
                organization_id,
                **kwargs
            )
            
            # API returns array with items and meta
            # Example: [{"items": [...], "meta": {...}}]
            if isinstance(result, list) and len(result) > 0:
                items = result[0].get("items", [])
            else:
                items = result if isinstance(result, list) else []
            
            authorities = [
                {
                    "id": auth.get("certificateAuthorityId"),
                    "certificate_authority_id": auth.get("certificateAuthorityId"),
                    "status": auth.get("status"),
                    "contents": auth.get("contents"),
                }
                for auth in items
            ]
            
            logger.info(f"Retrieved {len(authorities)} RadSec device CA(s)")
            return authorities
        except Exception as e:
            logger.error(f"Failed to get RadSec device CAs: {e}")
            raise MerakiClientError(f"Failed to get device CAs: {e}") from e

    async def get_radsec_device_certificate_authority(
        self,
        organization_id: str,
        certificate_authority_id: str,
    ) -> dict | None:
        """Get a specific RadSec device certificate authority by ID.

        Convenience method to retrieve a single CA.

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        certificate_authority_id : str
            Specific CA ID to retrieve

        Returns
        -------
        dict | None
            Certificate authority details, or None if not found
        """
        authorities = await self.get_radsec_device_certificate_authorities(
            organization_id=organization_id,
            certificate_authority_ids=[certificate_authority_id],
        )
        
        return authorities[0] if authorities else None

    async def trust_radsec_device_certificate_authority(
        self,
        organization_id: str,
        authority_id: str,
    ) -> dict:
        """Trust a RadSec device certificate authority.

        Updates the CA state to "trusted", at which point Meraki will generate
        device certificates. "trusted" means the CA is placed on your RADSEC
        server(s) and devices establishing a secure connection using certs signed
        by this CA will pass verification.

        Uses official Meraki API:
        https://developer.cisco.com/meraki/api-v1/update-organization-wireless-devices-radsec-certificates-authorities/

        Parameters
        ----------
        organization_id : str
            Meraki organization ID
        authority_id : str
            Certificate authority ID to trust

        Returns
        -------
        dict
            Updated authority with id, status, and contents

        Notes
        -----
        Only valid status update is "trusted". This endpoint is called after
        creating a CA to activate it for device certificate generation.
        """
        try:
            result = await self._run_sync(
                self._dashboard.wireless.updateOrganizationWirelessDevicesRadsecCertificatesAuthorities,
                organization_id,
                status="trusted",
                certificateAuthorityId=authority_id,
            )

            ca_id = result.get("certificateAuthorityId")
            status_val = result.get("status")
            contents = result.get("contents")

            logger.info(
                f"Trusted RadSec device CA {ca_id} "
                f"(status: {status_val})"
            )

            return {
                "id": ca_id,
                "certificate_authority_id": ca_id,
                "authority_id": ca_id,  # Backward compat
                "status": status_val,
                "contents": contents,
            }
        except Exception as e:
            logger.error(f"Failed to trust RadSec device CA: {e}")
            raise MerakiClientError(f"Failed to trust device CA: {e}") from e

    async def configure_network_radsec(
        self,
        network_id: str,
        ssid_number: int,
        radius_host: str,
        radius_port: int = 2083,
        shared_secret: str = "",
        ca_certificate_id: str = "",
        radius_radsec_tls_idle_timeout: int = 60,
    ) -> dict:
        """Configure an SSID to use RadSec for RADIUS authentication.

        This fully configures the SSID for Identity PSK with RADIUS (WPN).
        Uses official Meraki API fields per:
        https://developer.cisco.com/meraki/api-v1/update-network-wireless-ssid/

        Parameters
        ----------
        network_id : str
            Meraki network ID
        ssid_number : int
            SSID number (0-14)
        radius_host : str
            RadSec server hostname or IP
        radius_port : int
            RadSec port (default 2083)
        shared_secret : str
            Shared secret for RADIUS
        ca_certificate_id : str
            Meraki certificate ID for the uploaded CA
        radius_radsec_tls_idle_timeout : int
            RadSec TLS idle timeout in seconds (default 60)

        Returns
        -------
        dict
            Updated SSID configuration
        """
        try:
            # Configure SSID with Identity PSK and RADIUS authentication
            # Per Meraki API docs: https://developer.cisco.com/meraki/api-v1/update-network-wireless-ssid/
            update_params = {
                "enabled": True,
                "authMode": "ipsk-with-radius",  # Identity PSK with RADIUS
                "wpaEncryptionMode": "WPA2 only",
                "ipAssignmentMode": "Bridge mode",
                "useVlanTagging": False,
                # RADIUS server configuration with RadSec
                "radiusServers": [
                    {
                        "host": radius_host,
                        "port": radius_port,
                        "secret": shared_secret,
                        "radsecEnabled": True,
                        "caCertificate": ca_certificate_id if ca_certificate_id else None,
                    }
                ],
                "radiusAccountingEnabled": True,
                "radiusAccountingServers": [
                    {
                        "host": radius_host,
                        "port": radius_port,
                        "secret": shared_secret,
                        "radsecEnabled": True,
                        "caCertificate": ca_certificate_id if ca_certificate_id else None,
                    }
                ],
                # RadSec TLS timeout
                "radiusRadsecTlsIdleTimeout": radius_radsec_tls_idle_timeout,
            }
            
            result = await self._run_sync(
                self._dashboard.wireless.updateNetworkWirelessSsid,
                network_id,
                str(ssid_number),
                **update_params
            )
            
            logger.info(
                f"Configured SSID {ssid_number} for RadSec on network {network_id}. "
                f"RADIUS: {radius_host}:{radius_port}, RadSec enabled with TLS timeout: {radius_radsec_tls_idle_timeout}s"
            )
            
            # Check if WPN ID is returned (indicates WPN support)
            wpn_enabled = bool(result.get("wifiPersonalNetworkId"))
            
            return {
                "ssid_number": ssid_number,
                "name": result.get("name"),
                "enabled": result.get("enabled"),
                "authMode": result.get("authMode"),
                "radiusServers": result.get("radiusServers"),
                "radiusRadsecTlsIdleTimeout": result.get("radiusRadsecTlsIdleTimeout"),
                "wifiPersonalNetworkId": result.get("wifiPersonalNetworkId"),
                "wpn_enabled": wpn_enabled,
                "configured": True,
            }
        except Exception as e:
            logger.error(f"Failed to configure SSID for RadSec: {e}")
            raise MerakiClientError(f"Failed to configure RadSec: {e}") from e
