import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getAllSettings } from './client'

const DEFAULT_RADIUS_API_URL = 'http://localhost:8000'
const SETTINGS_CACHE_TTL_MS = 30000

interface RadiusSettings {
  apiUrl: string
  apiToken: string | null
}

// Extended config with custom properties
interface RadiusRequestConfig extends InternalAxiosRequestConfig {
  skipAuth?: boolean
}

let cachedSettings: RadiusSettings | null = null
let lastSettingsFetchMs = 0

async function loadRadiusSettings(): Promise<RadiusSettings> {
  const now = Date.now()
  if (cachedSettings && now - lastSettingsFetchMs < SETTINGS_CACHE_TTL_MS) {
    return cachedSettings
  }

  try {
    const settings = await getAllSettings()
    const apiUrlValue = [
      settings.radius_api_url,
      settings.radius_api_endpoint,
    ].find((value) => typeof value === 'string' && value.trim().length > 0) as string | undefined

    cachedSettings = {
      apiUrl: apiUrlValue?.trim() || DEFAULT_RADIUS_API_URL,
      apiToken:
        typeof settings.radius_api_token === 'string' && settings.radius_api_token.trim().length > 0
          ? settings.radius_api_token.trim()
          : null,
    }
  } catch (error) {
    cachedSettings = {
      apiUrl: DEFAULT_RADIUS_API_URL,
      apiToken: null,
    }
  }

  lastSettingsFetchMs = now
  return cachedSettings
}

function createMissingTokenError(): Error {
  return new Error(
    'RADIUS API token is missing. Set radius_api_token in the portal settings.'
  )
}

const radiusApi = axios.create({
  baseURL: DEFAULT_RADIUS_API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

radiusApi.interceptors.request.use(async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
  const requestConfig = config as RadiusRequestConfig
  const settings = await loadRadiusSettings()

  config.baseURL = settings.apiUrl

  if (!requestConfig.skipAuth) {
    if (!settings.apiToken) {
      throw createMissingTokenError()
    }
    config.headers.set('Authorization', `Bearer ${settings.apiToken}`)
  }

  return config
})

radiusApi.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    if (error instanceof Error && error.message === createMissingTokenError().message) {
      return Promise.reject(error)
    }

    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An error occurred'
    return Promise.reject(new Error(message))
  }
)

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface NadCapabilities {
  supports_radsec?: boolean
  supports_coa?: boolean
  supports_disconnect?: boolean
  supports_accounting?: boolean
  supports_ipv6?: boolean
  max_sessions?: number | null
}

export interface NadResponse {
  id: number
  name: string
  description?: string | null
  ipaddr: string
  secret: string
  nas_type: string
  vendor?: string | null
  model?: string | null
  location?: string | null
  radsec_enabled: boolean
  radsec_port?: number | null
  require_tls_cert: boolean
  coa_enabled: boolean
  coa_port?: number | null
  require_message_authenticator: boolean
  virtual_server?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  health_status?: {
    is_reachable: boolean
    last_seen?: string | null
    request_count?: number
    success_count?: number
    failure_count?: number
    avg_response_time_ms?: number | null
  } | null
  capabilities?: NadCapabilities | null
}

export interface NadCreate {
  name: string
  ipaddr: string
  secret: string
  nas_type?: string
  description?: string | null
  vendor?: string | null
  model?: string | null
  location?: string | null
  radsec_enabled?: boolean
  radsec_port?: number | null
  require_tls_cert?: boolean
  coa_enabled?: boolean
  coa_port?: number | null
  require_message_authenticator?: boolean
  virtual_server?: string | null
  is_active?: boolean
  capabilities?: NadCapabilities | null
}

export interface NadUpdate {
  name?: string | null
  description?: string | null
  ipaddr?: string | null
  secret?: string | null
  nas_type?: string | null
  vendor?: string | null
  model?: string | null
  location?: string | null
  radsec_enabled?: boolean | null
  radsec_port?: number | null
  require_tls_cert?: boolean | null
  coa_enabled?: boolean | null
  coa_port?: number | null
  require_message_authenticator?: boolean | null
  virtual_server?: string | null
  is_active?: boolean | null
  capabilities?: NadCapabilities | null
}

