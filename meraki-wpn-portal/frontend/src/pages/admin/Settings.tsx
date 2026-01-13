import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { 
  Save, 
  RefreshCw, 
  TestTube, 
  Key, 
  Shield, 
  Palette, 
  Wifi,
  Users,
  Eye,
  EyeOff,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Cloud,
  ExternalLink
} from 'lucide-react'
import { 
  getAllSettings, 
  updateSettings, 
  testConnection, 
  resetSettings,
  getIPSKOptions,
  getWPNSSIDStatus,
  configureSSIDForWPN,
  createWPNGroupPolicy,
  testCloudflareConnection,
  getCloudflareOptions,
  configureCloudfareTunnel,
  disconnectCloudfareTunnel
} from '../../api/client'

interface SettingsFormData {
  run_mode?: string
  meraki_api_key?: string
  ha_url?: string
  // Portal Branding
  property_name?: string
  logo_url?: string
  primary_color?: string
  // Network Defaults
  default_network_id?: string
  default_ssid_number?: number
  default_group_policy?: string
  standalone_ssid_name?: string
  // Authentication
  auth_self_registration?: boolean
  auth_invite_codes?: boolean
  auth_email_verification?: boolean
  auth_sms_verification?: boolean
  require_unit_number?: boolean
  unit_source?: string
  manual_units?: string
  // IPSK
  default_ipsk_duration_hours?: number
  passphrase_length?: number
  // Admin
  admin_username?: string
  secret_key?: string
  access_token_expire_minutes?: number
  database_url?: string
  // OAuth
  enable_oauth?: boolean
  oauth_provider?: string
  duo_client_id?: string
  duo_client_secret?: string
  duo_api_hostname?: string
  entra_client_id?: string
  entra_client_secret?: string
  entra_tenant_id?: string
  oauth_admin_only?: boolean
  oauth_auto_provision?: boolean
  oauth_callback_url?: string
  // Cloudflare
  cloudflare_enabled?: boolean
  cloudflare_api_token?: string
  cloudflare_account_id?: string
  cloudflare_tunnel_id?: string
  cloudflare_tunnel_name?: string
  cloudflare_zone_id?: string
  cloudflare_zone_name?: string
  cloudflare_hostname?: string
  cloudflare_local_url?: string
}

type TabType = 'branding' | 'meraki' | 'auth' | 'oauth' | 'cloudflare' | 'advanced'

const TABS: { id: TabType; label: string; icon: React.ReactNode }[] = [
  { id: 'branding', label: 'Branding', icon: <Palette size={18} /> },
  { id: 'meraki', label: 'Network', icon: <Wifi size={18} /> },
  { id: 'auth', label: 'Registration', icon: <Users size={18} /> },
  { id: 'oauth', label: 'OAuth / SSO', icon: <Shield size={18} /> },
  { id: 'cloudflare', label: 'Cloudflare Tunnel', icon: <Cloud size={18} /> },
  { id: 'advanced', label: 'Advanced', icon: <Key size={18} /> },
]

