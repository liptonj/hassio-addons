"""
UDN (User Defined Network) ID management for Meraki WPN.

This module manages the assignment and tracking of UDN IDs for MAC-based
authentication in Meraki Wi-Fi Personal Networks (WPN). UDN IDs create
private network segments for each user/unit.

UDN ID Range: 2-16777200 (ID 1 is reserved by Meraki)
VSA Format: Cisco-AVPair = "udn:private-group-id=<ID>"
"""

import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UdnAssignment, User

logger = logging.getLogger(__name__)

# UDN ID constants
UDN_MIN_ID = 2  # ID 1 is reserved
UDN_MAX_ID = 16777200
UDN_VSA_ATTRIBUTE = "Cisco-AVPair"
UDN_VSA_FORMAT = "udn:private-group-id={udn_id}"

# MAC address regex patterns
MAC_PATTERNS = [
    re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$"),  # AA:BB:CC:DD:EE:FF
    re.compile(r"^([0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}$"),  # AA-BB-CC-DD-EE-FF
    re.compile(r"^[0-9a-fA-F]{12}$"),                     # AABBCCDDEEFF
]


class UdnError(Exception):
    """Base exception for UDN management errors."""


class UdnPoolExhausted(UdnError):
    """Raised when no UDN IDs are available."""


class InvalidMacAddress(UdnError):
    """Raised when MAC address format is invalid."""


def normalize_mac_address(mac: str) -> str:
    """
    Normalize MAC address to lowercase colon format.

    Args:
        mac: MAC address in various formats

    Returns:
        Normalized MAC address (aa:bb:cc:dd:ee:ff)

    Raises:
        InvalidMacAddress: If format is invalid
    """
    # Remove whitespace
    mac = mac.strip()
    
    # Validate format
    if not any(pattern.match(mac) for pattern in MAC_PATTERNS):
        raise InvalidMacAddress(f"Invalid MAC address format: {mac}")
    
    # Remove separators and convert to lowercase
    mac_clean = mac.replace(":", "").replace("-", "").lower()
    
    # Format with colons
    return ":".join([mac_clean[i:i+2] for i in range(0, 12, 2)])


def validate_udn_id(udn_id: int) -> bool:
    """
    Validate UDN ID is in acceptable range.

    Args:
        udn_id: UDN ID to validate

    Returns:
        True if valid

    Raises:
        UdnError: If UDN ID is out of range
    """
    if not UDN_MIN_ID <= udn_id <= UDN_MAX_ID:
        raise UdnError(
            f"UDN ID {udn_id} out of range ({UDN_MIN_ID}-{UDN_MAX_ID})"
        )
    return True


def format_cisco_avpair(udn_id: int) -> str:
    """
    Format UDN ID as Cisco-AVPair VSA for RADIUS.

    Args:
        udn_id: UDN ID to format

    Returns:
        Formatted VSA string

    Example:
        >>> format_cisco_avpair(500)
        'Cisco-AVPair := "udn:private-group-id=500"'
    """
    validate_udn_id(udn_id)
    return f'{UDN_VSA_ATTRIBUTE} := "{UDN_VSA_FORMAT.format(udn_id=udn_id)}"'