export interface PolicyResponse {
  id: number
  name: string
  description?: string | null
  priority: number
  group_name?: string | null
  policy_type: string
  match_username?: string | null
  match_mac_address?: string | null
  match_calling_station?: string | null
  match_nas_identifier?: string | null
  match_nas_ip?: string | null
  reply_attributes?: Array<{ attribute: string; operator?: string; value: string }>
  check_attributes?: Array<{ attribute: string; operator?: string; value: string }>
  time_restrictions?: {
    days_of_week?: number[] | null
    time_start?: string | null
    time_end?: string | null
    timezone?: string
  } | null
  vlan_id?: number | null
  vlan_name?: string | null
  bandwidth_limit_up?: number | null
  bandwidth_limit_down?: number | null
  session_timeout?: number | null
  idle_timeout?: number | null
  max_concurrent_sessions?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  usage_count?: number
  last_used?: string | null
}

export interface PolicyCreate {
  name: string
  description?: string | null
  priority?: number
  group_name?: string | null
  policy_type?: string
  match_username?: string | null
  match_mac_address?: string | null
  match_calling_station?: string | null
  match_nas_identifier?: string | null
  match_nas_ip?: string | null
  reply_attributes?: Array<{ attribute: string; operator?: string; value: string }>
  check_attributes?: Array<{ attribute: string; operator?: string; value: string }>
  time_restrictions?: {
    days_of_week?: number[] | null
    time_start?: string | null
    time_end?: string | null
    timezone?: string
  } | null
  vlan_id?: number | null
  vlan_name?: string | null
  bandwidth_limit_up?: number | null
  bandwidth_limit_down?: number | null
  session_timeout?: number | null
  idle_timeout?: number | null
  max_concurrent_sessions?: number | null
  is_active?: boolean
}

export type PolicyUpdate = Partial<PolicyCreate>

export interface PolicyTestRequest {
  username: string
  mac_address?: string | null
  nas_identifier?: string | null
  nas_ip?: string | null
  additional_attributes?: Record<string, unknown> | null
}

export interface PolicyTestResponse {
  matches: boolean
  policy_id?: number | null
  policy_name?: string | null
  reply_attributes: Array<{ attribute: string; operator?: string; value: string }>
  reason?: string | null
}

export interface RadSecConfigResponse {
  id: number
  name: string
  description?: string | null
  listen_address: string
  listen_port: number
  tls_min_version: string
  tls_max_version: string
  cipher_list: string
  certificate_file: string
  private_key_file: string
  ca_certificate_file: string
  require_client_cert: boolean
  verify_client_cert: boolean
  verify_depth: number
  crl_file?: string | null
  check_crl: boolean
  ocsp_enable: boolean
  ocsp_url?: string | null
  max_connections: number
  connection_timeout: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  server_cert_info?: {
    subject: string
    issuer: string
    valid_from: string
    valid_until: string
    is_expired: boolean
    days_until_expiry: number
    serial_number: string
    fingerprint_sha256: string
  } | null
  ca_cert_info?: {
    subject: string
    issuer: string
    valid_from: string
    valid_until: string
    is_expired: boolean
    days_until_expiry: number
    serial_number: string
    fingerprint_sha256: string
  } | null
}

export type RadSecConfigCreate = Omit<RadSecConfigResponse, 'id' | 'created_at' | 'updated_at'>
export type RadSecConfigUpdate = Partial<RadSecConfigCreate>

// MAC Bypass Configuration
export interface MacBypassConfigResponse {
  id: number
  name: string
  description?: string | null
  mac_addresses: string[]
  bypass_mode: 'whitelist' | 'blacklist'
  require_registration: boolean
  registered_policy_id?: number | null
  unregistered_policy_id?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  // Policy names for display
  registered_policy_name?: string | null
  unregistered_policy_name?: string | null
}

export interface MacBypassConfigCreate {
  name: string
  description?: string | null
  mac_addresses?: string[]
  bypass_mode?: 'whitelist' | 'blacklist'
  require_registration?: boolean
  registered_policy_id?: number | null
  unregistered_policy_id?: number | null
  is_active?: boolean
}

export type MacBypassConfigUpdate = Partial<MacBypassConfigCreate>

// Unlang Policy (Authorization Policies with conditions and profile links)
export interface UnlangPolicyResponse {
  id: number
  name: string
  description?: string | null
  priority: number
  policy_type: string
  section: string
  condition_type: string
  condition_attribute?: string | null
  condition_operator: string
  condition_value?: string | null
  sql_condition?: string | null
  additional_conditions?: Array<{
    attribute: string
    operator: string
    value: string
  }> | null
  condition_logic: string
  action_type: string
  authorization_profile_id?: number | null
  module_name?: string | null
  custom_unlang?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  // Profile name for display
  authorization_profile_name?: string | null
  // Usage info
  used_by_mac_bypass?: string[]
  used_by_eap_methods?: string[]
}

