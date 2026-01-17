"""Policy configuration generator for FreeRADIUS.

Uses Jinja2 templates for clean, maintainable configuration generation.
"""

import logging
from datetime import datetime, UTC
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import (
    RadiusPolicy,
    RadiusMacBypassConfig,
    RadiusEapConfig,
    RadiusEapMethod,
)

logger = logging.getLogger(__name__)


class PolicyGenerator:
    """Generates FreeRADIUS policy files from database."""
    
    def __init__(self):
        """Initialize policy generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        
        # Ensure directory exists
        self.config_path.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        logger.info(f"Policy generator initialized: {self.config_path}")
    
    def _format_check_item(self, attribute: str, operator: str, value: str) -> str:
        """Format a check item for FreeRADIUS users file.
        
        Args:
            attribute: Attribute name
            operator: Operator (==, !=, =~, etc.)
            value: Attribute value
            
        Returns:
            Formatted check item string
        """
        # Handle regex operator
        if operator == "=~":
            return f'{attribute} {operator} "{value}"'
        return f'{attribute} {operator} {value}'
    
    def _format_reply_item(self, attribute: str, operator: str, value: str) -> str:
        """Format a reply item for FreeRADIUS users file.
        
        Args:
            attribute: Attribute name
            operator: Operator (:=, +=, ==, etc.)
            value: Attribute value
            
        Returns:
            Formatted reply item string
        """
        # Skip comment attributes (they should be handled separately)
        if attribute.startswith("#"):
            return f"    # {value}"
        
        # Determine if value should be quoted
        # Numeric values and certain attributes should not be quoted
        numeric_attributes = [
            "Tunnel-Private-Group-Id",
            "Session-Timeout",
            "Idle-Timeout",
            "Tunnel-Type",
            "Tunnel-Medium-Type",
        ]
        
        should_quote = (
            attribute not in numeric_attributes and
            attribute not in ["Tunnel-Type", "Tunnel-Medium-Type"] and
            isinstance(value, str) and
            not value.isdigit()
        )
        
        # Special handling for Tunnel-Type and Tunnel-Medium-Type (enum values)
        if attribute == "Tunnel-Type":
            return f'    {attribute} {operator} {value}'
        if attribute == "Tunnel-Medium-Type":
            return f'    {attribute} {operator} {value}'
        
        if should_quote:
            return f'    {attribute} {operator} "{value}"'
        else:
            return f'    {attribute} {operator} {value}'
    
    def _build_check_items(self, policy: RadiusPolicy) -> list[str]:
        """Build check items from policy match conditions.
        
        Args:
            policy: Policy to build check items from
            
        Returns:
            List of check item strings
        """
        check_items = []
        
        # Username match (regex) - for PSK matching
        if policy.match_username:
            check_items.append(self._format_check_item("User-Name", "=~", policy.match_username))
        
        # MAC address match (regex) - only if MAC matching is enabled
        if policy.mac_matching_enabled and not policy.match_on_psk_only:
            if policy.match_mac_address:
                check_items.append(self._format_check_item("Calling-Station-Id", "=~", policy.match_mac_address))
        
        # Calling station (alternative to MAC) - only if MAC matching enabled
        if policy.mac_matching_enabled and not policy.match_on_psk_only:
            if policy.match_calling_station:
                check_items.append(self._format_check_item("Calling-Station-Id", "=~", policy.match_calling_station))
        
        # NAS identifier match
        if policy.match_nas_identifier:
            check_items.append(self._format_check_item("NAS-Identifier", "=~", policy.match_nas_identifier))
        
        # NAS IP match
        if policy.match_nas_ip:
            check_items.append(self._format_check_item("NAS-IP-Address", "=~", policy.match_nas_ip))
        
        # PSK validation check
        if policy.psk_validation_required:
            check_items.append(self._format_check_item("Cleartext-Password", "!=", ""))
        
        # Add custom check attributes
        if policy.check_attributes:
            for attr in policy.check_attributes:
                check_items.append(self._format_check_item(
                    attr["attribute"],
                    attr.get("operator", "=="),
                    attr["value"]
                ))
        
        return check_items
    
    def _build_reply_items(self, policy: RadiusPolicy, db: Session = None) -> list[str]:
        """Build reply items from policy.
        
        Args:
            policy: Policy to build reply items from
            db: Database session (for UDN lookup if needed)
            
        Returns:
            List of reply item strings
            
        Vendor-specific attributes:
        - Meraki: Filter-Id for group policy, Cisco-AVPair for url-redirect
        - Cisco AireOS: Cisco-AVPair with air-group-policy-name
        - Cisco ISE: ACS:CiscoSecure-Defined-ACL for downloadable ACL
        - Aruba: Aruba-User-Role or Filter-Id
        """
        reply_items = []
        vendor = getattr(policy, 'group_policy_vendor', 'meraki') or 'meraki'
        
        # ======================================================================
        # CAPTIVE PORTAL / URL REDIRECT
        # ======================================================================
        if policy.splash_url:
            reply_items.append(self._format_reply_item("Reply-Message", ":=", f"Redirect: {policy.splash_url}"))
            # Cisco-AVPair url-redirect works with most Cisco/Meraki devices
            reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"url-redirect={policy.splash_url}"))
        
        # URL Redirect ACL - Controls what traffic gets redirected
        url_redirect_acl = getattr(policy, 'url_redirect_acl', None)
        if url_redirect_acl:
            reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"url-redirect-acl={url_redirect_acl}"))
        
        # ======================================================================
        # GROUP POLICY - Vendor-specific formatting
        # ======================================================================
        # Meraki uses Filter-Id for group policy names
        filter_id = getattr(policy, 'filter_id', None)
        if filter_id:
            reply_items.append(self._format_reply_item("Filter-Id", ":=", filter_id))
        
        # Group policy assignment based on vendor
        if policy.registered_group_policy:
            if vendor == 'meraki':
                # Meraki: Use Filter-Id (if not already set) or Cisco-AVPair
                if not filter_id:
                    reply_items.append(self._format_reply_item("Filter-Id", ":=", policy.registered_group_policy))
            elif vendor == 'cisco_aireos':
                # Cisco AireOS WLC: air-group-policy-name
                reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"air-group-policy-name={policy.registered_group_policy}"))
            elif vendor == 'cisco_ise':
                # Cisco ISE: ACS:CiscoSecure-Group-Id
                reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"ACS:CiscoSecure-Group-Id={policy.registered_group_policy}"))
            elif vendor == 'aruba':
                # Aruba: Aruba-User-Role
                reply_items.append(self._format_reply_item("Aruba-User-Role", ":=", policy.registered_group_policy))
            else:
                # Default: Use Cisco-AVPair
                reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"group-policy-name={policy.registered_group_policy}"))
        
        if policy.unregistered_group_policy:
            # Unregistered group policy - typically for pre-auth / guest access
            if vendor == 'meraki':
                # Meraki doesn't have a separate unregistered policy - handled via CoA
                reply_items.append(self._format_reply_item("# Unregistered policy", "", policy.unregistered_group_policy))
            elif vendor == 'cisco_aireos':
                reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"air-guest-policy-name={policy.unregistered_group_policy}"))
            else:
                reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"guest-policy-name={policy.unregistered_group_policy}"))
        
        # Downloadable ACL (Cisco ISE)
        downloadable_acl = getattr(policy, 'downloadable_acl', None)
        if downloadable_acl:
            reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"ACS:CiscoSecure-Defined-ACL=#ACSACL#{downloadable_acl}"))
        
        # ======================================================================
        # CISCO TRUSTSEC / MERAKI ADAPTIVE POLICY - SGT
        # ======================================================================
        # Security Group Tag (SGT) for network segmentation
        # Format: cts:security-group-tag=XXXX-00 (hex value with revision)
        sgt_value = getattr(policy, 'sgt_value', None)
        if sgt_value is not None:
            # Convert to 4-digit hex with leading zeros, add revision 00
            sgt_hex = f"{sgt_value:04x}-00"
            sgt_name = getattr(policy, 'sgt_name', None)
            if sgt_name:
                reply_items.append(self._format_reply_item(f"# SGT: {sgt_name}", "", f"({sgt_value})"))
            reply_items.append(self._format_reply_item("Cisco-AVPair", ":=", f"cts:security-group-tag={sgt_hex}"))
        
        # UDN ID inclusion (for registered users)
        # Note: UDN lookup happens dynamically in FreeRADIUS via SQL or unlang
        # This is handled at runtime, not in the static users file
        
        # ======================================================================
        # VLAN ASSIGNMENT
        # ======================================================================
        if policy.vlan_id:
            reply_items.append(self._format_reply_item("Tunnel-Type", ":=", "VLAN"))
            reply_items.append(self._format_reply_item("Tunnel-Medium-Type", ":=", "IEEE-802"))
            reply_items.append(self._format_reply_item("Tunnel-Private-Group-Id", ":=", str(policy.vlan_id)))
        
        # Session timeout
        if policy.session_timeout:
            reply_items.append(self._format_reply_item("Session-Timeout", ":=", str(policy.session_timeout)))
        
        # Idle timeout
        if policy.idle_timeout:
            reply_items.append(self._format_reply_item("Idle-Timeout", ":=", str(policy.idle_timeout)))
        
        # Bandwidth limits (vendor-specific for most vendors)
        if policy.bandwidth_limit_up or policy.bandwidth_limit_down:
            if policy.bandwidth_limit_down:
                reply_items.append(self._format_reply_item(
                    "Filter-Id",
                    "+=",
                    f"rate-limit:downstream:{policy.bandwidth_limit_down}"
                ))
            if policy.bandwidth_limit_up:
                reply_items.append(self._format_reply_item(
                    "Filter-Id",
                    "+=",
                    f"rate-limit:upstream:{policy.bandwidth_limit_up}"
                ))
        
        # Add custom reply attributes
        if policy.reply_attributes:
            for attr in policy.reply_attributes:
                reply_items.append(self._format_reply_item(
                    attr["attribute"],
                    attr.get("operator", ":="),
                    attr["value"]
                ))
        
        return reply_items
    
    def generate_policy_file(self, db: Session) -> Path:
        """Generate FreeRADIUS users file from policies.
        
        Includes comprehensive authentication configuration:
        - MAC bypass configurations
        - EAP methods
        - Authorization policies
        
        Args:
            db: Database session
            
        Returns:
            Path to generated policy file
        """
        # Query active policies ordered by priority
        stmt = select(RadiusPolicy).where(
            RadiusPolicy.is_active == True
        ).order_by(RadiusPolicy.priority.asc())
        
        policies = db.execute(stmt).scalars().all()
        
        # Get MAC bypass configurations
        mac_bypass_configs = db.query(RadiusMacBypassConfig).filter(
            RadiusMacBypassConfig.is_active == True
        ).order_by(RadiusMacBypassConfig.name).all()
        
        # Get EAP configuration
        eap_config = db.query(RadiusEapConfig).filter(
            RadiusEapConfig.is_active == True
        ).first()
        
        eap_methods = []
        if eap_config:
            eap_methods = db.query(RadiusEapMethod).filter(
                RadiusEapMethod.eap_config_id == eap_config.id
            ).all()
        
        # Build policy data for template
        policies_data = []
        for policy in policies:
            check_items = self._build_check_items(policy)
            reply_items = self._build_reply_items(policy, db)
            policies_data.append({
                "name": policy.name,
                "priority": policy.priority,
                "description": policy.description,
                "group_name": policy.group_name,
                "policy_type": policy.policy_type,
                "include_udn": policy.include_udn,
                "check_items": check_items,
                "reply_items": reply_items,
            })
        
        # Build template context
        context = {
            "timestamp": datetime.now(UTC).isoformat(),
            "mac_bypass_configs": mac_bypass_configs,
            "eap_config": eap_config,
            "eap_methods": eap_methods,
            "policies": policies_data,
        }
        
        try:
            template = self.jinja_env.get_template("policy_users.j2")
            policy_file = template.render(**context)
        except TemplateNotFound:
            logger.error("Policy template not found - falling back to code generation")
            policy_file = self._generate_fallback_policy_file(
                policies_data, mac_bypass_configs, eap_config, eap_methods
            )
        except Exception as e:
            logger.error(f"Error rendering policy template: {e}", exc_info=True)
            policy_file = self._generate_fallback_policy_file(
                policies_data, mac_bypass_configs, eap_config, eap_methods
            )
        
        # Validate and write safely - prevents invalid configs
        from radius_app.core.config_validator import safe_write_config_file
        output_path = self.config_path / "policies"
        safe_write_config_file(output_path, policy_file, file_type="policy")
        
        logger.info(f"✅ Generated policy file with {len(policies)} policies")
        return output_path
    
    def _generate_fallback_policy_file(
        self,
        policies_data: list,
        mac_bypass_configs: list,
        eap_config,
        eap_methods: list
    ) -> str:
        """Fallback policy file generation if template fails.
        
        Args:
            policies_data: List of policy dictionaries
            mac_bypass_configs: MAC bypass configurations
            eap_config: EAP configuration
            eap_methods: EAP methods
            
        Returns:
            Policy file content as string
        """
        logger.warning("Using fallback code-based policy file generation")
        
        policy_file = "# Policy file - Generated (fallback mode)\n"
        policy_file += f"# Timestamp: {datetime.now(UTC).isoformat()}\n\n"
        
        for policy in policies_data:
            policy_file += f"# Policy: {policy['name']} (Priority: {policy['priority']})\n"
            
            if policy["check_items"]:
                check_line = "DEFAULT " + ", ".join(policy["check_items"])
                policy_file += f"{check_line}\n"
            else:
                policy_file += "DEFAULT Auth-Type := Accept\n"
            
            if policy["reply_items"]:
                for i, item in enumerate(policy["reply_items"]):
                    if i < len(policy["reply_items"]) - 1:
                        policy_file += f"{item},\n"
                    else:
                        policy_file += f"{item}\n"
            
            policy_file += "\n"
        
        policy_file += "# Fallback\n"
        policy_file += "DEFAULT Auth-Type := Accept\n"
        policy_file += '    Reply-Message := "Access granted"\n'
        
        return policy_file
    
    def generate_policy_include(self) -> Path:
        """Generate an include file for policies in the authorize section.
        
        This creates a small include file that can be added to the
        FreeRADIUS authorize section to load policies.
        
        Returns:
            Path to generated include file
        """
        include_content = "# Include authorization policies\n"
        include_content += "# Add this to your FreeRADIUS authorize section:\n"
        include_content += "#   include ${confdir}/policy-includes\n\n"
        include_content += "$INCLUDE ${confdir}/policies\n"
        
        output_path = self.config_path / "policy-includes"
        output_path.write_text(include_content)
        output_path.chmod(0o644)
        
        logger.info("✅ Generated policy include file")
        return output_path
