import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { 
  Shield, 
  Wifi,
  Key,
  UserCheck,
  AlertTriangle,
  CheckCircle,
  Save,
  Trash2,
  Plus,
  Edit,
} from 'lucide-react'
import radiusApi, {
  listUnlangPolicies,
  listPskConfigs,
  createPskConfig,
  updatePskConfig,
  deletePskConfig,
  type UnlangPolicyResponse,
  type PskConfigResponse,
  type PskConfigCreate,
} from '../../api/radiusClient'
import api from '../../api/client'

type TabKey = 'eap' | 'mac-bypass' | 'psk'

interface EapConfig {
  id: number
  name: string
  description?: string
  default_eap_type: string
  enabled_methods: string[]
  tls_min_version: string
  tls_max_version: string
  is_active: boolean
}

interface EapMethod {
  id: number
  method_name: string
  is_enabled: boolean
  auth_attempts: number
  auth_successes: number
  auth_failures: number
  success_policy_id?: number | null
  failure_policy_id?: number | null
  success_policy_name?: string | null
  failure_policy_name?: string | null
}

interface MacBypassConfig {
  id: number
  name: string
  description?: string
  mac_addresses: string[]
  bypass_mode: 'whitelist' | 'blacklist'
  require_registration: boolean
  registered_policy_id?: number | null
  unregistered_policy_id?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  registered_policy_name?: string | null
  unregistered_policy_name?: string | null
}

interface MacBypassFormData {
  name: string
  description: string
  mac_addresses: string[]
  bypass_mode: 'whitelist' | 'blacklist'
  require_registration: boolean
  registered_policy_id: number | null
  unregistered_policy_id: number | null
  is_active: boolean
}

const emptyMacBypassForm: MacBypassFormData = {
  name: '',
  description: '',
  mac_addresses: [],
  bypass_mode: 'whitelist',
  require_registration: false,
  registered_policy_id: null,
  unregistered_policy_id: null,
  is_active: true,
}