export interface UnlangPolicyCreate {
  name: string
  description?: string | null
  priority?: number
  policy_type?: string
  section?: string
  condition_type?: string
  condition_attribute?: string | null
  condition_operator?: string
  condition_value?: string | null
  sql_condition?: string | null
  additional_conditions?: Array<{
    attribute: string
    operator: string
    value: string
  }> | null
  condition_logic?: string
  action_type?: string
  authorization_profile_id?: number | null
  module_name?: string | null
  custom_unlang?: string | null
  is_active?: boolean
}

export type UnlangPolicyUpdate = Partial<UnlangPolicyCreate>

// PSK (Pre-Shared Key) Configuration
export interface PskConfigResponse {
  id: number
  name: string
  description?: string | null
  psk_type: 'generic' | 'user'
  generic_passphrase?: string | null
  auth_policy_id?: number | null
  default_group_policy?: string | null
  default_vlan_id?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string | null
  // Policy name for display
  auth_policy_name?: string | null
}

export interface PskConfigCreate {
  name: string
  description?: string | null
  psk_type?: 'generic' | 'user'
  generic_passphrase?: string | null
  auth_policy_id?: number | null
  default_group_policy?: string | null
  default_vlan_id?: number | null
  is_active?: boolean
}

export type PskConfigUpdate = Partial<PskConfigCreate>

// EAP Configuration
export interface EapConfigResponse {
  id: number
  name: string
  description?: string | null
  default_eap_type: string
  enabled_methods: string[]
  tls_min_version: string
  tls_max_version: string
  is_active: boolean
}

export interface EapMethodResponse {
  id: number
  method_name: string
  is_enabled: boolean
  settings?: Record<string, unknown> | null
  auth_attempts: number
  auth_successes: number
  auth_failures: number
  success_rate: number
  success_policy_id?: number | null
  failure_policy_id?: number | null
  success_policy_name?: string | null
  failure_policy_name?: string | null
}

export interface EapMethodUpdate {
  is_enabled?: boolean
  settings?: Record<string, unknown> | null
  success_policy_id?: number | null
  failure_policy_id?: number | null
}

export interface CertificateGenerateRequest {
  common_name: string
  organization?: string | null
  country?: string | null
  validity_days?: number
  key_size?: number
}

export interface CertificateGenerateResponse {
  success: boolean
  message: string
  certificate_path?: string | null
  key_path?: string | null
  certificate_info?: {
    subject: string
    issuer: string
    valid_from: string
    valid_until: string
    is_expired: boolean
    days_until_expiry: number
    serial_number: string
    fingerprint_sha256: string
  } | null
}

export interface UdnAssignmentResponse {
  id: number
  udn_id: number
  mac_address: string
  user_id?: number | null
  registration_id?: number | null
  ipsk_id?: string | null
  user_name?: string | null
  user_email?: string | null
  unit?: string | null
  network_id?: string | null
  ssid_number?: number | null
  is_active: boolean
  note?: string | null
  created_at: string
  updated_at: string
  last_auth_at?: string | null
}

export interface UdnAssignmentCreate {
  mac_address: string
  user_id?: number | null
  registration_id?: number | null
  ipsk_id?: string | null
  user_name?: string | null
  user_email?: string | null
  unit?: string | null
  network_id?: string | null
  ssid_number?: number | null
  note?: string | null
  udn_id?: number | null
}

export interface UdnAssignmentUpdate extends Partial<UdnAssignmentCreate> {
  is_active?: boolean | null
}

export interface AvailableUdnResponse {
  udn_id: number
  total_assigned: number
  total_available: number
}

export interface HealthResponse {
  status: string
  timestamp: string
  radius_running: boolean
  portal_db_connected: boolean
  config_files_exist: boolean
}

export interface ConfigStatusResponse {
  [key: string]: unknown
}

export interface ReloadResponse {
  success: boolean
  message: string
  reloaded: boolean
}

export interface StatsResponse {
  total_clients: number
  active_clients: number
  total_assignments: number
  active_assignments: number
  udn_utilization_percent: number
  recent_authentications: number
}

export async function listNads(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
  search?: string
}): Promise<PaginatedResponse<NadResponse>> {
  const { data } = await radiusApi.get('/api/nads', { params })
  return data
}