export default function Settings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<SettingsFormData>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [activeTab, setActiveTab] = useState<TabType>('branding')
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [passwordForm, setPasswordForm] = useState({
    current: '',
    new: '',
    confirm: ''
  })
  const [merakiOptions, setMerakiOptions] = useState<{
    networks: Array<{ id: string; name: string }>
    ssids: Array<{ number: number; name: string }>
    group_policies: Array<{ id: string; name: string }>
  }>({
    networks: [],
    ssids: [],
    group_policies: []
  })

  // Cloudflare state
  const [cloudflareOptions, setCloudflareOptions] = useState<{
    tunnels: Array<{ id: string; name: string; status: string; label: string }>
    zones: Array<{ id: string; name: string; label: string }>
  }>({
    tunnels: [],
    zones: []
  })
  const [cloudflareConnected, setCloudflareConnected] = useState(false)
  const [cloudflareLoading, setCloudflareLoading] = useState(false)
  const [cloudflarePreview, setCloudflarePreview] = useState({
    hostname: '',
    localUrl: 'http://localhost:8080'
  })

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings-all'],
    queryFn: getAllSettings,
  })

  // Check if we're in standalone mode
  const settingsData = settings as Record<string, unknown> | undefined
  const isStandalone = settingsData?.is_standalone || settingsData?.run_mode === 'standalone'
  const isEditable = settingsData?.editable_settings && isStandalone

  // Load Meraki options (networks, SSIDs)
  const { data: ipskOptions } = useQuery({
    queryKey: ['ipsk-options'],
    queryFn: async () => {
      try {
        return await getIPSKOptions()
      } catch (error) {
        console.error('Failed to load Meraki options:', error)
        return { networks: [], ssids: [], group_policies: [] }
      }
    },
    enabled: !!isEditable,
  })

  // Update form data when settings load
  useEffect(() => {
    if (settings) {
      setFormData(settings as SettingsFormData)
    }
  }, [settings])

  // Update Meraki options when loaded
  useEffect(() => {
    if (ipskOptions) {
      setMerakiOptions(ipskOptions)
    }
  }, [ipskOptions])

  const saveMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      setNotification({
        type: data.requires_restart ? 'warning' : 'success',
        message: data.message,
      })
      queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to save settings',
      })
    },
  })

  const testMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) => testConnection(settings),
    onSuccess: (data) => {
      // Build a summary message from results
      const resultMessages = Object.entries(data.results || {})
        .map(([key, val]) => `${key}: ${val.message}`)
        .join('; ')
      setNotification({
        type: data.success ? 'success' : 'error',
        message: resultMessages || (data.success ? 'Connection successful' : 'Connection failed'),
      })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Connection test failed',
      })
    },
  })

  const resetMutation = useMutation({
    mutationFn: resetSettings,
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Settings reset to defaults',
      })
      queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to reset settings',
      })
    },
  })

  const passwordMutation = useMutation({
    mutationFn: async (data: { current_password: string; new_password: string }) => {
      const response = await fetch('/api/admin/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to change password')
      }
      return response.json()
    },
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Password changed successfully' })
      setShowPasswordModal(false)
      setPasswordForm({ current: '', new: '', confirm: '' })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message })
    },
  })

  const updateField = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const toggleSecret = (field: string) => {
    setShowSecrets((prev) => ({ ...prev, [field]: !prev[field] }))
  }

  const handleSave = () => {
    saveMutation.mutate(formData as Record<string, unknown>)
  }

  const handleTest = () => {
    testMutation.mutate(formData as Record<string, unknown>)
  }

  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset all settings to defaults?')) {
      resetMutation.mutate()
    }
  }

  const handlePasswordChange = () => {
    if (passwordForm.new !== passwordForm.confirm) {
      setNotification({ type: 'error', message: 'New passwords do not match' })
      return
    }
    if (passwordForm.new.length < 8) {
      setNotification({ type: 'error', message: 'Password must be at least 8 characters' })
      return
    }
    passwordMutation.mutate({
      current_password: passwordForm.current,
      new_password: passwordForm.new,
    })
  }

  // Cloudflare functions
  const handleTestCloudflare = async () => {
    if (!formData.cloudflare_api_token || formData.cloudflare_api_token === '***') {
      setNotification({ type: 'error', message: 'Please enter a Cloudflare API token first' })
      return
    }
    setCloudflareLoading(true)
    try {
      const result = await testCloudflareConnection(
        formData.cloudflare_api_token,
        formData.cloudflare_account_id || undefined
      )
      if (result.success) {
        setCloudflareConnected(true)
        setNotification({ type: 'success', message: result.message || 'Connected to Cloudflare!' })
        // Load options - pass the token directly since it's not saved yet
        await handleLoadCloudflareOptions(
          formData.cloudflare_api_token,
          formData.cloudflare_account_id
        )
      } else {
        setCloudflareConnected(false)
        setNotification({ type: 'error', message: result.error || 'Connection failed' })
      }
    } catch (error) {
      setCloudflareConnected(false)
      setNotification({ type: 'error', message: 'Failed to connect to Cloudflare' })
    } finally {
      setCloudflareLoading(false)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  const handleLoadCloudflareOptions = async (token?: string, accountId?: string) => {
    try {
      // Use provided token/account or fall back to form data
      const apiToken = token || formData.cloudflare_api_token
      const acctId = accountId || formData.cloudflare_account_id

      const options = await getCloudflareOptions(
        apiToken !== '***' ? apiToken : undefined,
        acctId || undefined
      )
      if (options.success) {
        setCloudflareOptions({
          tunnels: options.tunnels || [],
          zones: options.zones || []
        })
        setCloudflareConnected(true)
      } else {
        console.error('Failed to load Cloudflare options:', options.error)
      }
    } catch (error) {
      console.error('Failed to load Cloudflare options:', error)
    }
  }

  const handleConfigureCloudflare = async () => {
    if (!formData.cloudflare_tunnel_id || !formData.cloudflare_zone_id || !cloudflarePreview.hostname) {
      setNotification({ type: 'error', message: 'Please select a tunnel, zone, and enter a hostname' })
      return
    }
    setCloudflareLoading(true)
    try {
      const result = await configureCloudfareTunnel(
        formData.cloudflare_tunnel_id,
        formData.cloudflare_zone_id,
        cloudflarePreview.hostname,
        cloudflarePreview.localUrl,
        formData.cloudflare_api_token !== '***' ? formData.cloudflare_api_token : undefined,
        formData.cloudflare_account_id || undefined
      )
      if (result.success) {
        setNotification({ type: 'success', message: result.message })
        // Update form with configured values
        updateField('cloudflare_enabled', true)
        updateField('cloudflare_hostname', result.hostname)
        updateField('cloudflare_local_url', result.local_url)
        updateField('cloudflare_tunnel_name', result.tunnel_name)
        queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      } else {
        setNotification({ type: 'error', message: 'Failed to configure tunnel' })
      }
    } catch (error) {
      setNotification({ type: 'error', message: 'Failed to configure Cloudflare tunnel' })
    } finally {
      setCloudflareLoading(false)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  const handleDisconnectCloudflare = async () => {
    if (!window.confirm('Disconnect the Cloudflare tunnel? The DNS record will remain.')) {
      return
    }
    setCloudflareLoading(true)
    try {
      const result = await disconnectCloudfareTunnel()
      if (result.success) {
        setNotification({ type: 'success', message: result.message })
        updateField('cloudflare_enabled', false)
        updateField('cloudflare_tunnel_id', '')
        updateField('cloudflare_hostname', '')
        queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      }
    } catch (error) {
      setNotification({ type: 'error', message: 'Failed to disconnect tunnel' })
    } finally {
      setCloudflareLoading(false)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  // Update hostname preview when zone or subdomain changes
  const updateHostnamePreview = (subdomain: string, zoneId: string) => {
    const zone = cloudflareOptions.zones.find(z => z.id === zoneId)
    if (zone && subdomain) {
      setCloudflarePreview(prev => ({
        ...prev,
        hostname: `${subdomain}.${zone.name}`
      }))
    }
  }

  // Load Cloudflare options on mount if token exists
  useEffect(() => {
    if (formData.cloudflare_api_token && formData.cloudflare_api_token !== '***') {
      handleLoadCloudflareOptions(formData.cloudflare_api_token, formData.cloudflare_account_id)
    }
    // Set preview from existing settings
    if (formData.cloudflare_hostname) {
      setCloudflarePreview(prev => ({
        ...prev,
        hostname: formData.cloudflare_hostname || ''
      }))
    }
    if (formData.cloudflare_local_url) {
      setCloudflarePreview(prev => ({
        ...prev,
        localUrl: formData.cloudflare_local_url || 'http://localhost:8080'
      }))
    }
  }, [formData.cloudflare_api_token, formData.cloudflare_hostname, formData.cloudflare_local_url])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin" size={32} />
      </div>
    )
  }

  // Read-only mode for Home Assistant managed settings
  if (!isEditable) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="card">
          <div className="flex items-center gap-3 text-warning">
            <AlertTriangle size={24} />
            <div>
              <h3 className="font-semibold">Managed by Home Assistant</h3>
              <p className="text-sm opacity-80">
                Settings are configured through the Home Assistant add-on configuration.
                Edit the add-on options in the Supervisor panel.
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Current Configuration</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600">Run Mode</span>
              <span className="font-medium">{settingsData?.run_mode as string || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600">Property Name</span>
              <span className="font-medium">{settingsData?.property_name as string || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600">Self Registration</span>
              <span className="font-medium">{settingsData?.auth_self_registration ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-600">Invite Codes</span>
              <span className="font-medium">{settingsData?.auth_invite_codes ? 'Enabled' : 'Disabled'}</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="flex gap-2">
          <button
            className="btn btn-secondary"
            onClick={handleTest}
            disabled={testMutation.isPending}
          >
            <TestTube size={16} />
            {testMutation.isPending ? 'Testing...' : 'Test Connection'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleReset}
            disabled={resetMutation.isPending}
          >
            <RefreshCw size={16} />
            Reset
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saveMutation.isPending}
          >
            <Save size={16} />
            {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 text-green-800 border border-green-200'
              : notification.type === 'warning'
              ? 'bg-yellow-100 text-yellow-800 border border-yellow-200'
              : 'bg-red-100 text-red-800 border border-red-200'
          }`}
        >
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <XCircle size={20} />}
          {notification.message}
        </div>
      )}

      {/* Storage Info */}
      <div className="text-sm text-gray-500 bg-gray-50 p-3 rounded-lg border">
        Settings are saved to the database (<code>portal_settings</code> table) for persistence without restart.
      </div>

      {/* Tab Navigation */}
      <div 
        style={{
          display: 'flex',
          borderBottom: '2px solid #e5e7eb',
          marginBottom: '8px',
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 20px',
              fontSize: '14px',
              fontWeight: 600,
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              borderBottom: activeTab === tab.id ? '3px solid #00A4E4' : '3px solid transparent',
              marginBottom: '-2px',
              color: activeTab === tab.id ? '#00A4E4' : '#6b7280',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.color = '#374151'
                e.currentTarget.style.borderBottomColor = '#d1d5db'
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.color = '#6b7280'
                e.currentTarget.style.borderBottomColor = 'transparent'
              }
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* BRANDING TAB */}
        {activeTab === 'branding' && (
          <div className="card">
            <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
              <Palette size={20} style={{ color: 'var(--meraki-blue)' }} />
              Portal Branding
            </h3>
            <FormRow label="Property Name">
              <input
                type="text"
                value={formData.property_name || ''}
                onChange={(e) => updateField('property_name', e.target.value)}
                className="input"
                placeholder="My Property"
              />
            </FormRow>
            <FormRow label="Logo URL">
              <input
                type="url"
                value={formData.logo_url || ''}
                onChange={(e) => updateField('logo_url', e.target.value)}
                className="input"
                placeholder="https://example.com/logo.png"
              />
            </FormRow>
            <FormRow label="Primary Color">
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={formData.primary_color || '#00A4E4'}
                  onChange={(e) => updateField('primary_color', e.target.value)}
                  style={{ 
                    width: '60px', 
                    height: '44px', 
                    cursor: 'pointer',
                    border: '2px solid var(--gray-300)',
                    borderRadius: '8px'
                  }}
                />
                <input
                  type="text"
                  value={formData.primary_color || '#00A4E4'}
                  onChange={(e) => updateField('primary_color', e.target.value)}
                  className="input"
                  placeholder="#00A4E4"
                  style={{ flex: 1 }}
                />
              </div>
            </FormRow>
          </div>
        )}

        {/* MERAKI & NETWORK TAB */}
        {activeTab === 'meraki' && (
          <>
            {/* API Key & Connection Status */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                  <Key size={20} style={{ color: 'var(--meraki-blue)' }} />
                  Meraki Dashboard API
                </h3>
                {/* Connection Status Indicator */}
                <div 
                  className="flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium"
                  style={{
                    backgroundColor: merakiOptions.networks.length > 0 ? '#dcfce7' : '#fef3c7',
                    color: merakiOptions.networks.length > 0 ? '#166534' : '#92400e',
                  }}
                >
                  <span 
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: merakiOptions.networks.length > 0 ? '#22c55e' : '#f59e0b',
                    }}
                  />
                  {merakiOptions.networks.length > 0 
                    ? `Connected (${merakiOptions.networks.length} networks)` 
                    : 'Not connected'}
                </div>
              </div>
              <FormRow label="API Key" required>
                <SecretInput
                  value={formData.meraki_api_key || ''}
                  onChange={(v) => updateField('meraki_api_key', v)}
                  show={showSecrets.meraki_api_key}
                  onToggle={() => toggleSecret('meraki_api_key')}
                  placeholder="Enter Meraki Dashboard API key"
                />
              </FormRow>
              <p className="text-sm text-gray-500 mt-2">
                Get your API key from the Meraki Dashboard: Organization → Settings → Dashboard API access
              </p>
            </div>

            {/* WPN Configuration */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Wifi size={20} style={{ color: 'var(--meraki-blue)' }} />
                WPN Configuration
              </h3>
              
              {/* WPN Setup Guide */}
              <div className="p-4 mb-4 rounded-lg" style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe' }}>
                <p className="text-sm" style={{ color: '#1e40af' }}>
                  <strong>Wi-Fi Personal Network (WPN) Requirements:</strong>
                </p>
                <ol className="text-sm mt-2 ml-4" style={{ color: '#1e40af', listStyleType: 'decimal' }}>
                  <li>Create a <strong>Group Policy</strong> in Meraki Dashboard (Network-wide → Group policies)</li>
                  <li>Configure SSID with <strong>Identity PSK without RADIUS</strong> and enable <strong>WPN</strong></li>
                  <li>Select the Network, SSID, and Group Policy below</li>
                </ol>
                <p className="text-xs mt-2" style={{ color: '#3b82f6' }}>
                  <a href="https://documentation.meraki.com/Wireless/Design_and_Configure/Configuration_Guides/Encryption_and_Authentication/Wi-Fi_Personal_Network_(WPN)" 
                     target="_blank" 
                     rel="noopener noreferrer"
                     style={{ textDecoration: 'underline' }}>
                    View Meraki WPN Documentation →
                  </a>
                </p>
              </div>
              
              {merakiOptions.networks.length === 0 && (
                <div className="p-4 mb-4 rounded-lg" style={{ backgroundColor: '#fef3c7', border: '1px solid #fcd34d' }}>
                  <p className="text-sm" style={{ color: '#92400e' }}>
                    <strong>No connection to Meraki Dashboard.</strong> Save a valid API key and refresh to load networks.
                  </p>
                </div>
              )}

              <FormRow label="Network">
                {merakiOptions.networks.length > 0 ? (
                  <select
                    value={formData.default_network_id || ''}
                    onChange={(e) => updateField('default_network_id', e.target.value)}
                    className="input"
                  >
                    <option value="">Select a network...</option>
                    {merakiOptions.networks.map((network) => (
                      <option key={network.id} value={network.id}>
                        {network.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <select className="input" disabled style={{ backgroundColor: '#f3f4f6' }}>
                    <option>Connect to Meraki to load networks</option>
                  </select>
                )}
              </FormRow>

              <FormRow label="SSID" required>
                {merakiOptions.ssids.length > 0 ? (
                  <select
                    value={formData.default_ssid_number || ''}
                    onChange={(e) => updateField('default_ssid_number', parseInt(e.target.value))}
                    className="input"
                  >
                    <option value="">Select an SSID...</option>
                    {merakiOptions.ssids.map((ssid) => (
                      <option key={ssid.number} value={ssid.number}>
                        {ssid.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <select className="input" disabled style={{ backgroundColor: '#f3f4f6' }}>
                    <option>Select a network first</option>
                  </select>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  Must be configured with "Identity PSK without RADIUS" and WPN enabled
                </p>
              </FormRow>

              <FormRow label="Group Policy" required>
                {merakiOptions.group_policies.length > 0 ? (
                  <select
                    value={formData.default_group_policy || ''}
                    onChange={(e) => updateField('default_group_policy', e.target.value)}
                    className="input"
                    style={!formData.default_group_policy ? { borderColor: '#f59e0b' } : {}}
                  >
                    <option value="">Select a group policy...</option>
                    {merakiOptions.group_policies.map((policy) => (
                      <option key={policy.id} value={policy.id}>
                        {policy.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <select className="input" disabled style={{ backgroundColor: '#f3f4f6' }}>
                    <option>Create group policies in Meraki Dashboard first</option>
                  </select>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  Required for WPN. Create in Meraki: Network-wide → Configure → Group policies
                </p>
              </FormRow>
            </div>

            {/* WPN Quick Setup */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Shield size={20} style={{ color: 'var(--meraki-blue)' }} />
                WPN Quick Setup
              </h3>
              <p className="text-sm text-gray-600 mb-4">
                Use these buttons to automatically configure your SSID for WPN or create group policies.
              </p>
              
              <div className="flex gap-3 flex-wrap">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={async () => {
                    try {
                      const data = await getWPNSSIDStatus()
                      const statusParts = [
                        `SSID: ${data.ssid_name}`,
                        `Enabled: ${data.enabled ? '✓' : '✗'}`,
                        `Identity PSK: ${data.ipsk_configured ? '✓' : '✗'}`,
                        `WPN: ${data.wpn_enabled ? '✓' : '✗'}`,
                      ]
                      if (data.wpn_ready) {
                        setNotification({
                          type: 'success',
                          message: `✓ ${data.ssid_name} is fully configured for WPN!\n\n${statusParts.join(' | ')}`,
                        })
                      } else {
                        setNotification({
                          type: 'warning',
                          message: `${statusParts.join(' | ')}\n\nIssues:\n${data.issues.map(i => `• ${i}`).join('\n')}`,
                        })
                      }
                    } catch (e) {
                      setNotification({ type: 'error', message: e instanceof Error ? e.message : 'Failed to check SSID status' })
                    }
                    setTimeout(() => setNotification(null), 10000)
                  }}
                >
                  Check SSID Status
                </button>
                
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={async () => {
                    const groupPolicyName = window.prompt(
                      'Enter group policy name (will be created if it doesn\'t exist):',
                      'WPN-Users'
                    )
                    if (!groupPolicyName) return
                    if (!window.confirm(`This will configure the SSID with:\n\n✓ Identity PSK without RADIUS\n✓ WPA2 encryption\n✓ Bridge mode\n✓ Group Policy: "${groupPolicyName}"\n\n⚠️ NOTE: WPN must be enabled MANUALLY in Meraki Dashboard\n(API does not support WPN toggle)\n\nContinue?`)) return
                    try {
                      const data = await configureSSIDForWPN(groupPolicyName)
                      if (data.success) {
                        const ssid = data.result?.ssid
                        const policyId = data.result?.group_policy_id
                        const splashUrl = data.splash_url
                        const defaultPsk = data.default_psk
                        setNotification({ 
                          type: 'warning', 
                          message: `✓ SSID "${ssid?.name}" configured!\n\n` +
                            `• Auth: Identity PSK without RADIUS\n` +
                            `• Group Policy: ${data.group_policy_name || groupPolicyName} (ID: ${policyId || 'N/A'})\n` +
                            `• Splash URL: ${splashUrl || 'N/A'}\n` +
                            `• Default PSK: ${defaultPsk || 'N/A'}\n\n` +
                            `⚠️ MANUAL STEP REQUIRED:\n` +
                            `Go to Meraki Dashboard → Wireless → Access Control\n` +
                            `→ Select SSID → Wi-Fi Personal Network (WPN) → Enable`,
                        })
                        // Refresh to get new group policy in dropdown
                        setTimeout(() => window.location.reload(), 5000)
                      } else {
                        setNotification({ type: 'error', message: 'Failed to configure SSID' })
                      }
                    } catch (e) {
                      setNotification({ type: 'error', message: e instanceof Error ? e.message : 'Failed to configure SSID' })
                    }
                    setTimeout(() => setNotification(null), 15000)
                  }}
                >
                  Configure SSID for WPN
                </button>
                
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={async () => {
                    const name = window.prompt('Enter name for new group policy:', 'WPN-Users')
                    if (!name) return
                    try {
                      const data = await createWPNGroupPolicy(name)
                      if (data.success) {
                        setNotification({ type: 'success', message: data.message })
                        // Refresh the IPSK options to get the new policy
                        setTimeout(() => window.location.reload(), 1500)
                      } else {
                        setNotification({ type: 'error', message: 'Failed to create group policy' })
                      }
                    } catch (e) {
                      setNotification({ type: 'error', message: e instanceof Error ? e.message : 'Failed to create group policy' })
                    }
                    setTimeout(() => setNotification(null), 5000)
                  }}
                >
                  + Create Group Policy
                </button>
              </div>
            </div>

            {/* IPSK Settings */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Key size={20} style={{ color: 'var(--meraki-blue)' }} />
                IPSK Settings
              </h3>
              <FormRow label="Default Duration (hours)">
                <input
                  type="number"
                  value={formData.default_ipsk_duration_hours || 24}
                  onChange={(e) => updateField('default_ipsk_duration_hours', parseInt(e.target.value))}
                  className="input"
                  min="1"
                  max="8760"
                />
              </FormRow>
              <FormRow label="Passphrase Length">
                <input
                  type="number"
                  value={formData.passphrase_length || 12}
                  onChange={(e) => updateField('passphrase_length', parseInt(e.target.value))}
                  className="input"
                  min="8"
                  max="64"
                />
              </FormRow>
            </div>
          </>
        )}

        {/* REGISTRATION TAB */}
        {activeTab === 'auth' && (
          <div className="card">
            <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
              <Users size={20} style={{ color: 'var(--meraki-blue)' }} />
              Registration Settings
            </h3>
            <FormRow label="Enable Self-Registration">
              <input
                type="checkbox"
                checked={formData.auth_self_registration || false}
                onChange={(e) => updateField('auth_self_registration', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>
            <FormRow label="Enable Invite Codes">
              <input
                type="checkbox"
                checked={formData.auth_invite_codes || false}
                onChange={(e) => updateField('auth_invite_codes', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>
            <FormRow label="Require Email Verification">
              <input
                type="checkbox"
                checked={formData.auth_email_verification || false}
                onChange={(e) => updateField('auth_email_verification', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>
            <FormRow label="Require SMS Verification">
              <input
                type="checkbox"
                checked={formData.auth_sms_verification || false}
                onChange={(e) => updateField('auth_sms_verification', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>
            <FormRow label="Require Unit Number">
              <input
                type="checkbox"
                checked={formData.require_unit_number || false}
                onChange={(e) => updateField('require_unit_number', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>
            {formData.require_unit_number && (
              <>
                <FormRow label="Unit Source">
                  <select
                    value={formData.unit_source || 'manual'}
                    onChange={(e) => updateField('unit_source', e.target.value)}
                    className="input"
                  >
                    <option value="manual">Manual Entry</option>
                    <option value="list">Predefined List</option>
                    <option value="api">External API</option>
                  </select>
                </FormRow>
                {formData.unit_source === 'list' && (
                  <FormRow label="Unit List (comma-separated)">
                    <input
                      type="text"
                      value={formData.manual_units || ''}
                      onChange={(e) => updateField('manual_units', e.target.value)}
                      className="input"
                      placeholder="101, 102, 103, 201, 202..."
                    />
                  </FormRow>
                )}
              </>
            )}
          </div>
        )}

        {/* OAUTH / SSO TAB */}
        {activeTab === 'oauth' && (
          <div className="card">
            <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
              <Shield size={20} style={{ color: 'var(--meraki-blue)' }} />
              OAuth / Single Sign-On
            </h3>
            
            <FormRow label="Enable OAuth">
              <input
                type="checkbox"
                checked={formData.enable_oauth || false}
                onChange={(e) => updateField('enable_oauth', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
            </FormRow>

            {formData.enable_oauth && (
              <>
                <FormRow label="OAuth Provider">
                  <select
                    value={formData.oauth_provider || ''}
                    onChange={(e) => updateField('oauth_provider', e.target.value)}
                    className="input"
                  >
                    <option value="">Select provider...</option>
                    <option value="duo">Duo Security</option>
                    <option value="entra">Microsoft Entra ID</option>
                  </select>
                </FormRow>

                <FormRow label="Admin Only">
                  <input
                    type="checkbox"
                    checked={formData.oauth_admin_only || false}
                    onChange={(e) => updateField('oauth_admin_only', e.target.checked)}
                    style={{ width: '20px', height: '20px' }}
                  />
                </FormRow>

                <FormRow label="Auto-Provision Users">
                  <input
                    type="checkbox"
                    checked={formData.oauth_auto_provision || false}
                    onChange={(e) => updateField('oauth_auto_provision', e.target.checked)}
                    style={{ width: '20px', height: '20px' }}
                  />
                </FormRow>

                <FormRow label="Callback URL">
                  <input
                    type="url"
                    value={formData.oauth_callback_url || ''}
                    onChange={(e) => updateField('oauth_callback_url', e.target.value)}
                    className="input"
                    placeholder="https://your-domain.com/api/auth/callback"
                  />
                </FormRow>

                {formData.oauth_provider === 'duo' && (
                  <>
                    <div className="border-t my-4 pt-4">
                      <h4 className="font-medium mb-3">Duo Security Settings</h4>
                    </div>
                    <FormRow label="Duo Client ID" required>
                      <input
                        type="text"
                        value={formData.duo_client_id || ''}
                        onChange={(e) => updateField('duo_client_id', e.target.value)}
                        className="input"
                        placeholder="Enter Duo Client ID"
                      />
                    </FormRow>
                    <FormRow label="Duo Client Secret" required>
                      <SecretInput
                        value={formData.duo_client_secret || ''}
                        onChange={(v) => updateField('duo_client_secret', v)}
                        show={showSecrets.duo_client_secret}
                        onToggle={() => toggleSecret('duo_client_secret')}
                        placeholder="Enter Duo Client Secret"
                      />
                    </FormRow>
                    <FormRow label="Duo API Hostname" required>
                      <input
                        type="text"
                        value={formData.duo_api_hostname || ''}
                        onChange={(e) => updateField('duo_api_hostname', e.target.value)}
                        className="input"
                        placeholder="api-xxxxxxxx.duosecurity.com"
                      />
                    </FormRow>
                  </>
                )}

                {formData.oauth_provider === 'entra' && (
                  <>
                    <div className="border-t my-4 pt-4">
                      <h4 className="font-medium mb-3">Microsoft Entra ID Settings</h4>
                    </div>
                    <FormRow label="Entra Client ID" required>
                      <input
                        type="text"
                        value={formData.entra_client_id || ''}
                        onChange={(e) => updateField('entra_client_id', e.target.value)}
                        className="input"
                        placeholder="Enter Application (client) ID"
                      />
                    </FormRow>
                    <FormRow label="Entra Client Secret" required>
                      <SecretInput
                        value={formData.entra_client_secret || ''}
                        onChange={(v) => updateField('entra_client_secret', v)}
                        show={showSecrets.entra_client_secret}
                        onToggle={() => toggleSecret('entra_client_secret')}
                        placeholder="Enter Client Secret Value"
                      />
                    </FormRow>
                    <FormRow label="Entra Tenant ID" required>
                      <input
                        type="text"
                        value={formData.entra_tenant_id || ''}
                        onChange={(e) => updateField('entra_tenant_id', e.target.value)}
                        className="input"
                        placeholder="Enter Directory (tenant) ID"
                      />
                    </FormRow>
                  </>
                )}
              </>
            )}
          </div>
        )}

        {/* CLOUDFLARE TAB */}
        {activeTab === 'cloudflare' && (
          <div className="card">
            <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
              <Cloud size={20} style={{ color: 'var(--meraki-blue)' }} />
              Cloudflare Zero Trust Tunnel
            </h3>

            <div className="p-4 mb-4 rounded-lg" style={{ background: 'rgba(0, 164, 228, 0.1)' }}>
              <p className="text-sm">
                <strong>What is this?</strong> Cloudflare Tunnels allow you to securely expose your portal
                to the internet without opening firewall ports. Perfect for splash page redirects and
                remote access.
              </p>
            </div>

            {/* Connection Status */}
            {formData.cloudflare_enabled && formData.cloudflare_hostname && (
              <div className="p-4 mb-4 rounded-lg flex items-center justify-between" 
                   style={{ background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)' }}>
                <div className="flex items-center gap-2">
                  <CheckCircle size={20} style={{ color: '#22c55e' }} />
                  <span className="font-medium" style={{ color: '#22c55e' }}>Tunnel Active</span>
                  <a 
                    href={`https://${formData.cloudflare_hostname}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-sm underline"
                    style={{ color: 'var(--meraki-blue)' }}
                  >
                    {formData.cloudflare_hostname}
                    <ExternalLink size={14} />
                  </a>
                </div>
                <button
                  onClick={handleDisconnectCloudflare}
                  disabled={cloudflareLoading}
                  className="btn btn-outline text-sm"
                  style={{ borderColor: '#dc2626', color: '#dc2626' }}
                >
                  Disconnect
                </button>
              </div>
            )}

            {/* API Token */}
            <FormRow label="Cloudflare API Token" required>
              <div className="flex gap-2">
                <div className="flex-1">
                  <SecretInput
                    value={formData.cloudflare_api_token || ''}
                    onChange={(v) => updateField('cloudflare_api_token', v)}
                    show={showSecrets.cloudflare_api_token}
                    onToggle={() => toggleSecret('cloudflare_api_token')}
                    placeholder="Enter Cloudflare API Token"
                  />
                </div>
                <button
                  onClick={handleTestCloudflare}
                  disabled={cloudflareLoading || !formData.cloudflare_api_token}
                  className="btn btn-outline"
                  style={{ minWidth: '120px' }}
                >
                  {cloudflareLoading ? <RefreshCw className="animate-spin" size={16} /> : 'Test & Load'}
                </button>
              </div>
              <p className="text-xs mt-1 opacity-60">
                Create a token at{' '}
                <a href="https://dash.cloudflare.com/profile/api-tokens" target="_blank" rel="noopener noreferrer" className="underline">
                  Cloudflare Dashboard
                </a>
                {' '}with "Cloudflare Tunnel:Edit" and "Zone:DNS:Edit" permissions.
              </p>
            </FormRow>

            {/* Account ID */}
            <FormRow label="Account ID">
              <input
                type="text"
                value={formData.cloudflare_account_id || ''}
                onChange={(e) => updateField('cloudflare_account_id', e.target.value)}
                className="input"
                placeholder="1a14a76e949f7da9e9acd50dd93612ac"
              />
              <p className="text-xs mt-1 opacity-60">
                Find your Account ID in the Cloudflare Dashboard URL or on the Overview page.
                Required for account-scoped API tokens.
              </p>
            </FormRow>

            {/* Tunnel Selection */}
            <FormRow label="Select Tunnel" required>
              <select
                value={formData.cloudflare_tunnel_id || ''}
                onChange={(e) => {
                  updateField('cloudflare_tunnel_id', e.target.value)
                  const tunnel = cloudflareOptions.tunnels.find(t => t.id === e.target.value)
                  if (tunnel) {
                    updateField('cloudflare_tunnel_name', tunnel.name)
                  }
                }}
                className="input"
                disabled={!cloudflareConnected || cloudflareOptions.tunnels.length === 0}
              >
                <option value="">
                  {!cloudflareConnected 
                    ? 'Test connection first...' 
                    : cloudflareOptions.tunnels.length === 0 
                      ? 'No tunnels found' 
                      : 'Select a tunnel...'}
                </option>
                {cloudflareOptions.tunnels.map((tunnel) => (
                  <option key={tunnel.id} value={tunnel.id}>
                    {tunnel.label}
                  </option>
                ))}
              </select>
              {formData.cloudflare_tunnel_name && (
                <p className="text-xs mt-1 opacity-60">
                  Selected: {formData.cloudflare_tunnel_name}
                </p>
              )}
            </FormRow>

            {/* Zone (Domain) Selection */}
            <FormRow label="Domain" required>
              <select
                value={formData.cloudflare_zone_id || ''}
                onChange={(e) => {
                  updateField('cloudflare_zone_id', e.target.value)
                  const zone = cloudflareOptions.zones.find(z => z.id === e.target.value)
                  if (zone) {
                    updateField('cloudflare_zone_name', zone.name)
                  }
                }}
                className="input"
                disabled={!cloudflareConnected || cloudflareOptions.zones.length === 0}
              >
                <option value="">
                  {!cloudflareConnected 
                    ? 'Test connection first...' 
                    : cloudflareOptions.zones.length === 0 
                      ? 'No domains found' 
                      : 'Select a domain...'}
                </option>
                {cloudflareOptions.zones.map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.label}
                  </option>
                ))}
              </select>
            </FormRow>

            {/* Hostname Preview */}
            <FormRow label="Public Hostname" required>
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  value={cloudflarePreview.hostname.split('.')[0] || ''}
                  onChange={(e) => {
                    const subdomain = e.target.value.replace(/[^a-z0-9-]/gi, '').toLowerCase()
                    updateHostnamePreview(subdomain, formData.cloudflare_zone_id || '')
                  }}
                  className="input"
                  placeholder="portal"
                  style={{ maxWidth: '150px' }}
                  disabled={!formData.cloudflare_zone_id}
                />
                <span className="opacity-60">.</span>
                <span className="opacity-80">
                  {formData.cloudflare_zone_name || 'example.com'}
                </span>
              </div>
              {cloudflarePreview.hostname && (
                <p className="text-xs mt-1" style={{ color: 'var(--meraki-blue)' }}>
                  Portal will be accessible at: <strong>https://{cloudflarePreview.hostname}</strong>
                </p>
              )}
            </FormRow>

            {/* Local URL Preview */}
            <FormRow label="Local Service URL">
              <input
                type="text"
                value={cloudflarePreview.localUrl}
                onChange={(e) => setCloudflarePreview(prev => ({ ...prev, localUrl: e.target.value }))}
                className="input"
                placeholder="http://localhost:8080"
              />
              <p className="text-xs mt-1 opacity-60">
                The local address where the portal is running. Usually <code>http://localhost:8080</code>
              </p>
            </FormRow>

            {/* Configure Button */}
            <div className="mt-6 pt-4 border-t flex justify-between items-center">
              <div className="text-sm opacity-60">
                {formData.cloudflare_enabled 
                  ? 'Tunnel is configured and active'
                  : 'Configure the tunnel to enable external access'}
              </div>
              <button
                onClick={handleConfigureCloudflare}
                disabled={
                  cloudflareLoading || 
                  !formData.cloudflare_tunnel_id || 
                  !formData.cloudflare_zone_id || 
                  !cloudflarePreview.hostname
                }
                className="btn btn-primary"
              >
                {cloudflareLoading ? (
                  <RefreshCw className="animate-spin" size={16} />
                ) : formData.cloudflare_enabled ? (
                  'Update Configuration'
                ) : (
                  'Configure Tunnel'
                )}
              </button>
            </div>
          </div>
        )}

        {/* ADVANCED TAB */}
        {activeTab === 'advanced' && (
          <>
            {/* Admin Security */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Shield size={20} style={{ color: 'var(--meraki-blue)' }} />
                Admin Security
              </h3>
              <FormRow label="Admin Username">
                <input
                  type="text"
                  value={formData.admin_username || ''}
                  onChange={(e) => updateField('admin_username', e.target.value)}
                  className="input"
                  placeholder="admin"
                />
              </FormRow>
              <div className="mt-4">
                <button 
                  className="btn btn-secondary"
                  onClick={() => setShowPasswordModal(true)}
                >
                  <Key size={16} />
                  Change Admin Password
                </button>
              </div>
            </div>

            {/* Session Settings */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Key size={20} style={{ color: 'var(--meraki-blue)' }} />
                Session Settings
              </h3>
              <FormRow label="Access Token Expiry (minutes)">
                <input
                  type="number"
                  value={formData.access_token_expire_minutes || 30}
                  onChange={(e) => updateField('access_token_expire_minutes', parseInt(e.target.value))}
                  className="input"
                  min="5"
                  max="1440"
                />
              </FormRow>
            </div>

            {/* Database (read-only info) */}
            <div className="card">
              <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
                <Key size={20} style={{ color: 'var(--meraki-blue)' }} />
                Database
              </h3>
              <FormRow label="Database URL">
                <input
                  type="text"
                  value={formData.database_url || ''}
                  className="input"
                  disabled
                  style={{ backgroundColor: 'var(--gray-100)', cursor: 'not-allowed' }}
                />
              </FormRow>
              <p className="text-sm text-gray-500">
                Database location is configured via environment variable.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Password Change Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Change Admin Password</h3>
            <div className="space-y-4">
              <FormRow label="Current Password" required>
                <input
                  type="password"
                  value={passwordForm.current}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, current: e.target.value }))}
                  className="input"
                  placeholder="Enter current password"
                />
              </FormRow>
              <FormRow label="New Password" required>
                <input
                  type="password"
                  value={passwordForm.new}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, new: e.target.value }))}
                  className="input"
                  placeholder="Enter new password (min 8 characters)"
                />
              </FormRow>
              <FormRow label="Confirm New Password" required>
                <input
                  type="password"
                  value={passwordForm.confirm}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, confirm: e.target.value }))}
                  className="input"
                  placeholder="Confirm new password"
                />
              </FormRow>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowPasswordModal(false)
                  setPasswordForm({ current: '', new: '', confirm: '' })
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handlePasswordChange}
                disabled={passwordMutation.isPending}
              >
                {passwordMutation.isPending ? 'Changing...' : 'Change Password'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function FormRow({ 
  label, 
  required, 
  children 
}: { 
  label: string
  required?: boolean
  children: React.ReactNode 
}) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium mb-2">
        {label}
        {required && <span style={{ color: 'var(--danger)' }}> *</span>}
      </label>
      {children}
    </div>
  )
}

function SecretInput({
  value,
  onChange,
  show,
  onToggle,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  show: boolean
  onToggle: () => void
  placeholder?: string
}) {
  // Check if value is masked (saved but hidden)
  const isMasked = value === '***' || value?.startsWith('***')
  
  return (
    <div className="flex gap-2">
      <div style={{ flex: 1, position: 'relative' }}>
        <input
          type={show ? 'text' : 'password'}
          value={isMasked ? '' : value}
          onChange={(e) => onChange(e.target.value)}
          className="input"
          placeholder={isMasked ? '••••••••••••  (saved - enter new to change)' : placeholder}
          style={{ 
            width: '100%',
            backgroundColor: isMasked ? '#f0fdf4' : undefined,
            borderColor: isMasked ? '#22c55e' : undefined,
          }}
        />
        {isMasked && (
          <span style={{
            position: 'absolute',
            right: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: '12px',
            color: '#22c55e',
            fontWeight: 500,
          }}>
            ✓ Saved
          </span>
        )}
      </div>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onToggle}
        style={{ padding: '0 12px' }}
      >
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  )
}
