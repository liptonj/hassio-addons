"""Pydantic schemas for settings management."""

from pydantic import BaseModel, Field  # type: ignore[import-untyped]


class AllSettings(BaseModel):
    """Complete settings model for viewing/editing."""

    # Run Mode
    run_mode: str = "standalone"
    is_standalone: bool = True
    editable_settings: bool = True

    # Meraki API
    meraki_api_key: str = Field(default="", description="Meraki Dashboard API Key")
    meraki_org_id: str = Field(
        default="",
        description="Selected Meraki organization ID",
    )

    # Home Assistant
    ha_url: str = "http://supervisor/core"
    ha_token: str = ""

    # Branding
    property_name: str = "My Property"
    logo_url: str = ""
    primary_color: str = "#00A4E4"

    # Network Settings
    default_network_id: str = ""
    default_ssid_number: int = 0
    default_group_policy_id: str = ""  # Group policy for registered users with iPSK
    default_group_policy_name: str = "WPN-Users"  # Name for registered users policy
    default_guest_group_policy_id: str = ""  # Group policy for guest/default PSK users
    default_guest_group_policy_name: str = "WPN-Guests"  # Name for guest policy
    standalone_ssid_name: str = "Demo-WiFi"
    default_ssid_psk: str = ""  # Default PSK for guest SSID (encrypted)
    splash_page_url: str = ""  # Custom splash page URL for the SSID

    # Registration Modes (can enable multiple)
    auth_open_registration: bool = True           # Open registration, immediate access
    auth_open_registration_approval: bool = False # Open registration + admin approval required
    auth_account_only: bool = False               # Existing accounts only, no new registrations
    auth_invite_code_account: bool = False        # Invite code required to create account
    auth_invite_code_only: bool = False           # Enter code → get PSK (no account needed)

    # Legacy fields (for backwards compatibility)
    auth_self_registration: bool = True   # Maps to auth_open_registration
    auth_invite_codes: bool = True        # Maps to auth_invite_code_account
    
    # Verification
    auth_email_verification: bool = False
    auth_sms_verification: bool = False

    # Registration
    require_unit_number: bool = False  # Optional by default, can be enabled in settings
    unit_source: str = "manual_list"
    manual_units: str = '["101", "102", "201", "202"]'

    # IPSK Settings
    default_ipsk_duration_hours: int = 0
    passphrase_length: int = 12

    # AUP Settings
    aup_enabled: bool = False
    aup_text: str = ""
    aup_url: str = ""
    aup_version: int = 1

    # Custom Registration Fields
    custom_registration_fields: str = "[]"  # JSON string

    # PSK Customization
    allow_custom_psk: bool = True
    psk_min_length: int = 8
    psk_max_length: int = 63

    # Invite Code Settings
    invite_code_email_restriction: bool = False
    invite_code_single_use: bool = False

    # Authentication Methods
    auth_method_local: bool = True
    auth_method_oauth: bool = False
    auth_method_invite_code: bool = True
    auth_method_self_registration: bool = True

    # Universal Login
    universal_login_enabled: bool = True
    show_login_method_selector: bool = False

    # iPSK Expiration Management
    ipsk_expiration_check_enabled: bool = True
    ipsk_expiration_check_interval_hours: int = 1
    ipsk_cleanup_action: str = "soft_delete"
    ipsk_expiration_warning_days: str = "7,3,1"
    ipsk_expiration_email_enabled: bool = False

    # Admin
    admin_notification_email: str = ""
    admin_username: str = "admin"
    admin_password: str = ""  # Only for updates
    admin_password_hash: str = ""

    # SMTP Email Settings
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_from_email: str = ""
    smtp_from_name: str = "WiFi Portal"
    smtp_timeout: int = 10

    # Security
    secret_key: str = ""
    access_token_expire_minutes: int = 30

    # Database
    database_url: str = "sqlite:///./meraki_wpn_portal.db"

    # OAuth
    enable_oauth: bool = False
    oauth_provider: str = "none"
    oauth_admin_only: bool = False
    oauth_auto_provision: bool = True
    oauth_callback_url: str = ""

    # Duo
    duo_client_id: str = ""
    duo_client_secret: str = ""
    duo_api_hostname: str = ""

    # Entra ID
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""

    # Cloudflare Zero Trust Tunnel
    cloudflare_enabled: bool = False
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_tunnel_id: str = ""
    cloudflare_tunnel_name: str = ""
    cloudflare_zone_id: str = ""
    cloudflare_zone_name: str = ""
    cloudflare_hostname: str = ""
    cloudflare_local_url: str = "http://localhost:8080"

    # CORS Configuration
    cors_origins: str = "*"

    # RADIUS Server Settings
    radius_enabled: bool = False
    radius_server_host: str = "localhost"
    radius_hostname: str = ""  # Public hostname (e.g., radius.example.com)
    radius_auth_port: int = 1812
    radius_acct_port: int = 1813
    radius_coa_port: int = 3799  # CoA/Disconnect port
    radius_radsec_enabled: bool = True
    radius_radsec_port: int = 2083
    radius_shared_secret: str = ""
    radius_radsec_ca_cert: str = ""
    radius_radsec_server_cert: str = ""
    radius_radsec_server_key: str = ""
    radius_radsec_auto_generate: bool = True
    radius_cert_source: str = "selfsigned"  # selfsigned, letsencrypt, cloudflare
    radius_api_url: str = "http://localhost:8000"
    radius_api_token: str = ""