export async function createNad(payload: NadCreate): Promise<NadResponse> {
  const { data } = await radiusApi.post('/api/nads', payload)
  return data
}

export async function updateNad(nadId: number, payload: NadUpdate): Promise<NadResponse> {
  const { data } = await radiusApi.put(`/api/nads/${nadId}`, payload)
  return data
}

export async function deleteNad(nadId: number): Promise<void> {
  await radiusApi.delete(`/api/nads/${nadId}`)
}

export async function listPolicies(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
  group_name?: string
  policy_type?: string
}): Promise<PaginatedResponse<PolicyResponse>> {
  const { data } = await radiusApi.get('/api/policies', { params })
  return data
}

export async function createPolicy(payload: PolicyCreate): Promise<PolicyResponse> {
  const { data } = await radiusApi.post('/api/policies', payload)
  return data
}

export async function updatePolicy(policyId: number, payload: PolicyUpdate): Promise<PolicyResponse> {
  const { data } = await radiusApi.put(`/api/policies/${policyId}`, payload)
  return data
}

export async function deletePolicy(policyId: number): Promise<void> {
  await radiusApi.delete(`/api/policies/${policyId}`)
}

export async function testPolicy(
  policyId: number,
  payload: PolicyTestRequest
): Promise<PolicyTestResponse> {
  const { data } = await radiusApi.post(`/api/policies/${policyId}/test`, payload)
  return data
}

export async function listRadSecConfigs(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
}): Promise<PaginatedResponse<RadSecConfigResponse>> {
  const { data } = await radiusApi.get('/api/radsec/configs', { params })
  return data
}

export async function createRadSecConfig(
  payload: RadSecConfigCreate
): Promise<RadSecConfigResponse> {
  const { data } = await radiusApi.post('/api/radsec/configs', payload)
  return data
}

export async function updateRadSecConfig(
  configId: number,
  payload: RadSecConfigUpdate
): Promise<RadSecConfigResponse> {
  const { data } = await radiusApi.put(`/api/radsec/configs/${configId}`, payload)
  return data
}

export async function deleteRadSecConfig(configId: number): Promise<void> {
  await radiusApi.delete(`/api/radsec/configs/${configId}`)
}

export async function listRadSecCertificates(): Promise<Record<string, unknown>> {
  const { data } = await radiusApi.get('/api/radsec/certificates')
  return data
}

export async function generateRadSecCertificates(
  payload: CertificateGenerateRequest
): Promise<CertificateGenerateResponse> {
  const { data } = await radiusApi.post('/api/radsec/certificates/generate', payload)
  return data
}

export async function verifyRadSecCertificate(params: {
  certificate_path: string
  ca_path?: string | null
}): Promise<Record<string, unknown>> {
  const { data } = await radiusApi.get('/api/radsec/certificates/verify', { params })
  return data
}

export async function listUdnAssignments(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
  search?: string
  user_id?: number
  network_id?: string
}): Promise<PaginatedResponse<UdnAssignmentResponse>> {
  const { data } = await radiusApi.get('/api/udn-assignments', { params })
  return data
}

export async function createUdnAssignment(
  payload: UdnAssignmentCreate
): Promise<UdnAssignmentResponse> {
  const { data } = await radiusApi.post('/api/udn-assignments', payload)
  return data
}

export async function updateUdnAssignment(
  assignmentId: number,
  payload: UdnAssignmentUpdate
): Promise<UdnAssignmentResponse> {
  const { data } = await radiusApi.put(`/api/udn-assignments/${assignmentId}`, payload)
  return data
}

export async function deleteUdnAssignment(assignmentId: number): Promise<void> {
  await radiusApi.delete(`/api/udn-assignments/${assignmentId}`)
}

export async function getAvailableUdn(): Promise<AvailableUdnResponse> {
  const { data } = await radiusApi.get('/api/udn-assignments/available-udn')
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await radiusApi.get('/health', { skipAuth: true } as RadiusRequestConfig)
  return data
}

export async function getConfigStatus(): Promise<ConfigStatusResponse> {
  const { data } = await radiusApi.get('/api/config/status')
  return data
}

export async function reloadConfig(force = false): Promise<ReloadResponse> {
  const { data } = await radiusApi.post('/api/reload', { force })
  return data
}

export async function getStats(): Promise<StatsResponse> {
  const { data } = await radiusApi.get('/api/stats')
  return data
}

export async function getRecentLogs(lines = 100): Promise<{ entries: unknown[]; total_lines: number }> {
  const { data } = await radiusApi.get('/api/logs/recent', { params: { lines } })
  return data
}

