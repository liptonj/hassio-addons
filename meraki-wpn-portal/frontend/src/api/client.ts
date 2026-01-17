import axios, { AxiosError } from 'axios'
import type { RegistrationRequest, RegistrationResponse, PortalOptions, EmailLookupResponse, UserDevice, QRToken, ChangePSKResponse } from '../types/user'
import type { IPSK, IPSKCreate, IPSKReveal, IPSKStats } from '../types/ipsk'
import type { Area, Device, InviteCode, InviteCodeCreate } from '../types/device'
import { isTokenExpired, needsTokenRefresh } from '../utils/token'

export interface IPSKOptions {
  organizations: Array<{ id: string; name: string }>
  networks: Array<{ id: string; name: string }>
  ssids: Array<{ number: number; name: string }>
  group_policies: Array<{ id: string; name: string }>
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests if available
api.interceptors.request.use((config) => {
  const adminToken = localStorage.getItem('admin_token')
  const userToken = localStorage.getItem('user_token')
  const url = config.url || ''
  const isAdminEndpoint = url.startsWith('/admin')
  const isUserEndpoint =
    url.startsWith('/auth/user') ||
    url.startsWith('/user') ||
    url.startsWith('/devices')

  // Check token expiration before adding to request
  if (isAdminEndpoint && adminToken) {
    if (isTokenExpired(adminToken)) {
      // Token expired - clear it and redirect to login
      localStorage.removeItem('admin_token')
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
      return Promise.reject(new Error('Token expired. Please log in again.'))
    }
    config.headers.Authorization = `Bearer ${adminToken}`
  } else if (isUserEndpoint && userToken) {
    if (isTokenExpired(userToken)) {
      // Token expired - clear it
      localStorage.removeItem('user_token')
      if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/user-auth')) {
        window.location.href = '/login'
      }
      return Promise.reject(new Error('Token expired. Please log in again.'))
    }
    config.headers.Authorization = `Bearer ${userToken}`
  }
  return config
})

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    // Handle 401 Unauthorized - token expired or invalid
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      // Clear tokens
      localStorage.removeItem('admin_token')
      localStorage.removeItem('user_token')
      
      // Redirect to login if not already there
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
        return Promise.reject(new Error('Session expired. Please log in again.'))
      }
    }
    const message = error.response?.data?.detail || error.message || 'An error occurred'
    return Promise.reject(new Error(message))
  }
)

// ============================================================================
// Auth Token Helpers
// ============================================================================

/**
 * Get the current auth token (admin or user token)
 * Used by other API clients (like radiusClient) to authenticate requests
 */
export function getAuthToken(): string | null {
  const adminToken = localStorage.getItem('admin_token')
  const userToken = localStorage.getItem('user_token')
  
  // Prefer admin token if available
  if (adminToken) {
    return adminToken
  }
  if (userToken) {
    return userToken
  }
  return null
}

// Public API
// ============================================================================

export async function getPortalOptions(): Promise<PortalOptions> {
  const { data } = await api.get<PortalOptions>('/options')
  return data
}

export async function getPublicAreas(): Promise<Area[]> {
  const { data } = await api.get<Area[]>('/areas')
  return data
}

export async function register(request: RegistrationRequest): Promise<RegistrationResponse> {
  const { data } = await api.post<RegistrationResponse>('/register', request)
  return data
}

// Invite Code Validation
export interface InviteCodeValidationResult {
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

export async function validateInviteCode(code: string): Promise<InviteCodeValidationResult> {
  const { data } = await api.post<InviteCodeValidationResult>('/invite-code/validate', null, {
    params: { code }
  })
  return data
}

// ============================================================================
// User Authentication
// ============================================================================

export interface UserInfo {
  id: number
  email: string
  name: string
  unit?: string
  is_admin: boolean
  has_ipsk: boolean
  ipsk_name?: string
  ssid_name?: string
}

export interface UserAuthResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

export async function userSignup(params: {
  email: string
  password: string
  name: string
  unit?: string
}): Promise<UserAuthResponse> {
  const { data } = await api.post<UserAuthResponse>('/auth/user/signup', params)
  // Store the user token
  localStorage.setItem('user_token', data.access_token)
  return data
}

export async function userLogin(email: string, password: string): Promise<UserAuthResponse> {
  const { data } = await api.post<UserAuthResponse>('/auth/user/login', { email, password })
  // Store the user token
  localStorage.setItem('user_token', data.access_token)
  return data
}

export async function getCurrentUser(): Promise<UserInfo> {
  const { data } = await api.get<UserInfo>('/auth/user/me')
  return data
}

export interface AutoIPSKResponse {
  success: boolean
  ipsk_id: string
  ipsk_name: string
  ssid_name: string
  passphrase: string
  qr_code: string
  wifi_config_string: string
}

export async function createUserIPSK(): Promise<AutoIPSKResponse> {
  const { data } = await api.post<AutoIPSKResponse>('/auth/user/create-ipsk')
  return data
}

export function getUserToken(): string | null {
  return localStorage.getItem('user_token')
}

export function clearUserToken(): void {
  localStorage.removeItem('user_token')
  localStorage.removeItem('admin_token')
  // Redirect to login if not already there
  if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/user-auth')) {
    window.location.href = '/login'
  }
}

