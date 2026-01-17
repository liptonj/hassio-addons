// Settings type definition
export interface AllSettings {
  // Run Mode
  run_mode: string
  is_standalone: boolean
  editable_settings: boolean

  // Meraki API
  meraki_api_key: string
  meraki_org_id: string

  // Home Assistant
  ha_url: string
  ha_token: string

  // Branding
  property_name: string
  logo_url: string
  primary_color: string

  // Network Settings
  default_network_id: string
  default_ssid_number: number
  default_group_policy_id: string
  default_group_policy_name: string
  default_guest_group_policy_id: string
  default_guest_group_policy_name: string
  standalone_ssid_name: string
  default_ssid_psk: string
  splash_page_url: string

  // User Registration
  allow_user_signup: boolean
  allow_guest_registration: boolean

  // Auth Methods
  auth_self_registration: boolean
  auth_invite_codes: boolean
  auth_email_verification: boolean
  auth_sms_verification: boolean

  // Registration
  require_unit_number: boolean
  unit_source: string
  manual_units: string

  // IPSK Settings
  default_ipsk_duration_hours: number
  passphrase_length: number

  // AUP Settings
  aup_enabled: boolean
  aup_text: string
  aup_url: string
  aup_version: number

  // Custom Registration Fields
  custom_registration_fields: string

  // PSK Customization
  allow_custom_psk: boolean
  psk_min_length: number
  psk_max_length: number

  // Invite Code Settings
  invite_code_email_restriction: boolean
  invite_code_single_use: boolean

  // Authentication Methods
  auth_method_local: boolean
  auth_method_oauth: boolean
  auth_method_invite_code: boolean
  auth_method_self_registration: boolean

  // Universal Login
  universal_login_enabled: boolean
  show_login_method_selector: boolean

  // iPSK Expiration Management
  ipsk_expiration_check_enabled: boolean
  ipsk_expiration_check_interval_hours: number
  ipsk_cleanup_action: string
  ipsk_expiration_warning_days: string
  ipsk_expiration_email_enabled: boolean

  // SMTP Email Settings
  smtp_enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password: string
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
  smtp_from_email: string
  smtp_from_name: string
  smtp_timeout: number

  // Admin
  admin_notification_email: string
  admin_username: string
  admin_password: string
  admin_password_hash: string

  // Security
  secret_key: string
  access_token_expire_minutes: number

  // Database
  database_url: string

  // OAuth
  enable_oauth: boolean
  oauth_provider: string
  oauth_admin_only: boolean
  oauth_auto_provision: boolean
  oauth_callback_url: string

  // Duo
  duo_client_id: string
  duo_client_secret: string
  duo_api_hostname: string

  // Entra ID
  entra_client_id: string
  entra_client_secret: string
  entra_tenant_id: string

  // Cloudflare Zero Trust Tunnel
  cloudflare_enabled: boolean
  cloudflare_api_token: string
  cloudflare_account_id: string
  cloudflare_tunnel_id: string
  cloudflare_tunnel_name: string
  cloudflare_zone_id: string
  cloudflare_zone_name: string
  cloudflare_hostname: string
  cloudflare_local_url: string

  // CORS Configuration
  cors_origins: string

  // RADIUS Server Settings
  radius_enabled: boolean
  radius_server_host: string
  radius_auth_port: number
  radius_acct_port: number
  radius_radsec_enabled: boolean
  radius_radsec_port: number
  radius_shared_secret: string
  radius_radsec_ca_cert: string
  radius_radsec_server_cert: string
  radius_radsec_server_key: string
  radius_radsec_auto_generate: boolean
  radius_api_url: string
  radius_api_token: string

  // EAP-TLS / Certificate Settings
  eap_tls_enabled: boolean
  cert_auto_renewal_enabled: boolean
  cert_validity_days: number
  ca_provider: string
  internal_ca_name: string
  internal_ca_country: string
  internal_ca_state: string
  internal_ca_locality: string
  internal_ca_organization: string
  internal_ca_organizational_unit: string
  letsencrypt_email: string
  letsencrypt_production: boolean
  external_ca_cert: string
  meraki_radsec_ca_url: string
}
