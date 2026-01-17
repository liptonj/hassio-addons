"""Database models - shared with portal."""

# Import models from portal's database models
# In production, these would be in a shared package
# For now, we'll duplicate the essential models

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""


class RadiusClient(Base):
    """RADIUS client configuration for Meraki networks."""

    __tablename__ = "radius_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Client identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    ipaddr: Mapped[str] = mapped_column(String(100), nullable=False)  # IP or CIDR
    secret: Mapped[str] = mapped_column(String(255), nullable=False)  # Shared secret
    
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


class RadiusNadExtended(Base):
    """Extended NAD information and capabilities."""

    __tablename__ = "radius_nad_extended"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Link to radius client
    radius_client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("radius_clients.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Device information
    vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # RadSec configuration
    radsec_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    radsec_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_tls_cert: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # CoA configuration
    coa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    coa_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Virtual server
    virtual_server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Capabilities (stored as JSON)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
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

    def __repr__(self) -> str:
        return f"<RadiusNadExtended client_id={self.radius_client_id}>"


# Backward compatibility alias
RadiusClientExtended = RadiusNadExtended


class RadiusNadHealth(Base):
    """NAD health monitoring data."""

    __tablename__ = "radius_nad_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Link to NAD extended
    nad_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("radius_nad_extended.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Health status
    is_reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Statistics
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Last check
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        status = "reachable" if self.is_reachable else "unreachable"
        return f"<RadiusNadHealth nad_id={self.nad_id} {status}>"


class RadiusAuthorizationProfile(Base):
    """Authorization Profile - WHAT to return in RADIUS reply.
    
    This defines the RADIUS attributes returned when a user is authorized:
    - VLAN assignment
    - SGT (Security Group Tag)
    - Group Policy (Filter-Id, Cisco-AVPair)
    - Captive Portal redirect
    - Bandwidth limits
    - Session timeouts
    
    This is separate from the policy logic (RadiusUnlangPolicy) which determines
    WHEN/IF a user should be authorized and which profile to apply.
    
    Note: Table name kept as 'radius_policies' for backward compatibility.
    """

    __tablename__ = "radius_policies"  # Keep original table name for migration compatibility

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Policy identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Priority and grouping
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    policy_type: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    
    # Match conditions (regex supported)
    match_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_calling_station: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_nas_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_nas_ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # RADIUS attributes (stored as JSON arrays)
    reply_attributes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    check_attributes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Time restrictions (stored as JSON)
    time_restrictions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # VLAN assignment
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vlan_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Bandwidth limits (kbps)
    bandwidth_limit_up: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bandwidth_limit_down: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Session controls
    session_timeout: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idle_timeout: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_concurrent_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # PSK and MAC validation settings
    psk_validation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mac_matching_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mac_validation_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_on_psk_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Authorization response fields - Captive Portal
    splash_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url_redirect_acl: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Group Policy - Multiple vendor formats
    unregistered_group_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_group_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_policy_vendor: Mapped[str] = mapped_column(
        String(50), default="meraki", nullable=False
    )
    
    # Meraki-specific: Filter-Id for group policy name
    filter_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Cisco ISE-specific ACL/dACL
    downloadable_acl: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Cisco TrustSec / Meraki Adaptive Policy - Security Group Tag (SGT)
    sgt_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sgt_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # UDN inclusion
    include_udn: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Usage statistics
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
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
        return f"<RadiusAuthorizationProfile {self.name} priority={self.priority}>"


# Backward compatibility alias - existing code can still use RadiusPolicy
RadiusPolicy = RadiusAuthorizationProfile


class RadiusUnlangPolicy(Base):
    """Unlang Policy - The decision logic (WHEN/HOW to authorize).
    
    This generates FreeRADIUS unlang code that determines:
    - IF a user should be allowed (conditions)
    - WHICH authorization profile to apply (actions)
    - Dynamic decisions based on SQL lookups
    
    Example unlang output:
    ```unlang
    # Policy: IPSK Authentication
    if (&User-Name) {
        sql {
            ok = return
            notfound = reject
        }
        
        if (ok) {
            # Apply authorization profile
            &reply += &control.Profile-Attributes
        }
    }
    ```
    
    Per FreeRADIUS v4 documentation:
    https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/unlang/index.html
    """

    __tablename__ = "radius_unlang_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Policy identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Policy execution order (lower = higher priority, evaluated first)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    
    # Policy type / category
    policy_type: Mapped[str] = mapped_column(
        String(50), default="authorization", nullable=False
    )  # 'authorization', 'authentication', 'accounting', 'post-auth'
    
    # Processing section where this policy applies
    section: Mapped[str] = mapped_column(
        String(50), default="authorize", nullable=False
    )  # 'authorize', 'authenticate', 'accounting', 'post-auth', 'pre-proxy', 'post-proxy'
    
    # ======================================================================
    # CONDITION - When should this policy match?
    # ======================================================================
    
    # Condition type: 'attribute', 'sql_lookup', 'module_call', 'custom'
    condition_type: Mapped[str] = mapped_column(
        String(50), default="attribute", nullable=False
    )
    
    # For attribute conditions: attribute name to check
    condition_attribute: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "User-Name", "Calling-Station-Id"
    
    # Operator: '==', '!=', '=~' (regex), '!~', 'exists', 'notexists'
    condition_operator: Mapped[str] = mapped_column(String(20), default="exists", nullable=False)
    
    # Value to compare against (for == and != operators)
    condition_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # For SQL lookup conditions: the SQL query
    # Use %{User-Name}, %{Calling-Station-Id} for attribute expansion
    sql_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g., "SELECT 1 FROM ipsk_registrations WHERE ipsk_id = '%{User-Name}'"
    
    # Additional conditions (AND/OR with primary condition)
    # Stored as JSON: [{"attribute": "NAS-Identifier", "operator": "==", "value": "Meraki-AP"}]
    additional_conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Logical operator between conditions
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND", nullable=False)  # 'AND', 'OR'
    
    # ======================================================================
    # ACTION - What to do when condition matches?
    # ======================================================================
    
    # Action type: 'accept', 'reject', 'apply_profile', 'continue', 'call_module'
    action_type: Mapped[str] = mapped_column(String(50), default="accept", nullable=False)
    
    # Profile to apply (if action_type == 'apply_profile')
    authorization_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Module to call (if action_type == 'call_module')
    module_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "sql", "eap", "ldap"
    
    # Custom unlang code (for advanced policies)
    custom_unlang: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Reply message (for accept/reject)
    reply_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Reject reason (for reject action)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # ======================================================================
    # ELSE ACTION - What to do when condition does NOT match?
    # ======================================================================
    
    else_action_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'continue', 'reject', 'apply_profile', None (no else)
    
    else_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_policies.id", ondelete="SET NULL"),
        nullable=True
    )
    
    else_reply_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # ======================================================================
    # METADATA
    # ======================================================================
    
    # Virtual server this policy applies to (None = default server)
    virtual_server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Usage statistics
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
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
        return f"<RadiusUnlangPolicy {self.name} priority={self.priority} action={self.action_type}>"


class RadiusRadSecConfig(Base):
    """RadSec (RADIUS over TLS) server configuration."""

    __tablename__ = "radius_radsec_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Configuration identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Network configuration
    listen_address: Mapped[str] = mapped_column(String(100), default="0.0.0.0", nullable=False)
    listen_port: Mapped[int] = mapped_column(Integer, default=2083, nullable=False)
    
    # TLS configuration
    tls_min_version: Mapped[str] = mapped_column(String(10), default="1.2", nullable=False)
    tls_max_version: Mapped[str] = mapped_column(String(10), default="1.3", nullable=False)
    cipher_list: Mapped[str] = mapped_column(
        Text,
        default="ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256",
        nullable=False
    )
    
    # Certificate paths
    certificate_file: Mapped[str] = mapped_column(String(255), nullable=False)
    private_key_file: Mapped[str] = mapped_column(String(255), nullable=False)
    ca_certificate_file: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Client certificate validation
    require_client_cert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verify_client_cert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verify_depth: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    
    # Certificate revocation
    crl_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    check_crl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # OCSP
    ocsp_enable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ocsp_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Connection limits
    max_connections: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    connection_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
        return f"<RadiusRadSecConfig {self.name} {self.listen_address}:{self.listen_port}>"


class RadiusRadSecClient(Base):
    """RadSec client certificate configuration."""

    __tablename__ = "radius_radsec_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Client identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Certificate information
    certificate_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    certificate_fingerprint: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Link to radius client (optional)
    radius_client_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Statistics
    connection_count: Mapped[int] = mapped_column(Integer, default=0)
    last_connected: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
        return f"<RadiusRadSecClient {self.name}>"


class RadiusSession(Base):
    """Active RADIUS session tracking."""

    __tablename__ = "radius_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Session identification
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # NAS information
    nas_ip: Mapped[str] = mapped_column(String(100), nullable=False)
    nas_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Station information
    calling_station_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    called_station_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    framed_ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Session timing
    session_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_time: Mapped[int] = mapped_column(Integer, default=0)  # seconds
    
    # Data usage
    input_octets: Mapped[int] = mapped_column(Integer, default=0)
    output_octets: Mapped[int] = mapped_column(Integer, default=0)
    
    # Termination
    terminate_cause: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<RadiusSession {self.session_id} {self.username}>"


class RadiusAuthLog(Base):
    """Authentication attempt logging."""

    __tablename__ = "radius_auth_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # Authentication details
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    
    # NAS information
    nas_ip: Mapped[str] = mapped_column(String(100), nullable=False)
    nas_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Result
    auth_result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # Accept, Reject
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Policy applied
    policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<RadiusAuthLog {self.username} {self.auth_result}>"


class RadiusEapConfig(Base):
    """Global EAP configuration settings."""

    __tablename__ = "radius_eap_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Configuration identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # EAP global settings
    default_eap_type: Mapped[str] = mapped_column(String(20), default="tls", nullable=False)
    timer_expire: Mapped[int] = mapped_column(Integer, default=60)
    ignore_unknown_eap_types: Mapped[bool] = mapped_column(Boolean, default=False)
    cisco_accounting_username_bug: Mapped[bool] = mapped_column(Boolean, default=False)
    max_sessions: Mapped[int] = mapped_column(Integer, default=4096)
    
    # Enabled EAP methods (stored as JSON array)
    enabled_methods: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["tls", "ttls", "peap"]
    
    # TLS configuration
    tls_min_version: Mapped[str] = mapped_column(String(10), default="1.2", nullable=False)
    tls_max_version: Mapped[str] = mapped_column(String(10), default="1.3", nullable=False)
    cipher_list: Mapped[str] = mapped_column(
        Text,
        default="HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4",
        nullable=False
    )
    cipher_server_preference: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Certificate paths
    private_key_file: Mapped[str] = mapped_column(String(500), default="${certdir}/server-key.pem")
    certificate_file: Mapped[str] = mapped_column(String(500), default="${certdir}/server.pem")
    ca_file: Mapped[str] = mapped_column(String(500), default="${certdir}/ca.pem")
    dh_file: Mapped[str] = mapped_column(String(500), default="${certdir}/dh")
    
    # Certificate verification
    check_cert_cn: Mapped[bool] = mapped_column(Boolean, default=True)
    check_crl: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Cache settings
    cache_enable: Mapped[bool] = mapped_column(Boolean, default=True)
    cache_lifetime: Mapped[int] = mapped_column(Integer, default=24)  # hours
    cache_max_entries: Mapped[int] = mapped_column(Integer, default=255)
    
    # TTLS settings
    ttls_default_eap_type: Mapped[str] = mapped_column(String(20), default="mschapv2")
    ttls_copy_request_to_tunnel: Mapped[bool] = mapped_column(Boolean, default=False)
    ttls_use_tunneled_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    ttls_virtual_server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # PEAP settings
    peap_default_eap_type: Mapped[str] = mapped_column(String(20), default="mschapv2")
    peap_copy_request_to_tunnel: Mapped[bool] = mapped_column(Boolean, default=False)
    peap_use_tunneled_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    peap_virtual_server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
        return f"<RadiusEapConfig {self.name}>"


class RadiusEapMethod(Base):
    """Per-method EAP configuration.
    
    Each EAP method (TLS, TTLS, PEAP) can have its own authorization policy
    that determines which profile to apply on successful/failed authentication.
    """

    __tablename__ = "radius_eap_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Link to EAP config
    eap_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("radius_eap_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Method identification
    method_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # tls, ttls, peap, fast
    
    # Method-specific settings (stored as JSON)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Authorization policy for successful authentication
    success_policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_unlang_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Authorization policy for failed authentication (optional)
    failure_policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_unlang_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Statistics
    auth_attempts: Mapped[int] = mapped_column(Integer, default=0)
    auth_successes: Mapped[int] = mapped_column(Integer, default=0)
    auth_failures: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    enabled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<RadiusEapMethod {self.method_name} enabled={self.is_enabled}>"


class RadiusMacBypassConfig(Base):
    """MAC address bypass configuration for authentication.
    
    This is an authentication setting that allows specific MAC addresses
    to bypass normal authentication methods.
    
    Registered MACs (found in device_registrations) use registered_policy_id.
    Unregistered MACs use unregistered_policy_id.
    """

    __tablename__ = "radius_mac_bypass_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Configuration identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # MAC address list (stored as JSON array)
    mac_addresses: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of MAC addresses to bypass
    
    # Bypass mode: 'whitelist' (only these MACs bypass) or 'blacklist' (these MACs don't bypass)
    bypass_mode: Mapped[str] = mapped_column(String(20), default="whitelist", nullable=False)  # 'whitelist' or 'blacklist'
    
    # Conditions for bypass
    require_registration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Authorization policy for registered MAC addresses (found in device_registrations)
    registered_policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_unlang_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Authorization policy for unregistered MAC addresses (not found in device_registrations)
    unregistered_policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_unlang_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
        return f"<RadiusMacBypassConfig {self.name} mode={self.bypass_mode} active={self.is_active}>"


class RadiusPskConfig(Base):
    """Global PSK (Pre-Shared Key) authentication configuration.
    
    Defines authorization policies for PSK-based authentication:
    - Generic PSK: Shared passphrase for all devices
    - User PSK (IPSK): Individual passphrases per user/device
    
    The auth_policy_id determines which authorization policy to apply
    when a device authenticates via PSK.
    """

    __tablename__ = "radius_psk_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Configuration identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # PSK type: 'generic' (shared) or 'user' (per-user IPSK)
    psk_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    
    # Generic PSK passphrase (only used if psk_type == 'generic')
    generic_passphrase: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Authorization policy for PSK-authenticated devices
    auth_policy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_unlang_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Default group policy (Meraki Filter-Id) if no profile specified
    default_group_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Default VLAN if no profile specified
    default_vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
        return f"<RadiusPskConfig {self.name} type={self.psk_type} active={self.is_active}>"


class RadiusUserCertificate(Base):
    """Mirror of portal user certificates for FreeRADIUS validation."""

    __tablename__ = "radius_user_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Certificate identification (synced from portal)
    portal_certificate_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Certificate subject
    subject_common_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_distinguished_name: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Certificate fingerprint for validation
    certificate_fingerprint: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Status (synced from portal)
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True
    )  # active, expired, revoked
    
    # UDN assignment for this certificate
    udn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # File path where certificate is stored
    cert_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Authentication tracking
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authentication_count: Mapped[int] = mapped_column(Integer, default=0)
    last_nas_ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Sync tracking
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<RadiusUserCertificate {self.subject_common_name} ({self.status})>"


class DeviceRegistration(Base):
    """Device registration for Meraki IPSK with RADIUS authentication.
    
    Per Meraki documentation:
    https://documentation.meraki.com/Wireless/Design_and_Configure/Configuration_Guides/Encryption_and_Authentication/IPSK_with_RADIUS_Authentication
    
    This table stores MAC address -> PSK mappings for IPSK authentication.
    When a device connects, Meraki sends the MAC as User-Name, and FreeRADIUS
    looks up the PSK to return via Tunnel-Password attribute.
    
    Authentication Flow:
    1. Client connects to SSID
    2. MR sends RADIUS MAB request with User-Name = client MAC
    3. FreeRADIUS looks up MAC in this table
    4. Returns Access-Accept with:
       - Tunnel-Password = psk
       - Filter-Id = group_policy (for Dashboard group policy)
       - Cisco-AVPair = "udn:private-group-id=<udn_id>" (for WPN)
    5. AP completes 4-way handshake with client using PSK
    """

    __tablename__ = "device_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Device identification
    mac_address: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )  # Format: aa:bb:cc:dd:ee:ff or aa-bb-cc-dd-ee-ff
    
    # PSK for this device (returned via Tunnel-Password)
    psk: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # User information (who registered this device)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Device information
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # laptop, phone, iot, etc.
    
    # Network/SSID this registration is for
    network_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ssid_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Authorization - Group Policy (returned via Filter-Id)
    group_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Dashboard group policy name
    
    # Authorization - UDN for WPN
    udn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Authorization - SGT for TrustSec/Adaptive Policy
    sgt_value: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-65535
    sgt_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Authorization - VLAN
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Link to authorization profile (for additional attributes)
    authorization_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Registration details
    registration_source: Mapped[str] = mapped_column(
        String(50), default="portal", nullable=False
    )  # 'portal', 'api', 'admin', 'import'
    
    # Validity
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    # Usage tracking
    last_auth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_count: Mapped[int] = mapped_column(Integer, default=0)
    last_nas_ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_ap_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
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
        return f"<DeviceRegistration {self.mac_address} user={self.user_email}>"


class IpskRegistration(Base):
    """IPSK (Identity PSK) registration for Meraki.
    
    For Easy PSK authentication (MR 32.1.3+), users can have a unique
    PSK identifier that works across any device they use.
    
    This is different from DeviceRegistration which is MAC-based.
    IPSK allows the same PSK to work on multiple devices for a user.
    """

    __tablename__ = "ipsk_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # IPSK identifier (unique per user)
    ipsk_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )  # Can be email, username, or random ID
    
    # PSK/passphrase for this IPSK
    passphrase: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # User information
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Network/SSID this IPSK is for
    network_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ssid_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Authorization - Group Policy
    group_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Authorization - UDN for WPN
    udn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Authorization - SGT
    sgt_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Link to authorization profile
    authorization_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("radius_policies.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Validity
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    # Usage tracking
    last_auth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_count: Mapped[int] = mapped_column(Integer, default=0)
    
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
        return f"<IpskRegistration {self.ipsk_id} user={self.user_email}>"