export async function grantNetworkAccess(
  options: {
    loginUrl?: string
    grantUrl?: string
    clientMac?: string
    continueUrl?: string
  }
): Promise<{ success: boolean; message?: string; redirect_url?: string; continue_url?: string; error?: string }> {
  const { data } = await api.post('/grant-access', null, {
    params: {
      login_url: options.loginUrl,
      base_grant_url: options.grantUrl,
      client_mac: options.clientMac,
      continue_url: options.continueUrl,
    },
  })
  return data
}

export async function getMyNetwork(email: string, verificationCode?: string): Promise<{
  ipsk_name: string
  ssid_name: string
  passphrase: string
  status: string
  connected_devices: number
  qr_code?: string
}> {
  const params = new URLSearchParams({ email })
  if (verificationCode) {
    params.append('verification_code', verificationCode)
  }
  const { data } = await api.get(`/my-network?${params.toString()}`)
  return data
}

// ============================================================================
// Universal Login & Enhanced User API
// ============================================================================

export async function lookupEmail(email: string): Promise<EmailLookupResponse> {
  const { data } = await api.post<EmailLookupResponse>('/auth/lookup-email', { email })
  return data
}

export async function registerDevice(
  mac_address: string, 
  user_agent: string, 
  device_name?: string
): Promise<{
  device_id: number
  device_type: string
  device_os: string
  device_os_version: string
  browser_name: string
  device_model: string
  device_vendor: string
  registered: boolean
}> {
  const { data } = await api.post('/devices/register', { mac_address, user_agent, device_name })
  return data
}

export async function changeUserPassword(
  current_password: string, 
  new_password: string
): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/user/change-password', { current_password, new_password })
  return data
}

export async function changeUserPSK(custom_passphrase?: string): Promise<ChangePSKResponse> {
  const { data } = await api.post<ChangePSKResponse>('/user/change-psk', { custom_passphrase })
  return data
}

export async function getUserDevices(): Promise<UserDevice[]> {
  const { data } = await api.get<UserDevice[]>('/user/devices')
  return data
}

export async function removeUserDevice(mac: string): Promise<void> {
  await api.delete(`/user/devices/${mac}`)
}

export async function createQRToken(ipsk_id: string): Promise<QRToken> {
  const { data } = await api.post<QRToken>('/wifi-qr/create', { ipsk_id })
  return data
}

// ============================================================================
// Admin API - Authentication
// ============================================================================

export async function login(username: string, password: string): Promise<string> {
  const { data } = await api.post<{ access_token: string }>('/auth/login', {
    username,
    password,
  })
  return data.access_token
}

export async function getAdminToken(haToken: string): Promise<string> {
  const { data } = await api.post<{ access_token: string }>('/auth/token', null, {
    params: { ha_token: haToken },
  })
  return data.access_token
}

// ============================================================================
// Admin API - IPSK Management
// ============================================================================

export async function listIPSKs(filters?: {
  network_id?: string
  ssid_number?: number
  status?: string
}): Promise<IPSK[]> {
  const { data } = await api.get<IPSK[]>('/admin/ipsks', { params: filters })
  return data
}

export async function createIPSK(ipsk: IPSKCreate): Promise<IPSK> {
  const { data } = await api.post<IPSK>('/admin/ipsks', ipsk)
  return data
}

export async function getIPSK(id: string): Promise<IPSK> {
  const { data } = await api.get<IPSK>(`/admin/ipsks/${id}`)
  return data
}

