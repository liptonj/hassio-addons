import axios, { AxiosError } from 'axios'
import type { RegistrationRequest, RegistrationResponse, PortalOptions } from '../types/user'
import type { IPSK, IPSKCreate, IPSKReveal, IPSKStats } from '../types/ipsk'
import type { Area, Device, InviteCode, InviteCodeCreate } from '../types/device'

export interface IPSKOptions {
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
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred'
    return Promise.reject(new Error(message))
  }
)

// ============================================================================
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

export function getUserToken(): string | null {
  return localStorage.getItem('user_token')
}

export function clearUserToken(): void {
  localStorage.removeItem('user_token')
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
  const { data } = await api.get<IPSKStats>('/admin/stats')
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
  const { data } = await api.get('/admin/settings')
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
  success: boolean
  results: Record<string, { success: boolean; message: string }>
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
  wpn_ready: boolean
  issues: string[]
  message: string
}

export interface WPNConfigureResult {
  success: boolean
  message: string
  splash_url?: string
  default_psk?: string
  group_policy_name?: string
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

export async function configureSSIDForWPN(groupPolicyName: string = 'WPN-Users'): Promise<WPNConfigureResult> {
  const { data } = await api.post<WPNConfigureResult>('/admin/wpn/configure-ssid', null, {
    params: { group_policy_name: groupPolicyName }
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
  const { data } = await api.post(`/admin/users/${userId}/toggle-admin`)
  return data
}

export default api