export async function getConfigFiles(): Promise<Array<{ filename: string; path: string; content: string }>> {
  const { data } = await radiusApi.get('/api/config/files')
  return data
}

// MAC Bypass Configuration API
export async function listMacBypassConfigs(activeOnly = true): Promise<MacBypassConfigResponse[]> {
  const { data } = await radiusApi.get('/api/v1/mac-bypass/config', {
    params: { active_only: activeOnly },
  })
  return data
}

export async function getMacBypassConfig(configId: number): Promise<MacBypassConfigResponse> {
  const { data } = await radiusApi.get(`/api/v1/mac-bypass/config/${configId}`)
  return data
}

export async function createMacBypassConfig(
  config: MacBypassConfigCreate
): Promise<MacBypassConfigResponse> {
  const { data } = await radiusApi.post('/api/v1/mac-bypass/config', config)
  return data
}

export async function updateMacBypassConfig(
  configId: number,
  config: MacBypassConfigUpdate
): Promise<MacBypassConfigResponse> {
  const { data } = await radiusApi.put(`/api/v1/mac-bypass/config/${configId}`, config)
  return data
}

export async function deleteMacBypassConfig(configId: number): Promise<void> {
  await radiusApi.delete(`/api/v1/mac-bypass/config/${configId}`)
}

// Unlang Policy API (Authorization Policies)
export async function listUnlangPolicies(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
  policy_type?: string
  section?: string
}): Promise<PaginatedResponse<UnlangPolicyResponse>> {
  const { data } = await radiusApi.get('/api/v1/unlang-policies', { params })
  return data
}

export async function getUnlangPolicy(policyId: number): Promise<UnlangPolicyResponse> {
  const { data } = await radiusApi.get(`/api/v1/unlang-policies/${policyId}`)
  return data
}

export async function createUnlangPolicy(
  payload: UnlangPolicyCreate
): Promise<UnlangPolicyResponse> {
  const { data } = await radiusApi.post('/api/v1/unlang-policies', payload)
  return data
}

export async function updateUnlangPolicy(
  policyId: number,
  payload: UnlangPolicyUpdate
): Promise<UnlangPolicyResponse> {
  const { data } = await radiusApi.put(`/api/v1/unlang-policies/${policyId}`, payload)
  return data
}

export async function deleteUnlangPolicy(policyId: number): Promise<void> {
  await radiusApi.delete(`/api/v1/unlang-policies/${policyId}`)
}

// PSK Configuration API
export async function listPskConfigs(activeOnly = false): Promise<PskConfigResponse[]> {
  const { data } = await radiusApi.get('/api/v1/psk/config', {
    params: { active_only: activeOnly },
  })
  return data
}

export async function getPskConfig(configId: number): Promise<PskConfigResponse> {
  const { data } = await radiusApi.get(`/api/v1/psk/config/${configId}`)
  return data
}

export async function createPskConfig(
  config: PskConfigCreate
): Promise<PskConfigResponse> {
  const { data } = await radiusApi.post('/api/v1/psk/config', config)
  return data
}

export async function updatePskConfig(
  configId: number,
  config: PskConfigUpdate
): Promise<PskConfigResponse> {
  const { data } = await radiusApi.put(`/api/v1/psk/config/${configId}`, config)
  return data
}

export async function deletePskConfig(configId: number): Promise<void> {
  await radiusApi.delete(`/api/v1/psk/config/${configId}`)
}

// EAP Configuration API
export async function listEapConfigs(): Promise<EapConfigResponse[]> {
  const { data } = await radiusApi.get('/api/v1/eap/config')
  return data
}

export async function listEapMethods(): Promise<EapMethodResponse[]> {
  const { data } = await radiusApi.get('/api/v1/eap/methods')
  return data
}

export async function updateEapMethod(
  methodId: number,
  update: EapMethodUpdate
): Promise<EapMethodResponse> {
  const { data } = await radiusApi.patch(`/api/v1/eap/methods/${methodId}`, update)
  return data
}

export async function enableEapMethod(methodName: string): Promise<{ success: boolean; message: string }> {
  const { data } = await radiusApi.post(`/api/v1/eap/methods/${methodName}/enable`)
  return data
}

export async function disableEapMethod(methodName: string): Promise<{ success: boolean; message: string }> {
  const { data } = await radiusApi.post(`/api/v1/eap/methods/${methodName}/disable`)
  return data
}

export default radiusApi
