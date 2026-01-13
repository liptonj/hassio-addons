"""Invite code management for registration access control."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import generate_invite_code
from app.db.models import InviteCode

logger = logging.getLogger(__name__)


class InviteCodeManager:
    """Manager for invite code operations."""

    def __init__(self, db: Session):
        """Initialize the invite code manager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_code(
        self,
        max_uses: int = 1,
        expires_at: datetime | None = None,
        note: str | None = None,
        created_by: str | None = None,
    ) -> InviteCode:
        """Create a new invite code.

        Args:
            max_uses: Maximum number of times the code can be used
            expires_at: Optional expiration datetime
            note: Optional note about the code
            created_by: Optional identifier of who created the code

        Returns:
            Created InviteCode instance
        """
        code = generate_invite_code()

        # Ensure uniqueness
        while self.db.query(InviteCode).filter(InviteCode.code == code).first():
            code = generate_invite_code()

        invite_code = InviteCode(
            code=code,
            max_uses=max_uses,
            expires_at=expires_at,
            note=note,
            created_by=created_by,
        )

        self.db.add(invite_code)
        self.db.commit()
        self.db.refresh(invite_code)

        logger.info(f"Created invite code: {code}")
        return invite_code

    def validate_code(self, code: str) -> tuple[bool, str]:
        """Validate an invite code.

        Args:
            code: The invite code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code:
            return False, "Invite code is required"

        invite_code = (
            self.db.query(InviteCode)
            .filter(InviteCode.code == code.upper())
            .first()
        )

        if not invite_code:
            return False, "Invalid invite code"

        if not invite_code.is_active:
            return False, "Invite code has been deactivated"

        if invite_code.uses >= invite_code.max_uses:
            return False, "Invite code has reached maximum uses"

        if invite_code.expires_at:
            if invite_code.expires_at < datetime.now(timezone.utc):
                return False, "Invite code has expired"

        return True, ""

    def use_code(self, code: str) -> bool:
        """Mark an invite code as used.

        Args:
            code: The invite code that was used

        Returns:
            True if successfully marked, False otherwise
        """
        invite_code = (
            self.db.query(InviteCode)
            .filter(InviteCode.code == code.upper())
            .first()
        )

        if not invite_code:
            return False

        invite_code.uses += 1
        invite_code.last_used_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"Invite code {code} used (now {invite_code.uses}/{invite_code.max_uses})")
        return True

    def list_codes(
        self,
        include_expired: bool = False,
        include_inactive: bool = False,
    ) -> list[InviteCode]:
        """List all invite codes.

        Args:
            include_expired: Include expired codes
            include_inactive: Include deactivated codes

        Returns:
            List of InviteCode instances
        """
        query = self.db.query(InviteCode)

        if not include_inactive:
            query = query.filter(InviteCode.is_active.is_(True))

        if not include_expired:
            query = query.filter(
                (InviteCode.expires_at.is_(None))
                | (InviteCode.expires_at > datetime.now(timezone.utc))
            )

        return query.order_by(InviteCode.created_at.desc()).all()

    def deactivate_code(self, code: str) -> bool:
        """Deactivate an invite code.

        Args:
            code: The invite code to deactivate

        Returns:
            True if successfully deactivated, False otherwise
        """
        invite_code = (
            self.db.query(InviteCode)
            .filter(InviteCode.code == code.upper())
            .first()
        )

        if not invite_code:
            return False

        invite_code.is_active = False
        self.db.commit()

        logger.info(f"Deactivated invite code: {code}")
        return True

    def delete_code(self, code: str) -> bool:
        """Delete an invite code.

        Args:
            code: The invite code to delete

        Returns:
            True if successfully deleted, False otherwise
        """
        invite_code = (
            self.db.query(InviteCode)
            .filter(InviteCode.code == code.upper())
            .first()
        )

        if not invite_code:
            return False

        self.db.delete(invite_code)
        self.db.commit()

        logger.info(f"Deleted invite code: {code}")
        return True
