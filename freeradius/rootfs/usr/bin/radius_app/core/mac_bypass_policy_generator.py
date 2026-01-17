"""MAC Bypass Policy Generator for FreeRADIUS.

This module generates pre-built authentication policies for Meraki WPN:

1. DEFAULT PSK POLICY - Accept default SSID PSK, redirect to captive portal
2. MAC + PSK VALIDATION - Look up MAC address, validate PSK, full access
3. PSK ONLY (IPSK) VALIDATION - Just validate IPSK, ignore MAC

Authentication Flow:
-------------------
1. New device connects with default SSID PSK
2. Server applies guest profile with captive portal URL
3. User registers through portal (creates MAC + PSK or IPSK)
4. Next connection: MAC/IPSK lookup, validate PSK, grant full access

Per FreeRADIUS documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/unlang/index.html
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.db.models import (
    RadiusAuthorizationProfile,
    RadiusMacBypassConfig,
)

logger = logging.getLogger(__name__)

# Default FreeRADIUS version
DEFAULT_FREERADIUS_VERSION = 3

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class MacBypassPolicyConfig:
    """Configuration for MAC bypass policy generation.
    
    Attributes:
        default_psk: Default SSID passphrase for unregistered devices
        portal_url: Captive portal URL for registration
        redirect_acl: ACL name for URL redirect
        guest_profile_id: ID of guest/unregistered authorization profile
        registered_profile_id: ID of registered user authorization profile
        mac_psk_table: Database table for MAC-PSK associations
        ipsk_table: Database table for IPSK registrations
        udn_table: Database table for UDN assignments
        reject_unknown: Reject unknown devices (False = continue to next policy)
        freeradius_version: FreeRADIUS version (3 or 4)
    """
    default_psk: str = "changeme"
    portal_url: str = "https://portal.example.com/register"
    redirect_acl: str = "CAPTIVE_PORTAL_REDIRECT"
    guest_profile_id: Optional[int] = None
    registered_profile_id: Optional[int] = None
    mac_psk_table: str = "device_registrations"
    ipsk_table: str = "ipsk_registrations"
    udn_table: str = "udn_assignments"
    reject_unknown: bool = False
    freeradius_version: int = DEFAULT_FREERADIUS_VERSION
    guest_group_policy: str = "Guest-Access"
    guest_session_timeout: int = 3600


class MacBypassPolicyGenerator:
    """Generates MAC bypass authentication policies for FreeRADIUS.
    
    This generator creates unlang policies for the common Meraki WPN
    authentication patterns:
    
    1. Default PSK -> Captive Portal redirect
    2. MAC + PSK validation -> Full access
    3. IPSK validation -> Full access
    """

    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        """Initialize generator with template directory.
        
        Args:
            template_dir: Path to Jinja2 templates.
        """
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_profile(
        self,
        db: Session,
        profile_id: Optional[int],
    ) -> Optional[RadiusAuthorizationProfile]:
        """Get authorization profile by ID.
        
        Args:
            db: Database session.
            profile_id: Profile ID.
            
        Returns:
            Authorization profile or None.
        """
        if not profile_id:
            return None
            
        stmt = select(RadiusAuthorizationProfile).where(
            RadiusAuthorizationProfile.id == profile_id
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_profile_by_name(
        self,
        db: Session,
        name: str,
    ) -> Optional[RadiusAuthorizationProfile]:
        """Get authorization profile by name.
        
        Args:
            db: Database session.
            name: Profile name.
            
        Returns:
            Authorization profile or None.
        """
        stmt = select(RadiusAuthorizationProfile).where(
            RadiusAuthorizationProfile.name == name,
            RadiusAuthorizationProfile.is_active == True,
        )
        return db.execute(stmt).scalar_one_or_none()

    def generate_mac_bypass_policies(
        self,
        db: Session,
        config: MacBypassPolicyConfig,
    ) -> str:
        """Generate all MAC bypass policies.
        
        Args:
            db: Database session.
            config: Policy configuration.
            
        Returns:
            Generated unlang policy code.
        """
        try:
            template = self.env.get_template("mac_bypass_policies.j2")
        except TemplateNotFound:
            logger.warning("Template mac_bypass_policies.j2 not found, using fallback")
            return self._generate_fallback(config)

        # Get profiles
        guest_profile = self.get_profile(db, config.guest_profile_id)
        registered_profile = self.get_profile(db, config.registered_profile_id)

        # If no profiles specified, try to find by common names
        if not guest_profile:
            guest_profile = self.get_profile_by_name(db, "Guest-Access")
        if not registered_profile:
            registered_profile = self.get_profile_by_name(db, "Registered-Users")

        context = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "freeradius_version": config.freeradius_version,
            "default_psk": config.default_psk,
            "portal_url": config.portal_url,
            "redirect_acl": config.redirect_acl,
            "guest_profile": guest_profile,
            "registered_profile": registered_profile,
            "mac_psk_table": config.mac_psk_table,
            "ipsk_table": config.ipsk_table,
            "udn_table": config.udn_table,
            "reject_unknown": config.reject_unknown,
            "guest_group_policy": config.guest_group_policy,
            "guest_session_timeout": config.guest_session_timeout,
        }

        return template.render(context)

    def write_mac_bypass_policies(
        self,
        db: Session,
        config: MacBypassPolicyConfig,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Write MAC bypass policies to file.
        
        Args:
            db: Database session.
            config: Policy configuration.
            output_path: Output file path.
            
        Returns:
            Path to written file.
        """
        if output_path is None:
            output_path = Path("/config/raddb/policy.d/mac_bypass")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        policy_content = self.generate_mac_bypass_policies(db, config)
        output_path.write_text(policy_content)

        logger.info(f"✅ Wrote MAC bypass policies to {output_path}")
        return output_path

    def _generate_fallback(self, config: MacBypassPolicyConfig) -> str:
        """Generate basic fallback policy without template.
        
        Args:
            config: Policy configuration.
            
        Returns:
            Basic unlang code.
        """
        lines = [
            "# MAC Bypass Policies (fallback generation)",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
        ]

        if config.freeradius_version == 4:
            lines.extend([
                "# Policy 1: Default PSK - Captive Portal",
                f'if (&User-Password == "{config.default_psk}") {{',
                f'    &reply.Cisco-AVPair += "url-redirect={config.portal_url}"',
                f'    &reply.Cisco-AVPair += "url-redirect-acl={config.redirect_acl}"',
                f'    &reply.Filter-Id := "{config.guest_group_policy}"',
                f"    &reply.Session-Timeout := {config.guest_session_timeout}",
                "    ok",
                "}",
                "",
                "# Policy 2: MAC + PSK Lookup",
                "if (&Calling-Station-Id) {",
                "    sql {",
                "        ok = return",
                "        notfound = noop",
                "    }",
                "}",
                "",
                "# Policy 3: IPSK Lookup",
                "if (&User-Name) {",
                "    sql {",
                "        ok = return",
                "        notfound = noop",
                "    }",
                "}",
            ])
        else:
            lines.extend([
                "# Policy 1: Default PSK - Captive Portal",
                f'if ("%{{User-Password}}" == "{config.default_psk}") {{',
                "    update reply {",
                f'        Cisco-AVPair += "url-redirect={config.portal_url}"',
                f'        Cisco-AVPair += "url-redirect-acl={config.redirect_acl}"',
                f'        Filter-Id := "{config.guest_group_policy}"',
                f"        Session-Timeout := {config.guest_session_timeout}",
                "    }",
                "    ok",
                "}",
                "",
                "# Policy 2: MAC + PSK Lookup",
                'if ("%{Calling-Station-Id}" != "") {',
                "    sql",
                "}",
                "",
                "# Policy 3: IPSK Lookup",
                'if ("%{User-Name}" != "") {',
                "    sql",
                "}",
            ])

        return "\n".join(lines)