class UdnManager:
    """Manages UDN ID assignment and tracking for WPN."""

    def __init__(self, db: Session):
        """
        Initialize UDN manager.

        Args:
            db: Database session
        """
        self.db = db
        logger.info("UDN Manager initialized")

    def get_next_available_udn_id(self) -> int:
        """
        Find the next available UDN ID.

        Returns:
            Available UDN ID

        Raises:
            UdnPoolExhausted: If no IDs available
        """
        # Get all assigned IDs
        stmt = select(UdnAssignment.udn_id).order_by(UdnAssignment.udn_id)
        assigned_ids = set(self.db.execute(stmt).scalars().all())
        
        # Find first available ID
        for udn_id in range(UDN_MIN_ID, UDN_MAX_ID + 1):
            if udn_id not in assigned_ids:
                logger.debug(f"Next available UDN ID: {udn_id}")
                return udn_id
        
        raise UdnPoolExhausted(
            f"No available UDN IDs (all {UDN_MAX_ID - UDN_MIN_ID + 1} IDs assigned)"
        )

    def get_udn_pool_status(self) -> dict[str, int | float]:
        """
        Get UDN ID pool statistics.

        Returns:
            Dictionary with pool status
        """
        total = UDN_MAX_ID - UDN_MIN_ID + 1
        assigned = self.db.query(UdnAssignment).filter(
            UdnAssignment.is_active == True  # noqa: E712
        ).count()
        available = total - assigned
        
        # Use 4 decimal places for utilization to handle large pools
        utilization = (assigned / total) * 100 if total > 0 else 0
        
        return {
            "total": total,
            "assigned": assigned,
            "available": available,
            "utilization_percent": round(utilization, 4),
        }

    def assign_udn_id(
        self,
        user_id: int,
        mac_address: Optional[str] = None,
        registration_id: Optional[int] = None,
        ipsk_id: Optional[str] = None,
        user_name: Optional[str] = None,
        user_email: Optional[str] = None,
        unit: Optional[str] = None,
        network_id: Optional[str] = None,
        ssid_number: Optional[int] = None,
        note: Optional[str] = None,
        specific_udn_id: Optional[int] = None,
    ) -> UdnAssignment:
        """
        Assign a UDN ID to a USER (not MAC address).
        
        Relationship: USER → PSK → UDN
        MAC address is optional (for tracking, not required for UDN lookup).

        Args:
            user_id: User ID (required) - UDN is assigned to user
            mac_address: MAC address (optional) - for tracking only
            registration_id: Associated registration ID
            ipsk_id: Associated IPSK ID
            user_name: User name for reference
            user_email: User email for reference
            unit: Unit number/identifier
            network_id: Meraki network ID
            ssid_number: SSID number
            note: Optional note
            specific_udn_id: Specific UDN ID to assign (optional)

        Returns:
            UdnAssignment object

        Raises:
            InvalidMacAddress: If MAC format invalid (if provided)
            UdnPoolExhausted: If no IDs available
            UdnError: If UDN ID already assigned
        """
        # Normalize MAC address if provided (optional)
        mac_normalized = None
        if mac_address:
            mac_normalized = normalize_mac_address(mac_address)
        
        # Check if user already has UDN assignment
        existing = self.db.query(UdnAssignment).filter(
            UdnAssignment.user_id == user_id,
            UdnAssignment.is_active == True
        ).first()
        
        if existing:
            logger.info(f"User {user_id} already has UDN ID {existing.udn_id}")
            # Update MAC address if provided and different
            if mac_normalized and existing.mac_address != mac_normalized:
                existing.mac_address = mac_normalized
                self.db.commit()
                logger.info(f"Updated MAC address for user {user_id}: {mac_normalized}")
            return existing
        
        # Determine UDN ID
        if specific_udn_id is not None:
            validate_udn_id(specific_udn_id)
            udn_id = specific_udn_id
            
            # Check if this UDN ID is already assigned
            conflict = self.db.query(UdnAssignment).filter(
                UdnAssignment.udn_id == udn_id,
                UdnAssignment.is_active == True  # noqa: E712
            ).first()
            
            if conflict:
                raise UdnError(
                    f"UDN ID {udn_id} already assigned to User {conflict.user_id}"
                )
        else:
            udn_id = self.get_next_available_udn_id()
        
        # Create assignment (UDN assigned to USER, not MAC)
        assignment = UdnAssignment(
            udn_id=udn_id,
            user_id=user_id,  # Required - UDN assigned to user
            mac_address=mac_normalized,  # Optional - for tracking only
            registration_id=registration_id,
            ipsk_id=ipsk_id,
            user_name=user_name,
            user_email=user_email,
            unit=unit,
            network_id=network_id,
            ssid_number=ssid_number,
            note=note,
            is_active=True,
        )
        
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        
        mac_str = f"MAC {mac_normalized}" if mac_normalized else "no MAC"
        logger.info(
            f"Assigned UDN ID {udn_id} to User {user_id} ({mac_str}) "
            f"(user: {user_name or 'N/A'}, unit: {unit or 'N/A'})"
        )
        
        return assignment
    
    def get_udn_by_user_id(self, user_id: int) -> Optional[UdnAssignment]:
        """Get UDN assignment for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            UdnAssignment if found, None otherwise
        """
        return self.db.query(UdnAssignment).filter(
            UdnAssignment.user_id == user_id,
            UdnAssignment.is_active == True
        ).first()
    
    def get_udn_by_psk(self, psk_passphrase: str, portal_db_url: Optional[str] = None) -> Optional[UdnAssignment]:
        """Get UDN assignment via USER → PSK relationship.
        
        Looks up user by PSK passphrase, then gets UDN ID assigned to that user.
        
        Args:
            psk_passphrase: PSK passphrase
            portal_db_url: Portal database URL (if different from FreeRADIUS DB)
            
        Returns:
            UdnAssignment if found, None otherwise
        """
        try:
            # Query portal database to find user by PSK
            # This assumes we can query the portal database directly
            if portal_db_url:
                from sqlalchemy import create_engine, text
                portal_engine = create_engine(portal_db_url)
                with portal_engine.connect() as portal_conn:
                    # Find user by PSK passphrase (need to decrypt and compare)
                    # For now, we'll query by ipsk_id if we have it
                    # In production, this should use a proper lookup mechanism
                    result = portal_conn.execute(text("""
                        SELECT id, email, ipsk_id
                        FROM users
                        WHERE ipsk_passphrase_encrypted IS NOT NULL
                          AND ipsk_passphrase_encrypted != ''
                          AND is_active = true
                    """))
                    
                    users = result.fetchall()
                    # Match PSK (would need decryption here)
                    # For now, return None - this should be implemented with proper PSK matching
                    return None
            else:
                # Fallback: query from UDN assignments if ipsk_id is available
                # This is a simplified lookup - actual implementation should match PSK
                return None
        except Exception as e:
            logger.error(f"Failed to lookup UDN by PSK: {e}")
            return None

    def get_assignment_by_mac(self, mac_address: str) -> Optional[UdnAssignment]:
        """
        Get UDN assignment for a MAC address.

        Args:
            mac_address: MAC address to lookup

        Returns:
            UdnAssignment or None
        """
        try:
            mac_normalized = normalize_mac_address(mac_address)
        except InvalidMacAddress:
            logger.warning(f"Invalid MAC address format: {mac_address}")
            return None
        
        return self.db.query(UdnAssignment).filter(
            UdnAssignment.mac_address == mac_normalized,
            UdnAssignment.is_active == True  # noqa: E712
        ).first()

    def get_assignment_by_udn_id(self, udn_id: int) -> Optional[UdnAssignment]:
        """
        Get UDN assignment for a UDN ID.

        Args:
            udn_id: UDN ID to lookup

        Returns:
            UdnAssignment or None
        """
        return self.db.query(UdnAssignment).filter(
            UdnAssignment.udn_id == udn_id,
            UdnAssignment.is_active == True  # noqa: E712
        ).first()

    def get_assignments_by_user(self, user_id: int) -> list[UdnAssignment]:
        """
        Get all UDN assignments for a user.

        Args:
            user_id: User ID

        Returns:
            List of UdnAssignment objects
        """
        return self.db.query(UdnAssignment).filter(
            UdnAssignment.user_id == user_id,
            UdnAssignment.is_active == True  # noqa: E712
        ).all()

    def get_assignments_by_unit(self, unit: str) -> list[UdnAssignment]:
        """
        Get all UDN assignments for a unit.

        Args:
            unit: Unit identifier

        Returns:
            List of UdnAssignment objects
        """
        return self.db.query(UdnAssignment).filter(
            UdnAssignment.unit == unit,
            UdnAssignment.is_active == True  # noqa: E712
        ).all()

    def revoke_assignment(self, mac_address: str) -> bool:
        """
        Revoke UDN assignment for a MAC address.

        Args:
            mac_address: MAC address to revoke

        Returns:
            True if revoked, False if not found
        """
        try:
            mac_normalized = normalize_mac_address(mac_address)
        except InvalidMacAddress:
            logger.warning(f"Invalid MAC address format: {mac_address}")
            return False
        
        assignment = self.get_assignment_by_mac(mac_normalized)
        if not assignment:
            logger.warning(f"No assignment found for MAC {mac_normalized}")
            return False
        
        assignment.is_active = False
        self.db.commit()
        
        logger.info(f"Revoked UDN ID {assignment.udn_id} for MAC {mac_normalized}")
        return True

    def update_last_auth(self, mac_address: str) -> bool:
        """
        Update last authentication timestamp for a MAC address.

        Args:
            mac_address: MAC address that authenticated

        Returns:
            True if updated, False if not found
        """
        from datetime import datetime, timezone
        
        try:
            mac_normalized = normalize_mac_address(mac_address)
        except InvalidMacAddress:
            logger.warning(f"Invalid MAC address format: {mac_address}")
            return False
        
        assignment = self.get_assignment_by_mac(mac_normalized)
        if not assignment:
            logger.debug(f"No assignment found for MAC {mac_normalized}")
            return False
        
        assignment.last_auth_at = datetime.now(timezone.utc)
        self.db.commit()
        
        logger.debug(f"Updated last auth for MAC {mac_normalized}")
        return True

    def list_assignments(
        self,
        active_only: bool = True,
        network_id: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> list[UdnAssignment]:
        """
        List UDN assignments with optional filtering.

        Args:
            active_only: Only return active assignments
            network_id: Filter by network ID
            unit: Filter by unit

        Returns:
            List of UdnAssignment objects
        """
        query = self.db.query(UdnAssignment)
        
        if active_only:
            query = query.filter(UdnAssignment.is_active == True)  # noqa: E712
        
        if network_id:
            query = query.filter(UdnAssignment.network_id == network_id)
        
        if unit:
            query = query.filter(UdnAssignment.unit == unit)
        
        return query.order_by(UdnAssignment.udn_id).all()

    def generate_radius_users_entry(self, assignment: UdnAssignment) -> str:
        """
        Generate FreeRADIUS users file entry for a UDN assignment.

        Args:
            assignment: UdnAssignment object

        Returns:
            Users file entry string

        Example:
            aa:bb:cc:dd:ee:ff Cleartext-Password := "N/A"
                Cisco-AVPair := "udn:private-group-id=500",
                Reply-Message := "WPN Access Granted"
        """
        cisco_avpair = UDN_VSA_FORMAT.format(udn_id=assignment.udn_id)
        reply_message = f"WPN Access - {assignment.user_name or 'User'} - Unit {assignment.unit or 'N/A'}"
        
        entry = f'{assignment.mac_address} Cleartext-Password := "N/A"\n'
        entry += f'    {UDN_VSA_ATTRIBUTE} := "{cisco_avpair}",\n'
        entry += f'    Reply-Message := "{reply_message}"\n'
        
        return entry

    def generate_all_radius_users(self) -> str:
        """
        Generate complete FreeRADIUS users file for all active assignments.

        Returns:
            Complete users file content
        """
        assignments = self.list_assignments(active_only=True)
        
        users_file = "# Auto-generated RADIUS users for WPN UDN assignment\n"
        users_file += "# Do not edit manually - managed by UDN Manager\n"
        users_file += f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n\n"
        
        for assignment in assignments:
            users_file += self.generate_radius_users_entry(assignment)
            users_file += "\n"
        
        # Add default deny at the end
        users_file += "# Default deny\n"
        users_file += "DEFAULT Auth-Type := Reject\n"
        users_file += '    Reply-Message := "Authentication failed"\n'
        
        logger.info(f"Generated RADIUS users file with {len(assignments)} entries")
        return users_file