export async function updateIPSK(id: string, updates: Partial<IPSKCreate>): Promise<IPSK> {
  const { data } = await api.put<IPSK>(`/admin/ipsks/${id}`, updates)
  return data
}

export async function deleteIPSK(id: string): Promise<void> {
  await api.delete(`/admin/ipsks/${id}`)
}

export async function revokeIPSK(id: string): Promise<void> {
  await api.post(`/admin/ipsks/${id}/revoke`)
}

export async function revealIPSKPassphrase(id: string): Promise<IPSKReveal> {
  const { data } = await api.post<IPSKReveal>(`/admin/ipsks/${id}/reveal-passphrase`)
  return data
}

export async function getIPSKStats(): Promise<IPSKStats> {
  const { data } = await api.get<IPSKStats>('/admin/ipsk/stats')
  return data
}

// ============================================================================
// Admin API - Device & Area Management
// ============================================================================

export async function listDevices(): Promise<Device[]> {
  const { data } = await api.get<Device[]>('/admin/ha/devices')
  return data
}

export async function listAreas(): Promise<Area[]> {
  const { data } = await api.get<Area[]>('/admin/ha/areas')
  return data
}

export async function associateIPSK(ipskId: string, association: {
  device_id?: string
  area_id?: string
}): Promise<void> {
  await api.post(`/admin/ipsks/${ipskId}/associate`, association)
}

export async function getIPSKOptions(): Promise<IPSKOptions> {
  const { data } = await api.get<IPSKOptions>('/admin/ipsk-options')
  return data
}

// ============================================================================
// Admin API - Invite Codes
// ============================================================================

export async function listInviteCodes(options?: {
  include_expired?: boolean
  include_inactive?: boolean
}): Promise<InviteCode[]> {
  const { data } = await api.get<InviteCode[]>('/admin/invite-codes', { params: options })
  return data
}

export async function createInviteCode(code: InviteCodeCreate): Promise<InviteCode> {
  const { data } = await api.post<InviteCode>('/admin/invite-codes', code)
  return data
}

export async function deleteInviteCode(code: string): Promise<void> {
  await api.delete(`/admin/invite-codes/${code}`)
}

export async function deactivateInviteCode(code: string): Promise<void> {
  await api.post(`/admin/invite-codes/${code}/deactivate`)
}

// ============================================================================
// Admin API - Dashboard & Settings
// ============================================================================

export async function getDashboardData(): Promise<{
  stats: IPSKStats & { online_now: number }
  meraki_status?: {
    status: 'online' | 'offline' | 'unknown'
    error: string | null
  }
  recent_activity: Array<{
    type: string
    name: string
    unit?: string
    status: string
    timestamp: string
  }>
}> {
  const { data } = await api.get('/admin/dashboard')
  return data
}

export async function getSettings(): Promise<Record<string, unknown>> {
  // Use /settings/all - there is no /settings endpoint
  const { data } = await api.get('/admin/settings/all')
  return data
}

export async function getAllSettings(): Promise<Record<string, unknown>> {
  const { data } = await api.get('/admin/settings/all')
  return data
}

export async function updateSettings(settings: Record<string, unknown>): Promise<{
  success: boolean
  message: string
  settings: Record<string, unknown>
  requires_restart: boolean
}> {
  const { data } = await api.put('/admin/settings/all', settings)
  return data
}

export async function testConnection(testSettings: Record<string, unknown>): Promise<{
  overall_success: boolean
  tests: Record<string, { success: boolean; message: string; [key: string]: unknown }>
}> {
  const { data } = await api.post('/admin/settings/test-connection', testSettings)
  return data
}

