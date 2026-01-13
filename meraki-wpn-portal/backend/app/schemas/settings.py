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
    default_group_policy_id: str = ""
    default_group_policy_name: str = "WPN-Users"
    standalone_ssid_name: str = "Demo-WiFi"
    default_ssid_psk: str = ""  # Default PSK for guest SSID (encrypted)

    # User Registration
    allow_user_signup: bool = True  # Allow users to create accounts
    allow_guest_registration: bool = True  # Allow registration without account

    # Auth Methods
    auth_self_registration: bool = True
    auth_invite_codes: bool = True
    auth_email_verification: bool = False
    auth_sms_verification: bool = False

    # Registration
    require_unit_number: bool = True
    unit_source: str = "manual_list"
    manual_units: str = '["101", "102", "201", "202"]'

    # IPSK Settings
    default_ipsk_duration_hours: int = 0
    passphrase_length: int = 12

    # Admin
    admin_notification_email: str = ""
    admin_username: str = "admin"
    admin_password: str = ""  # Only for updates
    admin_password_hash: str = ""

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


class SettingsUpdate(BaseModel):
    """Partial settings update - all fields optional."""

    # Run Mode
    run_mode: str | None = None

    # Meraki API
    meraki_api_key: str | None = None

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
    standalone_ssid_name: str | None = None

    # Auth Methods
    auth_self_registration: bool | None = None
    auth_invite_codes: bool | None = None
    auth_email_verification: bool | None = None
    auth_sms_verification: bool | None = None

    # Registration
    require_unit_number: bool | None = None
    unit_source: str | None = None
    manual_units: str | None = None

    # IPSK Settings
    default_ipsk_duration_hours: int | None = None
    passphrase_length: int | None = None

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


class SettingsResponse(BaseModel):
    """Settings response with masked secrets."""

    success: bool
    message: str
    settings: dict
    requires_restart: bool = False
