"""Unlang Policy Generator for FreeRADIUS.

This module generates FreeRADIUS unlang policy code from the database.
Unlang policies determine WHEN/IF a user should be authorized and
WHICH authorization profile to apply.

Per FreeRADIUS v4 documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/unlang/index.html

Key concepts:
- Keywords: if, elsif, else, switch, case, foreach
- Conditions: attribute comparisons, regex, exists
- Actions: ok, reject, fail, noop, handled
- Local variables: uint32, string, etc. (v4 only)
- Module calls: sql, eap, ldap, etc.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.db.models import (
    RadiusAuthorizationProfile,
    RadiusUnlangPolicy,
)

logger = logging.getLogger(__name__)

# Default FreeRADIUS version (Alpine package is v3.x)
DEFAULT_FREERADIUS_VERSION = 3

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


class UnlangPolicyGenerator:
    """Generates FreeRADIUS unlang policies from database configuration.
    
    This generator creates policy files that contain the decision logic
    for authentication and authorization. The policies reference
    authorization profiles which define what attributes to return.
    """

    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        """Initialize the generator with template directory.
        
        Args:
            template_dir: Path to Jinja2 templates directory.
        """
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_policies_by_section(
        self,
        db: Session,
        section: str = "authorize",
    ) -> list[RadiusUnlangPolicy]:
        """Get all active policies for a specific section.
        
        Args:
            db: Database session.
            section: Processing section (authorize, authenticate, etc.)
            
        Returns:
            List of policies ordered by priority.
        """
        stmt = (
            select(RadiusUnlangPolicy)
            .where(
                RadiusUnlangPolicy.is_active == True,
                RadiusUnlangPolicy.section == section,
            )
            .order_by(RadiusUnlangPolicy.priority)
        )
        
        return list(db.execute(stmt).scalars().all())

    def get_authorization_profile(
        self,
        db: Session,
        profile_id: int,
    ) -> Optional[RadiusAuthorizationProfile]:
        """Get an authorization profile by ID.
        
        Args:
            db: Database session.
            profile_id: Profile ID to retrieve.
            
        Returns:
            Authorization profile or None.
        """
        if not profile_id:
            return None
            
        stmt = select(RadiusAuthorizationProfile).where(
            RadiusAuthorizationProfile.id == profile_id
        )
        return db.execute(stmt).scalar_one_or_none()

    def generate_policy_unlang(
        self,
        policy: RadiusUnlangPolicy,
        db: Session,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
    ) -> str:
        """Generate unlang code for a single policy.
        
        Args:
            policy: The policy to generate code for.
            db: Database session.
            freeradius_version: FreeRADIUS version (3 or 4).
            
        Returns:
            Generated unlang code as string.
        """
        try:
            template = self.env.get_template("unlang_policy.j2")
        except TemplateNotFound:
            logger.warning("Template unlang_policy.j2 not found, using fallback")
            return self._generate_fallback_policy(policy, db, freeradius_version)

        # Get referenced profiles
        authorization_profile = self.get_authorization_profile(
            db, policy.authorization_profile_id
        )
        else_profile = self.get_authorization_profile(
            db, policy.else_profile_id
        )

        context = {
            "policy": policy,
            "authorization_profile": authorization_profile,
            "else_profile": else_profile,
            "freeradius_version": freeradius_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return template.render(context)

    def generate_section_policies(
        self,
        db: Session,
        section: str = "authorize",
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
    ) -> str:
        """Generate all unlang policies for a section.
        
        Args:
            db: Database session.
            section: Processing section.
            freeradius_version: FreeRADIUS version.
            
        Returns:
            Combined unlang code for all policies in section.
        """
        policies = self.get_policies_by_section(db, section)
        
        if not policies:
            logger.info(f"No active policies for section: {section}")
            return f"# No custom policies defined for {section} section\n"

        output_parts = [
            f"# ============================================================================",
            f"# Custom Unlang Policies for {section.upper()} Section",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            f"# Total Policies: {len(policies)}",
            f"# ============================================================================",
            "",
        ]

        for policy in policies:
            logger.info(f"Generating unlang for policy: {policy.name}")
            policy_code = self.generate_policy_unlang(
                policy, db, freeradius_version
            )
            output_parts.append(policy_code)
            output_parts.append("")

        return "\n".join(output_parts)

    def write_policy_file(
        self,
        db: Session,
        section: str = "authorize",
        output_path: Optional[Path] = None,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
    ) -> Path:
        """Write policies to a file.
        
        Args:
            db: Database session.
            section: Processing section.
            output_path: Path to write to. Defaults to policy.d/{section}
            freeradius_version: FreeRADIUS version.
            
        Returns:
            Path to written file.
        """
        if output_path is None:
            output_path = Path(f"/config/raddb/policy.d/{section}_custom")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        policy_content = self.generate_section_policies(
            db, section, freeradius_version
        )

        output_path.write_text(policy_content)
        logger.info(f"✅ Wrote {section} policies to {output_path}")

        return output_path

    def write_all_policies(
        self,
        db: Session,
        output_dir: Optional[Path] = None,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
    ) -> dict[str, Path]:
        """Write all policy files for all sections.
        
        Args:
            db: Database session.
            output_dir: Directory to write to.
            freeradius_version: FreeRADIUS version.
            
        Returns:
            Dict mapping section names to output paths.
        """
        sections = ["authorize", "authenticate", "post-auth", "accounting"]
        output_paths = {}

        for section in sections:
            if output_dir:
                output_path = output_dir / f"{section}_custom"
            else:
                output_path = None
                
            output_paths[section] = self.write_policy_file(
                db, section, output_path, freeradius_version
            )

        return output_paths

    def _generate_fallback_policy(
        self,
        policy: RadiusUnlangPolicy,
        db: Session,
        freeradius_version: int,
    ) -> str:
        """Generate policy without template (fallback).
        
        Args:
            policy: Policy to generate.
            db: Database session.
            freeradius_version: FreeRADIUS version.
            
        Returns:
            Basic unlang code.
        """
        lines = [
            f"# Policy: {policy.name}",
            f"# Priority: {policy.priority}",
        ]
        
        if policy.description:
            lines.append(f"# {policy.description}")
        
        # Build condition
        if policy.condition_type == "attribute":
            if policy.condition_operator == "exists":
                if freeradius_version == 4:
                    lines.append(f"if (&{policy.condition_attribute}) {{")
                else:
                    lines.append(f'if ("%{{{policy.condition_attribute}}}" != "") {{')
            else:
                if freeradius_version == 4:
                    lines.append(
                        f'if (&{policy.condition_attribute} {policy.condition_operator} "{policy.condition_value}") {{'
                    )
                else:
                    lines.append(
                        f'if ("%{{{policy.condition_attribute}}}" {policy.condition_operator} "{policy.condition_value}") {{'
                    )
        elif policy.condition_type == "sql_lookup":
            if freeradius_version == 4:
                lines.append(f"# SQL lookup: {policy.sql_condition}")
                lines.append(f"sql {{")
                lines.append(f"    ok = return")
                lines.append(f"}}")
                lines.append(f"if (ok) {{")
            else:
                lines.append(f'if ("%{{sql:{policy.sql_condition}}}" != "") {{')
        else:
            lines.append("if (1) {")  # Always true for custom/unknown

        # Build action
        if policy.action_type == "accept":
            lines.append(f"    ok")
        elif policy.action_type == "reject":
            if freeradius_version == 4:
                lines.append(f'    &reply.Reply-Message := "{policy.reject_reason or "Access Denied"}"')
            else:
                lines.append(f"    update reply {{")
                lines.append(f'        Reply-Message := "{policy.reject_reason or "Access Denied"}"')
                lines.append(f"    }}")
            lines.append(f"    reject")
        elif policy.action_type == "apply_profile":
            profile = self.get_authorization_profile(db, policy.authorization_profile_id)
            if profile:
                lines.append(f"    # Apply profile: {profile.name}")
                if freeradius_version == 4:
                    if profile.vlan_id:
                        lines.append(f"    &reply.Tunnel-Private-Group-Id := {profile.vlan_id}")
                    if profile.filter_id:
                        lines.append(f'    &reply.Filter-Id := "{profile.filter_id}"')
                else:
                    lines.append(f"    update reply {{")
                    if profile.vlan_id:
                        lines.append(f"        Tunnel-Private-Group-Id := {profile.vlan_id}")
                    if profile.filter_id:
                        lines.append(f'        Filter-Id := "{profile.filter_id}"')
                    lines.append(f"    }}")
            lines.append(f"    ok")
        elif policy.action_type == "call_module":
            lines.append(f"    {policy.module_name}")
        else:
            lines.append(f"    noop")

        lines.append("}")

        # Else action
        if policy.else_action_type:
            lines.append("else {")
            if policy.else_action_type == "reject":
                lines.append(f"    reject")
            else:
                lines.append(f"    noop")
            lines.append("}")

        lines.append("")
        return "\n".join(lines)


# Convenience function
def generate_unlang_policies(
    db: Session,
    output_dir: Optional[Path] = None,
    freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
) -> dict[str, Path]:
    """Generate all unlang policy files.
    
    Args:
        db: Database session.
        output_dir: Directory to write to.
        freeradius_version: FreeRADIUS version.
        
    Returns:
        Dict mapping section names to output paths.
    """
    generator = UnlangPolicyGenerator()
    return generator.write_all_policies(db, output_dir, freeradius_version)
