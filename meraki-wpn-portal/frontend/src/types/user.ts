export interface User {
  id: number
  name: string
  email: string
  unit?: string
  area_id?: string
  ipsk_id?: string
  ipsk_name?: string
  is_active: boolean
  created_at: string
  // Approval workflow fields
  approval_status?: 'pending' | 'approved' | 'rejected'
  approval_notes?: string
  approved_at?: string
  approved_by?: string
  preferred_auth_method?: 'ipsk' | 'eap-tls' | 'both'
}

export interface RegistrationRequest {
  name: string
  email: string
  unit?: string
  area_id?: string
  invite_code?: string
  mac_address?: string
  // NEW FIELDS
  custom_passphrase?: string
  accept_aup?: boolean
  custom_fields?: Record<string, string>
  user_agent?: string
  // EAP-TLS FIELDS
  auth_method?: 'ipsk' | 'eap-tls' | 'both'
  certificate_password?: string
}

export interface DeviceInfo {
  device_type: string
  device_os: string
  device_model: string
  device_name?: string
}

export interface RegistrationResponse {
  success: boolean
  ipsk_id?: string | null
  ipsk_name?: string | null
  ssid_name: string
  passphrase?: string | null
  qr_code?: string | null
  wifi_config_string?: string | null
  // NEW FIELDS
  is_returning_user?: boolean
  device_info?: DeviceInfo
  mobileconfig_url?: string
  // EAP-TLS FIELDS
  auth_method?: string
  certificate_id?: number | null
  certificate_download_url?: string | null
  // APPROVAL WORKFLOW FIELDS
  pending_approval?: boolean
  pending_message?: string
}

export interface CustomField {
  id: string
  label: string
  type: 'text' | 'select' | 'number'
  required: boolean
  options?: string[]
}

export interface PortalOptions {
  property_name: string
  logo_url: string
  primary_color: string
  unit_source: 'ha_areas' | 'manual_list' | 'free_text'
  units: Array<{ area_id: string; name: string }>
  require_unit_number: boolean
  auth_methods: {
    self_registration: boolean
    invite_codes: boolean
    email_verification: boolean
    local: boolean
    oauth: boolean
  }
  // NEW FIELDS
  aup_enabled: boolean
  aup_text: string
  aup_url: string
  aup_version: number
  custom_fields: CustomField[]
  allow_custom_psk: boolean
  psk_requirements: {
    min_length: number
    max_length: number
  }
  invite_code_email_restriction: boolean
  invite_code_single_use: boolean
  universal_login_enabled: boolean
  show_login_method_selector: boolean
  // EAP-TLS FIELDS
  auth_ipsk_enabled?: boolean
  auth_eap_enabled?: boolean
  // REGISTRATION MODE
  registration_mode?: 'open' | 'invite_only' | 'approval_required'
}

// Invite Code Validation
export interface InviteCodeValidation {
  valid: boolean
  error?: string
  code_info?: {
    max_uses: number
    uses: number
    remaining_uses: number
    expires_at?: string
    note?: string
  }
}

// Approval workflow types
export interface ApprovalRequest {
  notes?: string
}

export interface ApprovalResponse {
  success: boolean
  message: string
  user: {
    id: number
    email: string
    name: string
    approval_status: string
    approved_at?: string
    approved_by?: string
    ipsk_name?: string
    ssid_name?: string
    approval_notes?: string
  }
  credentials?: {
    passphrase: string
    ssid_name: string
    ipsk_name: string
  } | null
}

export interface EmailLookupResponse {
  found: boolean
  auth_method: 'local' | 'oauth' | 'none'
  oauth_provider?: 'duo' | 'entra'
  has_account: boolean
  has_ipsk: boolean
  is_admin: boolean
  suggested_action: 'login' | 'signup' | 'sso_redirect'
}

export interface UserDevice {
  id: number
  mac_address: string
  device_type: string
  device_os: string
  device_model: string
  device_name?: string
  registered_at: string
  last_seen_at?: string
  is_active: boolean
}

export interface QRToken {
  token: string
  public_url: string
  expires_at: string
}

export interface ChangePSKResponse {
  success: boolean
  new_passphrase: string
  qr_code: string
}
