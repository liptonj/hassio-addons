"""SQLAlchemy database models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""


class User(Base):
    """User model for registered residents/guests and admins.
    
    Supports unified authentication: One account for both portal and WiFi access.
    - Portal authentication: email/password (OAuth optional via Duo/Entra)
    - WiFi authentication: radius_username/radius_password_hash (WPA2-Enterprise)
    - WPN authentication: MAC address (assigned to UDN ID in udn_assignments table)
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Portal Authentication - local username/password
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # OAuth/SSO Authentication (optional)
    auth_type: Mapped[str] = mapped_column(String(20), default='local')  # 'local', 'duo', 'entra'
    oauth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # External OAuth user ID

    # RADIUS/WiFi Authentication (NEW - Unified Auth)
    # When enabled, user can authenticate to WiFi using username/password
    radius_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    radius_username: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    radius_password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Separate WiFi password

    # IPSK association (for WPA2-PSK with IPSK)
    ipsk_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ipsk_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted passphrase - stored locally since Meraki API doesn't return it
    ipsk_passphrase_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssid_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # AUP (Acceptable Use Policy) tracking
    accept_aup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aup_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Custom registration fields (JSON string)
    custom_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # iPSK Lifecycle Management
    ipsk_status: Mapped[str] = mapped_column(String(20), default='active')  # active, expired, revoked
    ipsk_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # OAuth provider tracking
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # duo, entra

    # EAP-TLS / Certificate Authentication
    eap_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cert_auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_auth_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ipsk, eap-tls, both
    certificate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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

    # Approval workflow
    approval_status: Mapped[str] = mapped_column(
        String(20),
        default="approved"
    )  # pending, approved, rejected
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

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


class RadiusClient(Base):
    """RADIUS client configuration for Meraki networks."""

    __tablename__ = "radius_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Client identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    ipaddr: Mapped[str] = mapped_column(String(100), nullable=False)  # IP or CIDR
    secret: Mapped[str] = mapped_column(String(255), nullable=False)  # Shared secret (encrypted)
    
    # NAS information
    nas_type: Mapped[str] = mapped_column(String(50), default="other")
    shortname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Meraki integration
    network_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    network_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Configuration
    require_message_authenticator: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<RadiusClient {self.name} ({self.ipaddr})>"


class UdnAssignment(Base):
    """UDN (User Defined Network) ID assignments for WPN segmentation.
    
    UDN is assigned to USER (not MAC address). Relationship: USER → PSK → UDN
    MAC address is optional (for tracking, not required for UDN lookup).
    """

    __tablename__ = "udn_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # UDN ID (2-16777200)
    udn_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    
    # USER assignment (required) - UDN is assigned to user, not MAC
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # MAC address (optional - for tracking, not required for UDN lookup)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    
    # Association with registration/PSK
    registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ipsk_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    
    # User information
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Network information
    network_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ssid_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_auth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        mac_str = f"MAC {self.mac_address}" if self.mac_address else "no MAC"
        return f"<UdnAssignment User {self.user_id} ({mac_str}) -> UDN {self.udn_id}>"


class RadiusAuthLog(Base):
    """RADIUS authentication attempt logs."""

    __tablename__ = "radius_auth_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Authentication request
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    
    # Request source
    nas_ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nas_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Result
    auth_result: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # accept, reject, challenge
    
    # UDN ID returned (if applicable)
    udn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Reply attributes
    reply_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cisco_avpair: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Failure reason (if rejected)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Session information
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calling_station_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    called_station_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Network information
    ssid_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Timestamp
    authenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<RadiusAuthLog {self.username} - {self.auth_result} @ {self.authenticated_at}>"


class DeviceRegistration(Base):
    """Device registration tracking with User-Agent parsing."""

    __tablename__ = "device_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Device identification
    mac_address: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Parsed from User-Agent
    device_type: Mapped[str] = mapped_column(String(50), nullable=True)  # phone, tablet, laptop, desktop, other
    device_os: Mapped[str] = mapped_column(String(50), nullable=True)  # ios, android, macos, windows, linux
    device_os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    browser_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    browser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Apple, Samsung, etc.
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)  # iPhone 15 Pro, Galaxy S23
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full UA string
    
    # Network information
    last_ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    udn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Authentication method tracking
    auth_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ipsk, eap-tls, both
    certificate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_eap: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DeviceRegistration {self.mac_address} - {self.device_type}/{self.device_os}>"