class SettingsUpdate(BaseModel):
    """Partial settings update - all fields optional."""

    # Run Mode
    run_mode: str | None = None

    # Meraki API
    meraki_api_key: str | None = None
    meraki_org_id: str | None = None

    # Home Assistant
    ha_url: str | None = None
    ha_token: str | None = None

    # Branding
    property_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None

    # Network Settings
    default_network_id: str | None = None
    default_ssid_number: int | None = None
    default_group_policy_id: str | None = None
    default_group_policy_name: str | None = None
    default_guest_group_policy_id: str | None = None
    default_guest_group_policy_name: str | None = None
    default_ssid_psk: str | None = None  # Default PSK for guest SSID
    standalone_ssid_name: str | None = None
    splash_page_url: str | None = None

    # Registration Modes
    auth_open_registration: bool | None = None
    auth_open_registration_approval: bool | None = None
    auth_account_only: bool | None = None
    auth_invite_code_account: bool | None = None
    auth_invite_code_only: bool | None = None
    
    # Legacy fields (for backwards compatibility)
    auth_self_registration: bool | None = None
    auth_invite_codes: bool | None = None
    
    # Verification
    auth_email_verification: bool | None = None
    auth_sms_verification: bool | None = None

    # Registration
    require_unit_number: bool | None = None
    unit_source: str | None = None
    manual_units: str | None = None

    # IPSK Settings
    default_ipsk_duration_hours: int | None = None
    passphrase_length: int | None = None

    # AUP Settings
    aup_enabled: bool | None = None
    aup_text: str | None = None
    aup_url: str | None = None
    aup_version: int | None = None

    # Custom Registration Fields
    custom_registration_fields: str | None = None

    # PSK Customization
    allow_custom_psk: bool | None = None
    psk_min_length: int | None = None
    psk_max_length: int | None = None

    # Invite Code Settings
    invite_code_email_restriction: bool | None = None
    invite_code_single_use: bool | None = None

    # Authentication Methods
    auth_method_local: bool | None = None
    auth_method_oauth: bool | None = None
    auth_method_invite_code: bool | None = None
    auth_method_self_registration: bool | None = None

    # Universal Login
    universal_login_enabled: bool | None = None
    show_login_method_selector: bool | None = None

    # iPSK Expiration Management
    ipsk_expiration_check_enabled: bool | None = None
    ipsk_expiration_check_interval_hours: int | None = None
    ipsk_cleanup_action: str | None = None
    ipsk_expiration_warning_days: str | None = None
    ipsk_expiration_email_enabled: bool | None = None

    # SMTP Email Settings
    smtp_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    smtp_use_ssl: bool | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None
    smtp_timeout: int | None = None

    # Admin
    admin_notification_email: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None  # Will be hashed

    # Security
    secret_key: str | None = None
    access_token_expire_minutes: int | None = None

    # Database
    database_url: str | None = None

    # OAuth
    enable_oauth: bool | None = None
    oauth_provider: str | None = None
    oauth_admin_only: bool | None = None
    oauth_auto_provision: bool | None = None
    oauth_callback_url: str | None = None

    # Duo
    duo_client_id: str | None = None
    duo_client_secret: str | None = None
    duo_api_hostname: str | None = None

    # Entra ID
    entra_client_id: str | None = None
    entra_client_secret: str | None = None
    entra_tenant_id: str | None = None

    # Cloudflare Zero Trust Tunnel
    cloudflare_enabled: bool | None = None
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_tunnel_id: str | None = None
    cloudflare_tunnel_name: str | None = None
    cloudflare_zone_id: str | None = None
    cloudflare_zone_name: str | None = None
    cloudflare_hostname: str | None = None
    cloudflare_local_url: str | None = None

    # CORS Configuration
    cors_origins: str | None = None

    # RADIUS Server Settings
    radius_enabled: bool | None = None
    radius_server_host: str | None = None
    radius_hostname: str | None = None
    radius_auth_port: int | None = None
    radius_acct_port: int | None = None
    radius_coa_port: int | None = None
    radius_radsec_enabled: bool | None = None
    radius_radsec_port: int | None = None
    radius_shared_secret: str | None = None
    radius_radsec_ca_cert: str | None = None
    radius_radsec_server_cert: str | None = None
    radius_radsec_server_key: str | None = None
    radius_radsec_auto_generate: bool | None = None
    radius_cert_source: str | None = None
    radius_api_url: str | None = None
    radius_api_token: str | None = None


class SettingsResponse(BaseModel):
    """Settings response with masked secrets."""

    success: bool
    message: str
    settings: dict
    requires_restart: bool = False
