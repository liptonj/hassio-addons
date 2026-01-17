export interface IPSK {
  id: string
  name: string
  network_id: string
  ssid_number: number
  ssid_name?: string
  status: 'active' | 'expired' | 'revoked'
  group_policy_id?: string
  group_policy_name?: string  // Human-readable group policy name
  groupPolicyId?: string  // Meraki API field name
  psk_group_id?: string  // WPN/UPN Group ID - unique per iPSK when WPN enabled
  pskGroupId?: string  // Meraki API field name
  expires_at?: string
  expiresAt?: string  // Meraki API field name
  created_at?: string
  associated_device_id?: string
  associated_device_name?: string
  associated_area_id?: string
  associated_area_name?: string
  associated_user?: string
  associated_unit?: string
  connected_clients?: number
  last_seen?: string
  passphrase?: string  // Only populated when revealed
}

export interface IPSKCreate {
  name: string
  network_id?: string
  ssid_number?: number
  passphrase?: string
  duration_hours?: number
  group_policy_id?: string
  associated_device_id?: string
  associated_area_id?: string
  associated_user?: string
  associated_unit?: string
}

export interface IPSKReveal {
  id: string
  name: string
  passphrase: string
  ssid_name?: string
  qr_code?: string
  wifi_config_string?: string
}

export interface IPSKStats {
  total_ipsks: number
  active_ipsks: number
  expired_ipsks: number
  revoked_ipsks: number
  online_devices: number
  registrations_today: number
}
