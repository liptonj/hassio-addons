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
}

export interface RegistrationRequest {
  name: string
  email: string
  unit?: string
  area_id?: string
  invite_code?: string
}

export interface RegistrationResponse {
  success: boolean
  ipsk_id?: string
  ipsk_name: string
  ssid_name: string
  passphrase: string
  qr_code: string
  wifi_config_string: string
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
  }
}