export async function resetSettings(): Promise<{
  success: boolean
  message: string
}> {
  const { data } = await api.post('/admin/settings/reset')
  return data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{
  success: boolean
  message: string
}> {
  const { data } = await api.post('/admin/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}

export async function listRegistrations(options?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<{
  total: number
  registrations: Array<{
    id: number
    name: string
    email: string
    unit?: string
    status: string
    ipsk_id?: string
    created_at: string
    completed_at?: string
  }>
}> {
  const { data } = await api.get('/admin/registrations', { params: options })
  return data
}

// ============================================================================
// Admin API - WPN Configuration
// ============================================================================

export interface WPNSSIDStatus {
  ssid_number: number
  ssid_name: string
  enabled: boolean
  auth_mode: string
  ipsk_configured: boolean
  wpn_enabled: boolean
  configuration_complete: boolean  // All API-configurable settings applied
  wpn_ready: boolean  // Fully ready including manual WPN enable
  overall_status: 'ready' | 'config_complete' | 'needs_wpn' | 'needs_config'  // For UI display
  issues: string[]  // Critical issues that prevent configuration
  warnings?: string[]  // Warnings (e.g., WPN not enabled manually)
  message: string
}

export interface WPNConfigureResult {
  success: boolean
  message: string
  splash_url?: string
  ssid_name?: string  // The actual SSID name from Meraki
  default_psk?: string
  default_ipsk_created?: boolean  // Whether the default iPSK was created in Meraki
  group_policy_name?: string
  group_policy_action?: 'created' | 'updated'  // Track if policy was created or updated
  guest_group_policy_name?: string
  guest_group_policy_id?: string  // The actual Meraki group policy ID
  guest_group_policy_action?: 'created' | 'updated' | null  // Track guest policy action
  splash_bypass_enabled?: boolean  // Confirm splash bypass is enabled
  result: {
    ssid: {
      number: number
      name: string
      enabled: boolean
      authMode: string
      wpaEncryptionMode: string
      ipAssignmentMode: string
      splashPage?: string
    }
    group_policy: {
      groupPolicyId: string
      name: string
    } | null
    group_policy_id: string | null
    manual_step_required: boolean
    message: string
  }
}

export async function getWPNSSIDStatus(): Promise<WPNSSIDStatus> {
  const { data } = await api.get<WPNSSIDStatus>('/admin/wpn/ssid-status')
  return data
}

export interface WPNValidationCheck {
  name: string
  passed: boolean
  value: string
}

export interface WPNValidationResult {
  valid: boolean
  checks: WPNValidationCheck[]
  issues: string[]
  summary: string
}

export async function validateWPNSetup(): Promise<WPNValidationResult> {
  const { data } = await api.get<WPNValidationResult>('/admin/wpn/validate')
  return data
}

export interface WPNConfigureOptions {
  groupPolicyName?: string
  guestGroupPolicyName?: string
  splashUrl?: string
  ssidName?: string
  defaultPsk?: string
}

export async function configureSSIDForWPN(
  options: WPNConfigureOptions = {}
): Promise<WPNConfigureResult> {
  const params: Record<string, string> = {}
  if (options.groupPolicyName) params.group_policy_name = options.groupPolicyName
  if (options.guestGroupPolicyName) params.guest_group_policy_name = options.guestGroupPolicyName
  if (options.splashUrl) params.splash_url = options.splashUrl
  if (options.ssidName) params.ssid_name = options.ssidName
  if (options.defaultPsk) params.default_psk = options.defaultPsk
  
  const { data } = await api.post<WPNConfigureResult>('/admin/wpn/configure-ssid', null, {
    params
  })
  return data
}

export async function createWPNGroupPolicy(name: string): Promise<{
  success: boolean
  message: string
  group_policy: { groupPolicyId: string; name: string }
}> {
  const { data } = await api.post('/admin/wpn/group-policies', null, {
    params: { name }
  })
  return data
}

// =============================================================================
// Cloudflare Zero Trust Tunnel
// =============================================================================

export interface CloudflareOptions {
  success: boolean
  error?: string
  tunnels: Array<{
    id: string
    name: string
    status: string
    label: string
  }>
  zones: Array<{
    id: string
    name: string
    label: string
  }>
}

export interface CloudflareTunnelConfig {
  success: boolean
  tunnel: {
    id: string
    name: string
    status: string
  }
  config: {
    config: {
      ingress: Array<{
        hostname?: string
        service: string
        path?: string
      }>
    }
  }
}

export interface CloudflareConfigureResult {
  success: boolean
  message: string
  tunnel_name: string
  hostname: string
  local_url: string
  dns_created: boolean
  instructions: string[]
}

export async function testCloudflareConnection(
  apiToken: string,
  accountId?: string
): Promise<{
  success: boolean
  message?: string
  error?: string
  accounts?: Array<{ id: string; name: string }>
}> {
  const { data } = await api.post('/admin/cloudflare/test-connection', {
    api_token: apiToken,
    account_id: accountId || undefined
  })
  return data
}

export async function getCloudflareOptions(
  apiToken?: string,
  accountId?: string
): Promise<CloudflareOptions> {
  const params: Record<string, string> = {}
  if (apiToken) params.api_token = apiToken
  if (accountId) params.account_id = accountId

  const { data } = await api.get<CloudflareOptions>('/admin/cloudflare/options', { params })
  return data
}

export async function getCloudfareTunnelConfig(tunnelId: string): Promise<CloudflareTunnelConfig> {
  const { data } = await api.get<CloudflareTunnelConfig>(`/admin/cloudflare/tunnel/${tunnelId}/config`)
  return data
}

export async function configureCloudfareTunnel(
  tunnelId: string,
  zoneId: string,
  hostname: string,
  localUrl: string = 'http://localhost:8080',
  apiToken?: string,
  accountId?: string
): Promise<CloudflareConfigureResult> {
  const params: Record<string, string> = {
    tunnel_id: tunnelId,
    zone_id: zoneId,
    hostname: hostname,
    local_url: localUrl
  }
  if (apiToken) params.api_token = apiToken
  if (accountId) params.account_id = accountId

  const { data } = await api.post<CloudflareConfigureResult>('/admin/cloudflare/tunnel/configure', null, {
    params
  })
  return data
}

export async function disconnectCloudfareTunnel(): Promise<{
  success: boolean
  message: string
}> {
  const { data } = await api.delete('/admin/cloudflare/tunnel/disconnect')
  return data
}

// =============================================================================
// Admin User Management
// =============================================================================

export interface AdminUserInfo {
  id: number
  email: string
  name: string
  unit?: string
  is_admin: boolean
  is_active: boolean
  has_ipsk: boolean
  ipsk_name?: string
  ssid_name?: string
  created_at?: string
  last_login_at?: string
}

export interface UserCreateRequest {
  email: string
  name: string
  password: string
  unit?: string
  is_admin?: boolean
}

export interface UserUpdateRequest {
  name?: string
  unit?: string
  is_admin?: boolean
  is_active?: boolean
  password?: string
}

export async function getUsers(
  skip = 0,
  limit = 100
): Promise<{ success: boolean; total: number; users: AdminUserInfo[] }> {
  const { data } = await api.get('/admin/users', { params: { skip, limit } })
  return data
}

export async function getUser(userId: number): Promise<{ success: boolean; user: AdminUserInfo }> {
  const { data } = await api.get(`/admin/users/${userId}`)
  return data
}

export async function createUser(
  userData: UserCreateRequest
): Promise<{ success: boolean; message: string; user: AdminUserInfo }> {
  const { data } = await api.post('/admin/users', userData)
  return data
}

export async function updateUser(
  userId: number,
  userData: UserUpdateRequest
): Promise<{ success: boolean; message: string; user: AdminUserInfo }> {
  const { data } = await api.put(`/admin/users/${userId}`, userData)
  return data
}

export async function deleteUser(
  userId: number
): Promise<{ success: boolean; message: string }> {
  const { data } = await api.delete(`/admin/users/${userId}`)
  return data
}

export async function toggleUserAdmin(
  userId: number
): Promise<{ success: boolean; message: string; user: AdminUserInfo }> {
  const { data} = await api.post(`/admin/users/${userId}/toggle-admin`)
  return data
}

// ============================================================================
// Admin API - User Approval Workflow
// ============================================================================

export interface PendingUser {
  id: number
  email: string
  name: string
  unit?: string
  area_id?: string
  preferred_auth_method?: string
  approval_status: string
  created_at: string
}

export async function getPendingUsers(): Promise<{
  total: number
  users: PendingUser[]
}> {
  const { data } = await api.get('/admin/users/pending')
  return data
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

export async function approveUser(
  userId: number,
  notes?: string
): Promise<ApprovalResponse> {
  const { data } = await api.post<ApprovalResponse>(
    `/admin/users/${userId}/approve`,
    notes ? { notes } : undefined
  )
  return data
}

export async function rejectUser(
  userId: number,
  notes?: string
): Promise<{ success: boolean; message: string; user: { id: number; email: string; name: string; approval_status: string; approval_notes?: string } }> {
  const { data } = await api.post(`/admin/users/${userId}/reject`, notes ? { notes } : undefined)
  return data
}

export interface DeviceInfo {
  id: number
  mac_address: string
  device_type: string
  device_os: string
  device_model: string
  device_name: string | null
  registered_at: string
  last_seen_at: string | null
  is_active: boolean
}

export async function getAdminUserDevices(
  userId: number
): Promise<{ success: boolean; total: number; devices: DeviceInfo[] }> {
  const { data } = await api.get(`/admin/users/${userId}/devices`)
  return data
}

export async function updateUserIpsk(
  userId: number,
  newPassphrase: string
): Promise<{ success: boolean; message: string }> {
  const { data } = await api.put(`/admin/users/${userId}/ipsk`, null, {
    params: { new_passphrase: newPassphrase }
  })
  return data
}

export async function resetUserPassword(
  userId: number,
  newPassword: string
): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post(`/admin/users/${userId}/reset-password`, null, {
    params: { new_password: newPassword }
  })
  return data
}

// ============================================================================
// RADIUS Management
// ============================================================================

export interface RADIUSConfig {
  radius_enabled: boolean
  radius_server_host: string
  radius_auth_port: number
  radius_acct_port: number
  radius_radsec_port: number
  radius_radsec_enabled: boolean
  radius_shared_secret: string
  radius_radsec_ca_cert: string
  radius_radsec_server_cert: string
  radius_radsec_server_key: string
  radius_radsec_auto_generate: boolean
}

export interface RADIUSClient {
  id: number
  name: string
  ipaddr: string
  shared_secret: string
  nas_type: string
  network_id: string
  network_name: string | null
  require_message_authenticator: boolean
  is_active: boolean
  created_at: string
}

export interface UDNAssignment {
  id: number
  mac_address: string
  udn_id: number
  user_email: string | null
  unit_number: string | null
  assigned_by: string
  is_active: boolean
  created_at: string
}

export interface UDNPoolStatus {
  total: number
  assigned: number
  available: number
  range_start: number
  range_end: number
}

export async function getRADIUSConfig(): Promise<RADIUSConfig> {
  const { data } = await api.get<RADIUSConfig>('/admin/radius/config')
  return data
}

export async function updateRADIUSConfig(config: Partial<RADIUSConfig>): Promise<{ success: boolean; message: string }> {
  const { data } = await api.put('/admin/radius/config', config)
  return data
}

export async function generateRADIUSCertificates(): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/admin/radius/certificates/generate')
  return data
}

export async function syncToFreeRADIUS(params: { sync_clients: boolean; sync_users: boolean; reload_radius: boolean }): Promise<{
  success: boolean
  clients_synced: number
  users_synced: number
  errors: string[]
  reloaded: boolean
  message: string
}> {
  const { data } = await api.post('/admin/radius/sync', params)
  return data
}

export async function getRADIUSClients(): Promise<{ clients: RADIUSClient[] }> {
  const { data } = await api.get('/admin/radius/clients')
  return data
}

export async function createRADIUSClient(client: {
  name: string
  ip_address: string
  shared_secret: string
  nas_type: string
  network_id: string
  network_name: string
  require_message_authenticator: boolean
}): Promise<{ success: boolean; message: string; id: number }> {
  const { data } = await api.post('/admin/radius/clients', client)
  return data
}

export async function deleteRADIUSClient(clientId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await api.delete(`/admin/radius/clients/${clientId}`)
  return data
}

export interface MerakiDevice {
  serial: string
  name: string
  model: string
  lanIp: string | null
  mac: string
  tags: string
  networkId: string
}

export async function getMerakiNetworkDevices(
  networkId: string
): Promise<{ success: boolean; total: number; devices: MerakiDevice[] }> {
  const { data } = await api.get(`/admin/meraki/networks/${networkId}/devices`)
  return data
}

export interface BulkNadCreate {
  network_id: string
  device_serials: string[]
  shared_secret: string
  nas_type?: string
}

export interface BulkNadResult {
  created: Array<{
    id: number
    serial: string
    name: string
    ip: string
    model: string
    mac: string
  }>
  failed: Array<{
    serial: string
    name: string
    ip: string
    error: string
  }>
  skipped: Array<{
    serial: string
    name: string
    ip?: string
    reason: string
  }>
}

export async function bulkCreateNads(
  bulkData: BulkNadCreate
): Promise<BulkNadResult> {
  const { data } = await api.post('/admin/radius/nads/bulk-from-devices', bulkData)
  return data
}

export async function getUDNAssignments(): Promise<{ assignments: UDNAssignment[] }> {
  const { data } = await api.get('/admin/radius/udn/assignments')
  return data
}

export async function assignUDN(params: { mac_address: string; user_email?: string; unit_number?: string }): Promise<{
  success: boolean
  message: string
  udn_id: number
  mac_address: string
}> {
  const { data } = await api.post('/admin/radius/udn/assignments', params)
  return data
}

export async function revokeUDN(mac_address: string): Promise<{ success: boolean; message: string }> {
  const { data} = await api.delete(`/admin/radius/udn/${encodeURIComponent(mac_address)}`)
  return data
}

// ============================================================================
// Email / SMTP API
// ============================================================================

export interface SendTestEmailRequest {
  recipient: string
}

export interface SendTestEmailResponse {
  success: boolean
  message: string
}

export async function sendTestEmail(recipient: string): Promise<SendTestEmailResponse> {
  const { data } = await api.post<SendTestEmailResponse>('/admin/email/test', { recipient })
  return data
}

// ============================================================================
// Authentication Configuration API
// ============================================================================

export interface AuthConfig {
  eap_tls_enabled: boolean
  ipsk_enabled: boolean
  allow_user_auth_choice: boolean
  ca_provider: 'internal' | 'letsencrypt' | 'external' | 'meraki'
  cert_validity_days: number
  cert_auto_renewal_enabled: boolean
  cert_renewal_threshold_days: number
  cert_key_size: number
  cert_signature_algorithm: 'sha256' | 'sha384' | 'sha512'
  ca_initialized: boolean
  ca_info?: {
    id: number
    name: string
    fingerprint: string
    valid_from: string
    valid_until: string
    certificates_issued: number
    certificates_revoked: number
  } | null
}

export async function getAuthConfig(): Promise<AuthConfig> {
  const { data } = await api.get<AuthConfig>('/admin/auth-config')
  return data
}

export async function updateAuthConfig(config: Partial<AuthConfig>): Promise<{ success: boolean; message: string }> {
  const { data } = await api.patch('/admin/auth-config', config)
  return data
}

export async function initializeCA(params: {
  common_name: string
  organization: string
}): Promise<{ ca_id: number; common_name: string; fingerprint: string; valid_from: string; valid_until: string; message: string }> {
  const { data } = await api.post('/admin/ca/initialize', params)
  return data
}

export async function downloadRootCA(): Promise<Blob> {
  const { data } = await api.get('/admin/ca/root-certificate', {
    responseType: 'blob',
  })
  return data
}

export async function regenerateCA(params: {
  common_name: string
  organization: string
}): Promise<{ success: boolean; message: string; warning: string; old_ca_id?: number | null; new_ca_id: number }> {
  const { data } = await api.post('/admin/ca/regenerate', params)
  return data
}

export async function getCAStats(): Promise<{
  certificates_issued: number
  certificates_revoked: number
  certificates_active: number
  certificates_expired: number
  certificates_expiring_soon: number
}> {
  const { data } = await api.get('/admin/ca/stats')
  return data
}

// ============================================================================
// User Certificates API
// ============================================================================

export interface UserCertificate {
  id: number
  user_email: string
  common_name: string
  serial_number: string
  fingerprint: string
  status: 'active' | 'revoked' | 'expired'
  issued_at: string
  valid_until: string
  auto_renew: boolean
  download_count: number
  last_downloaded_at?: string
}

export async function getUserCertificates(): Promise<{ certificates: UserCertificate[] }> {
  const { data } = await api.get('/user/certificates')
  return data
}

export async function downloadCertificate(id: number, format: 'pkcs12' | 'pem' = 'pkcs12'): Promise<Blob> {
  const { data } = await api.get(`/user/certificates/${id}/download`, {
    params: { format },
    responseType: 'blob',
  })
  return data
}

export async function revokeCertificate(id: number, reason: string = 'user_requested'): Promise<{ success: boolean; message: string }> {
  const { data } = await api.delete(`/user/certificates/${id}`, {
    params: { reason },
  })
  return data
}

export async function renewCertificate(id: number, passphrase: string): Promise<{ success: boolean; message: string; new_certificate_id: number }> {
  const { data } = await api.post(`/user/certificates/${id}/renew`, { passphrase })
  return data
}

export async function getUDNPoolStatus(): Promise<UDNPoolStatus> {
  const { data } = await api.get<UDNPoolStatus>('/admin/radius/udn/pool')
  return data
}

export default api