export default function AuthenticationConfig() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabKey>('eap')
  const [showMacBypassModal, setShowMacBypassModal] = useState(false)
  const [editingMacBypass, setEditingMacBypass] = useState<MacBypassConfig | null>(null)
  const [macBypassForm, setMacBypassForm] = useState<MacBypassFormData>(emptyMacBypassForm)
  const [macAddressInput, setMacAddressInput] = useState('')
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  // EAP Config Query
  const { data: eapConfigs, isLoading: eapLoading } = useQuery({
    queryKey: ['eap-configs'],
    queryFn: async () => {
      const { data } = await radiusApi.get('/api/v1/eap/config')
      return data as EapConfig[]
    },
  })

  // EAP Methods Query
  const { data: eapMethods, isLoading: methodsLoading } = useQuery({
    queryKey: ['eap-methods'],
    queryFn: async () => {
      const { data } = await radiusApi.get('/api/v1/eap/methods')
      return data as EapMethod[]
    },
  })

  // MAC Bypass Configs Query
  const { data: macBypassConfigs, isLoading: macBypassLoading } = useQuery({
    queryKey: ['mac-bypass-configs'],
    queryFn: async () => {
      const { data } = await radiusApi.get('/api/v1/mac-bypass/config')
      return data as MacBypassConfig[]
    },
  })

  // Authorization Policies Query (for dropdowns)
  const { data: authPolicies } = useQuery({
    queryKey: ['unlang-policies'],
    queryFn: async () => {
      const response = await listUnlangPolicies({ page: 1, page_size: 100 })
      return response.items
    },
  })

  // PSK Configs Query
  const { data: pskConfigs, isLoading: pskLoading } = useQuery({
    queryKey: ['psk-configs'],
    queryFn: async () => {
      return await listPskConfigs()
    },
  })

  // PSK Config Mutations
  const createPskMutation = useMutation({
    mutationFn: async (payload: PskConfigCreate) => createPskConfig(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['psk-configs'] })
      setNotification({ type: 'success', message: 'PSK config created successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  const updatePskMutation = useMutation({
    mutationFn: async ({ configId, payload }: { configId: number; payload: Partial<PskConfigCreate> }) =>
      updatePskConfig(configId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['psk-configs'] })
      setNotification({ type: 'success', message: 'PSK config updated successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  const deletePskMutation = useMutation({
    mutationFn: async (configId: number) => deletePskConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['psk-configs'] })
      setNotification({ type: 'success', message: 'PSK config deleted successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  // Enable/Disable EAP Method
  const toggleEapMethod = useMutation({
    mutationFn: async ({ methodName, enable }: { methodName: string; enable: boolean }) => {
      const endpoint = enable 
        ? `/api/v1/eap/methods/${methodName}/enable`
        : `/api/v1/eap/methods/${methodName}/disable`
      const { data } = await radiusApi.post(endpoint)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eap-methods'] })
      queryClient.invalidateQueries({ queryKey: ['eap-configs'] })
      setNotification({ type: 'success', message: 'EAP method updated successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  // Update EAP Method Policy
  const updateEapMethodPolicy = useMutation({
    mutationFn: async ({ methodId, successPolicyId, failurePolicyId }: { 
      methodId: number
      successPolicyId?: number | null
      failurePolicyId?: number | null
    }) => {
      const { data } = await radiusApi.patch(`/api/v1/eap/methods/${methodId}`, {
        success_policy_id: successPolicyId,
        failure_policy_id: failurePolicyId,
      })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eap-methods'] })
      setNotification({ type: 'success', message: 'EAP method policy updated successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  // MAC Bypass Mutations
  const createMacBypassMutation = useMutation({
    mutationFn: async (payload: MacBypassFormData) => {
      const { data } = await radiusApi.post('/api/v1/mac-bypass/config', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mac-bypass-configs'] })
      setNotification({ type: 'success', message: 'MAC bypass config created successfully' })
      setShowMacBypassModal(false)
      setMacBypassForm(emptyMacBypassForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  const updateMacBypassMutation = useMutation({
    mutationFn: async ({ configId, payload }: { configId: number; payload: MacBypassFormData }) => {
      const { data } = await radiusApi.put(`/api/v1/mac-bypass/config/${configId}`, payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mac-bypass-configs'] })
      setNotification({ type: 'success', message: 'MAC bypass config updated successfully' })
      setShowMacBypassModal(false)
      setEditingMacBypass(null)
      setMacBypassForm(emptyMacBypassForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  const deleteMacBypassMutation = useMutation({
    mutationFn: async (configId: number) => {
      await radiusApi.delete(`/api/v1/mac-bypass/config/${configId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mac-bypass-configs'] })
      setNotification({ type: 'success', message: 'MAC bypass config deleted successfully' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (err: Error) => {
      setNotification({ type: 'error', message: err.message })
    },
  })

  const handleOpenMacBypassModal = (config?: MacBypassConfig) => {
    if (config) {
      setEditingMacBypass(config)
      setMacBypassForm({
        name: config.name,
        description: config.description || '',
        mac_addresses: config.mac_addresses || [],
        bypass_mode: config.bypass_mode,
        require_registration: config.require_registration,
        registered_policy_id: config.registered_policy_id ?? null,
        unregistered_policy_id: config.unregistered_policy_id ?? null,
        is_active: config.is_active,
      })
    } else {
      setEditingMacBypass(null)
      setMacBypassForm(emptyMacBypassForm)
    }
    setShowMacBypassModal(true)
  }

  const handleAddMacAddress = () => {
    if (macAddressInput.trim()) {
      setMacBypassForm({
        ...macBypassForm,
        mac_addresses: [...macBypassForm.mac_addresses, macAddressInput.trim()],
      })
      setMacAddressInput('')
    }
  }

  const handleRemoveMacAddress = (index: number) => {
    setMacBypassForm({
      ...macBypassForm,
      mac_addresses: macBypassForm.mac_addresses.filter((_, i) => i !== index),
    })
  }

  const handleSaveMacBypass = (e: React.FormEvent) => {
    e.preventDefault()
    if (!macBypassForm.name.trim()) {
      setNotification({ type: 'error', message: 'Name is required' })
      return
    }

    if (editingMacBypass) {
      updateMacBypassMutation.mutate({ configId: editingMacBypass.id, payload: macBypassForm })
    } else {
      createMacBypassMutation.mutate(macBypassForm)
    }
  }

  const handleDeleteMacBypass = (config: MacBypassConfig) => {
    if (window.confirm(`Delete MAC bypass config "${config.name}"?`)) {
      deleteMacBypassMutation.mutate(config.id)
    }
  }

  const isLoading = eapLoading || methodsLoading || macBypassLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <span className="loading-spinner w-10 h-10" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Authentication Configuration</h1>
        <p className="text-gray-600 mt-2">
          Configure authentication methods for client devices: EAP-TLS, EAP-TTLS, PEAP, MAC-BYPASS, and PSK
        </p>
      </div>

      {notification && (
        <div
          className={`p-4 rounded-lg flex items-start gap-3 mb-6 ${
            notification.type === 'success'
              ? 'bg-green-50 border border-green-200'
              : notification.type === 'error'
              ? 'bg-red-50 border border-red-200'
              : 'bg-yellow-50 border border-yellow-200'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
          ) : (
            <AlertTriangle
              className={`flex-shrink-0 ${
                notification.type === 'error' ? 'text-red-600' : 'text-yellow-600'
              }`}
              size={20}
            />
          )}
          <p
            className={`text-sm ${
              notification.type === 'success'
                ? 'text-green-900'
                : notification.type === 'error'
                ? 'text-red-900'
                : 'text-yellow-900'
            }`}
          >
            {notification.message}
          </p>
        </div>
      )}

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('eap')}
            className={`pb-3 px-1 border-b-2 font-medium transition-colors ${
              activeTab === 'eap'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <Shield size={18} />
              EAP Methods
            </div>
          </button>
          <button
            onClick={() => setActiveTab('mac-bypass')}
            className={`pb-3 px-1 border-b-2 font-medium transition-colors ${
              activeTab === 'mac-bypass'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <UserCheck size={18} />
              MAC-BYPASS
            </div>
          </button>
          <button
            onClick={() => setActiveTab('psk')}
            className={`pb-3 px-1 border-b-2 font-medium transition-colors ${
              activeTab === 'psk'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <Key size={18} />
              PSK Authentication
            </div>
          </button>
        </nav>
      </div>

      {/* EAP Methods Tab */}
      {activeTab === 'eap' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">EAP Authentication Methods</h2>
            <p className="text-gray-600 mb-6">
              Configure EAP (Extensible Authentication Protocol) methods for client device authentication.
            </p>

            {eapConfigs && eapConfigs.length > 0 && (
              <div className="mb-6">
                <h3 className="font-medium mb-2">Active Configuration</h3>
                {eapConfigs.filter(c => c.is_active).map(config => (
                  <div key={config.id} className="bg-gray-50 p-4 rounded-lg mb-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium">{config.name}</h4>
                        {config.description && (
                          <p className="text-sm text-gray-600">{config.description}</p>
                        )}
                        <p className="text-sm text-gray-500 mt-1">
                          Default: {config.default_eap_type} | TLS: {config.tls_min_version}-{config.tls_max_version}
                        </p>
                      </div>
                      <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                        <CheckCircle size={12} />
                        Active
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-4">
              <h3 className="font-medium">Available Methods</h3>
              {eapMethods && eapMethods.length > 0 ? (
                <div className="space-y-4">
                  {eapMethods.map((method) => (
                    <div
                      key={method.id}
                      className="p-4 border border-gray-200 rounded-lg"
                    >
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div>
                            <div className="font-medium">{method.method_name.toUpperCase()}</div>
                            <div className="text-sm text-gray-500">
                              Attempts: {method.auth_attempts} | 
                              Success: {method.auth_successes} | 
                              Failures: {method.auth_failures}
                            </div>
                          </div>
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={method.is_enabled}
                            onChange={(e) =>
                              toggleEapMethod.mutate({
                                methodName: method.method_name,
                                enable: e.target.checked,
                              })
                            }
                            className="w-4 h-4"
                          />
                          <span className="text-sm">
                            {method.is_enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </label>
                      </div>
                      
                      {/* Authorization Policies for this method */}
                      {method.is_enabled && (
                        <div className="grid grid-cols-2 gap-4 border-t pt-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Success Policy
                            </label>
                            <select
                              value={method.success_policy_id || ''}
                              onChange={(e) =>
                                updateEapMethodPolicy.mutate({
                                  methodId: method.id,
                                  successPolicyId: e.target.value ? parseInt(e.target.value, 10) : null,
                                  failurePolicyId: method.failure_policy_id,
                                })
                              }
                              className="input w-full text-sm"
                            >
                              <option value="">-- No policy --</option>
                              {authPolicies?.map((policy) => (
                                <option key={policy.id} value={policy.id}>
                                  {policy.name}
                                  {policy.authorization_profile_name ? ` → ${policy.authorization_profile_name}` : ''}
                                </option>
                              ))}
                            </select>
                            <p className="text-xs text-gray-500 mt-1">
                              Applied on successful authentication
                            </p>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Failure Policy
                            </label>
                            <select
                              value={method.failure_policy_id || ''}
                              onChange={(e) =>
                                updateEapMethodPolicy.mutate({
                                  methodId: method.id,
                                  successPolicyId: method.success_policy_id,
                                  failurePolicyId: e.target.value ? parseInt(e.target.value, 10) : null,
                                })
                              }
                              className="input w-full text-sm"
                            >
                              <option value="">-- No policy --</option>
                              {authPolicies?.map((policy) => (
                                <option key={policy.id} value={policy.id}>
                                  {policy.name}
                                </option>
                              ))}
                            </select>
                            <p className="text-xs text-gray-500 mt-1">
                              Applied on failed authentication (optional)
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">No EAP methods configured</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MAC-BYPASS Tab */}
      {activeTab === 'mac-bypass' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button
              onClick={() => handleOpenMacBypassModal()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus size={18} />
              Add MAC Bypass Config
            </button>
          </div>

          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mode</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MAC Addresses</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Active</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {!macBypassConfigs || macBypassConfigs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                        No MAC bypass configurations yet.
                      </td>
                    </tr>
                  ) : (
                    macBypassConfigs.map((config) => (
                      <tr key={config.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <div className="font-medium text-gray-900">{config.name}</div>
                          {config.description && (
                            <div className="text-xs text-gray-500">{config.description}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          <span className={`px-2 py-1 rounded-full text-xs ${
                            config.bypass_mode === 'whitelist'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {config.bypass_mode}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {config.mac_addresses?.length || 0} address{config.mac_addresses?.length !== 1 ? 'es' : ''}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {config.is_active ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                              <CheckCircle size={12} />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                              <AlertTriangle size={12} />
                              Disabled
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => handleOpenMacBypassModal(config)}
                              className="text-blue-600 hover:text-blue-800 transition-colors p-2"
                              title="Edit"
                            >
                              <Edit size={16} />
                            </button>
                            <button
                              onClick={() => handleDeleteMacBypass(config)}
                              className="text-red-600 hover:text-red-800 transition-colors p-2"
                              title="Delete"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* PSK Authentication Tab */}
      {activeTab === 'psk' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">PSK Authentication</h2>
            <p className="text-gray-600 mb-6">
              PSK (Pre-Shared Key) authentication configurations with authorization policy assignments.
            </p>

            {/* PSK Configurations */}
            <div className="space-y-6">
              <h3 className="font-medium">PSK Configurations</h3>
              
              {pskLoading ? (
                <div className="text-center py-4">
                  <span className="loading-spinner w-6 h-6" />
                </div>
              ) : pskConfigs && pskConfigs.length > 0 ? (
                <div className="space-y-4">
                  {pskConfigs.map((config) => (
                    <div key={config.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h4 className="font-medium">{config.name}</h4>
                          {config.description && (
                            <p className="text-sm text-gray-500">{config.description}</p>
                          )}
                          <div className="text-xs text-gray-400 mt-1">
                            Type: {config.psk_type === 'generic' ? 'Generic PSK' : 'User PSK'}
                            {config.is_active ? (
                              <span className="ml-2 text-green-600">• Active</span>
                            ) : (
                              <span className="ml-2 text-gray-400">• Inactive</span>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete PSK config "${config.name}"?`)) {
                              deletePskMutation.mutate(config.id)
                            }
                          }}
                          className="text-red-600 hover:text-red-800 p-2"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>

                      {/* Authorization Policy */}
                      <div className="border-t pt-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Authorization Policy
                        </label>
                        <select
                          value={config.auth_policy_id || ''}
                          onChange={(e) =>
                            updatePskMutation.mutate({
                              configId: config.id,
                              payload: {
                                auth_policy_id: e.target.value ? parseInt(e.target.value, 10) : undefined,
                              },
                            })
                          }
                          className="input w-full"
                        >
                          <option value="">-- No policy --</option>
                          {authPolicies?.map((policy) => (
                            <option key={policy.id} value={policy.id}>
                              {policy.name}
                              {policy.authorization_profile_name ? ` → ${policy.authorization_profile_name}` : ''}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">
                          {config.auth_policy_name
                            ? `Current: ${config.auth_policy_name}`
                            : 'Select a policy to apply RADIUS attributes on PSK authentication'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-50 p-4 rounded-lg text-center">
                  <p className="text-sm text-gray-600">
                    No PSK configurations found.
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    PSK configurations can be created through the API.
                  </p>
                </div>
              )}

              {/* Info about User PSK */}
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">About PSK Authentication</h4>
                <p className="text-sm text-blue-800">
                  <strong>Generic PSK:</strong> Shared passphrase for all devices.
                </p>
                <p className="text-sm text-blue-800 mt-1">
                  <strong>User PSK (IPSK):</strong> Per-user passphrases managed through device registration.
                </p>
                <p className="text-sm text-blue-700 mt-2">
                  Authorization policies determine which RADIUS profile (VLAN, bandwidth, etc.) to apply.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MAC Bypass Modal */}
      {showMacBypassModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">
              {editingMacBypass ? 'Edit MAC Bypass Config' : 'Add MAC Bypass Config'}
            </h3>
            <form onSubmit={handleSaveMacBypass} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
                <input
                  type="text"
                  value={macBypassForm.name}
                  onChange={(e) => setMacBypassForm({ ...macBypassForm, name: e.target.value })}
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
                <input
                  type="text"
                  value={macBypassForm.description}
                  onChange={(e) => setMacBypassForm({ ...macBypassForm, description: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Bypass Mode</label>
                <select
                  value={macBypassForm.bypass_mode}
                  onChange={(e) => setMacBypassForm({ ...macBypassForm, bypass_mode: e.target.value as 'whitelist' | 'blacklist' })}
                  className="input"
                >
                  <option value="whitelist">Whitelist (only these MACs bypass)</option>
                  <option value="blacklist">Blacklist (these MACs don't bypass)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">MAC Addresses</label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={macAddressInput}
                    onChange={(e) => setMacAddressInput(e.target.value)}
                    placeholder="aa:bb:cc:dd:ee:ff"
                    className="input flex-1"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleAddMacAddress()
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleAddMacAddress}
                    className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                  >
                    Add
                  </button>
                </div>
                {macBypassForm.mac_addresses.length > 0 && (
                  <div className="space-y-1">
                    {macBypassForm.mac_addresses.map((mac, index) => (
                      <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                        <span className="text-sm font-mono">{mac}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveMacAddress(index)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={macBypassForm.require_registration}
                    onChange={(e) => setMacBypassForm({ ...macBypassForm, require_registration: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-gray-700">Require Registration</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={macBypassForm.is_active}
                    onChange={(e) => setMacBypassForm({ ...macBypassForm, is_active: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-gray-700">Active</span>
                </label>
              </div>

              {/* Authorization Policy Dropdowns */}
              <div className="border-t pt-4 mt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Authorization Policies</h4>
                <p className="text-xs text-gray-500 mb-4">
                  Policies determine which RADIUS profile (VLAN, bandwidth, etc.) to apply.
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Registered MAC Policy
                    </label>
                    <select
                      value={macBypassForm.registered_policy_id || ''}
                      onChange={(e) =>
                        setMacBypassForm({
                          ...macBypassForm,
                          registered_policy_id: e.target.value ? parseInt(e.target.value, 10) : null,
                        })
                      }
                      className="input w-full"
                    >
                      <option value="">-- No policy --</option>
                      {authPolicies?.map((policy) => (
                        <option key={policy.id} value={policy.id}>
                          {policy.name}
                          {policy.authorization_profile_name ? ` → ${policy.authorization_profile_name}` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Applied when MAC is found in device registrations
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Unregistered MAC Policy
                    </label>
                    <select
                      value={macBypassForm.unregistered_policy_id || ''}
                      onChange={(e) =>
                        setMacBypassForm({
                          ...macBypassForm,
                          unregistered_policy_id: e.target.value ? parseInt(e.target.value, 10) : null,
                        })
                      }
                      className="input w-full"
                    >
                      <option value="">-- No policy --</option>
                      {authPolicies?.map((policy) => (
                        <option key={policy.id} value={policy.id}>
                          {policy.name}
                          {policy.authorization_profile_name ? ` → ${policy.authorization_profile_name}` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Applied when MAC is not found in device registrations
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-3 justify-end mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowMacBypassModal(false)
                    setEditingMacBypass(null)
                    setMacBypassForm(emptyMacBypassForm)
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-white rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors"
                  disabled={createMacBypassMutation.isPending || updateMacBypassMutation.isPending}
                >
                  {createMacBypassMutation.isPending || updateMacBypassMutation.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