class IPSKExpirationLog(Base):
    """Audit log for iPSK expiration events."""

    __tablename__ = "ipsk_expiration_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ipsk_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Action taken
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # expired, notified, extended, bulk_extended, revoked
    
    # Additional details (JSON string)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Who performed the action
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)  # 'automated' or admin username
    
    # Timestamp
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<IPSKExpirationLog {self.ipsk_id} - {self.action} @ {self.performed_at}>"


class WifiQRToken(Base):
    """Shareable QR code tokens for WiFi credentials."""

    __tablename__ = "wifi_qr_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Token (secure random string)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # Association
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ipsk_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    
    # Usage tracking
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<WifiQRToken {self.token[:8]}... expires {self.expires_at}>"


class CertificateAuthority(Base):
    """Certificate Authority configuration and key storage."""

    __tablename__ = "certificate_authorities"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # CA Identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # CA Type
    ca_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # internal, letsencrypt, external, meraki
    
    # Certificate data (PEM format)
    root_certificate: Mapped[str] = mapped_column(Text, nullable=False)
    root_certificate_fingerprint: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Private key (AES-256 encrypted at rest)
    private_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Certificate chain (for external CAs)
    certificate_chain: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Key information
    key_algorithm: Mapped[str] = mapped_column(String(20), default="RSA")
    key_size: Mapped[int] = mapped_column(Integer, default=4096)
    signature_algorithm: Mapped[str] = mapped_column(String(50), default="sha256WithRSAEncryption")
    
    # Certificate issuance settings
    default_validity_days: Mapped[int] = mapped_column(Integer, default=365)
    auto_renewal_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    renewal_threshold_days: Mapped[int] = mapped_column(Integer, default=30)
    
    # CRL settings
    crl_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    crl_distribution_point: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)  # Primary CA for new certs
    
    # Statistics
    certificates_issued: Mapped[int] = mapped_column(Integer, default=0)
    certificates_revoked: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<CertificateAuthority {self.name} ({self.ca_type})>"


class UserCertificate(Base):
    """User certificates for EAP-TLS authentication."""

    __tablename__ = "user_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Association
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ca_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Certificate data (PEM format)
    certificate: Mapped[str] = mapped_column(Text, nullable=False)
    certificate_fingerprint: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # Private key (AES-256 encrypted)
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    
    # PKCS#12 data (encrypted, for iOS/macOS)
    pkcs12_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    pkcs12_password_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Certificate subject
    subject_common_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_distinguished_name: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Key information
    key_algorithm: Mapped[str] = mapped_column(String(20), default="RSA")
    key_size: Mapped[int] = mapped_column(Integer, default=2048)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True
    )  # active, expired, revoked, renewed
    
    # Renewal tracking
    renewed_by_certificate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    renewal_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Revocation
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Usage tracking
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authentication_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<UserCertificate {self.subject_common_name} ({self.status})>"
    
    @property
    def is_expiring_soon(self) -> bool:
        """Check if certificate expires within 30 days."""
        if self.status != "active":
            return False
        days_until_expiry = (self.valid_until - datetime.now(timezone.utc)).days
        return 0 <= days_until_expiry <= 30


class CertificateRevocation(Base):
    """Certificate Revocation List (CRL) entries."""

    __tablename__ = "certificate_revocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Certificate reference
    certificate_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ca_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Revocation details
    revocation_reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # unspecified, keyCompromise, caCompromise, affiliationChanged, superseded, cessationOfOperation
    
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    revoked_by: Mapped[str] = mapped_column(String(255), nullable=False)  # admin username or 'automated'
    
    # CRL publishing
    published_to_crl: Mapped[bool] = mapped_column(Boolean, default=False)
    crl_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Additional context
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CertificateRevocation serial={self.serial_number} reason={self.revocation_reason}>"


class AuthMethodPreference(Base):
    """User's authentication method preference per device."""

    __tablename__ = "auth_method_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Association
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    
    # Preference
    auth_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # ipsk, eap-tls
    
    # Reason for preference (optional)
    preference_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Timestamps
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AuthMethodPreference user_id={self.user_id} method={self.auth_method}>"

