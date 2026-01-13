"""SQLAlchemy database models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""


class User(Base):
    """User model for registered residents/guests and admins."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Authentication - local username/password
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # IPSK association
    ipsk_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ipsk_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted passphrase - stored locally since Meraki API doesn't return it
    ipsk_passphrase_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssid_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.name} ({self.email})>"


class Registration(Base):
    """Registration request model for tracking registrations."""

    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Invite code used
    invite_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Result
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )  # pending, approved, rejected, completed
    ipsk_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Registration {self.name} ({self.status})>"


class InviteCode(Base):
    """Invite code model for controlled registration access."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    # Usage limits
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses: Mapped[int] = mapped_column(Integer, default=0)

    # Validity
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadata
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<InviteCode {self.code} ({self.uses}/{self.max_uses})>"

    @property
    def is_valid(self) -> bool:
        """Check if the invite code is still valid."""
        if not self.is_active:
            return False
        if self.uses >= self.max_uses:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True


class SplashAccess(Base):
    """Log of devices accessing the splash portal from Meraki."""

    __tablename__ = "splash_access"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Client device info (from Meraki)
    client_mac: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Access point info (from Meraki)
    ap_mac: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ap_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ap_tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    node_mac: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Network info
    ssid_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    network_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # URLs from Meraki
    login_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    continue_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    access_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Request metadata
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<SplashAccess {self.client_mac} @ {self.accessed_at}>"


class PortalSetting(Base):
    """Portal settings stored in database for dynamic reload without restart."""

    __tablename__ = "portal_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Value type hint for frontend
    value_type: Mapped[str] = mapped_column(
        String(20), 
        default="string"
    )  # string, int, bool, json, encrypted
    
    # Metadata
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # meraki, branding, auth, network
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<PortalSetting {self.key}>"