def create_default_profiles(db: Session) -> tuple[int, int]:
    """Create default Guest and Registered authorization profiles if they don't exist.
    
    Args:
        db: Database session.
        
    Returns:
        Tuple of (guest_profile_id, registered_profile_id).
    """
    # Check for existing Guest profile
    guest_stmt = select(RadiusAuthorizationProfile).where(
        RadiusAuthorizationProfile.name == "Guest-Access"
    )
    guest_profile = db.execute(guest_stmt).scalar_one_or_none()
    
    if not guest_profile:
        guest_profile = RadiusAuthorizationProfile(
            name="Guest-Access",
            description="Guest/Unregistered devices - Captive portal redirect",
            priority=200,
            policy_type="guest",
            splash_url="https://portal.example.com/register",
            url_redirect_acl="CAPTIVE_PORTAL_REDIRECT",
            filter_id="Guest-Access",
            session_timeout=3600,
            sgt_value=10,  # Low-trust SGT
            sgt_name="Guest",
            is_active=True,
        )
        db.add(guest_profile)
        logger.info("Created default Guest-Access authorization profile")

    # Check for existing Registered profile
    reg_stmt = select(RadiusAuthorizationProfile).where(
        RadiusAuthorizationProfile.name == "Registered-Users"
    )
    registered_profile = db.execute(reg_stmt).scalar_one_or_none()
    
    if not registered_profile:
        registered_profile = RadiusAuthorizationProfile(
            name="Registered-Users",
            description="Registered users - Full network access",
            priority=100,
            policy_type="user",
            filter_id="Full-Access",
            session_timeout=86400,  # 24 hours
            sgt_value=100,  # Trusted SGT
            sgt_name="Registered",
            include_udn=True,
            is_active=True,
        )
        db.add(registered_profile)
        logger.info("Created default Registered-Users authorization profile")

    db.commit()
    
    # Refresh to get IDs
    db.refresh(guest_profile)
    db.refresh(registered_profile)
    
    return guest_profile.id, registered_profile.id


# Convenience function
def generate_mac_bypass_policies(
    db: Session,
    default_psk: str = "changeme",
    portal_url: str = "https://portal.example.com/register",
    output_path: Optional[Path] = None,
    freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
) -> Path:
    """Generate and write MAC bypass policies.
    
    Args:
        db: Database session.
        default_psk: Default SSID passphrase.
        portal_url: Captive portal URL.
        output_path: Output file path.
        freeradius_version: FreeRADIUS version.
        
    Returns:
        Path to written file.
    """
    # Ensure default profiles exist
    guest_id, registered_id = create_default_profiles(db)
    
    config = MacBypassPolicyConfig(
        default_psk=default_psk,
        portal_url=portal_url,
        guest_profile_id=guest_id,
        registered_profile_id=registered_id,
        freeradius_version=freeradius_version,
    )
    
    generator = MacBypassPolicyGenerator()
    return generator.write_mac_bypass_policies(db, config, output_path)
