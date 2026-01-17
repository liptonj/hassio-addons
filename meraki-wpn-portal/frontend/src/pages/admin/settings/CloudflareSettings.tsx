import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Cloud, RefreshCw, CheckCircle, AlertTriangle, XCircle, ExternalLink } from 'lucide-react'
import { 
  getAllSettings, 
  updateSettings,
  testCloudflareConnection,
  getCloudflareOptions,
  configureCloudfareTunnel,
  disconnectCloudfareTunnel
} from '../../../api/client'

interface CloudflareSettings {
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

export default function CloudflareSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<CloudflareSettings>({
    cloudflare_local_url: 'http://localhost:8080',
  })
  const [cloudflareOptions, setCloudflareOptions] = useState<{
    tunnels: Array<{ id: string; name: string; status: string; label: string }>
    zones: Array<{ id: string; name: string; label: string }>
  }>({ tunnels: [], zones: [] })
  const [cloudflareConnected, setCloudflareConnected] = useState(false)
  const [cloudflareLoading, setCloudflareLoading] = useState(false)
  const [hostnameSubdomain, setHostnameSubdomain] = useState('')
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings-all'],
    queryFn: getAllSettings,
  })

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
      setTimeout(() => setNotification(null), 5000)
    },
  })

  useEffect(() => {
    if (settings) {
      const data = settings as Record<string, unknown>
      setFormData({
        cloudflare_enabled: data.cloudflare_enabled as boolean,
        cloudflare_api_token: data.cloudflare_api_token as string,
        cloudflare_account_id: data.cloudflare_account_id as string,
        cloudflare_tunnel_id: data.cloudflare_tunnel_id as string,
        cloudflare_tunnel_name: data.cloudflare_tunnel_name as string,
        cloudflare_zone_id: data.cloudflare_zone_id as string,
        cloudflare_zone_name: data.cloudflare_zone_name as string,
        cloudflare_hostname: data.cloudflare_hostname as string,
        cloudflare_local_url: data.cloudflare_local_url as string || 'http://localhost:8080',
      })
      if (data.cloudflare_hostname) {
        setHostnameSubdomain((data.cloudflare_hostname as string).split('.')[0])
      }
    }
  }, [settings])

  const handleTestCloudflare = async () => {
    if (!formData.cloudflare_api_token) {
      setNotification({ type: 'error', message: 'Please enter a Cloudflare API token first' })
      return
    }
    setCloudflareLoading(true)
    try {
      const tokenToUse = formData.cloudflare_api_token !== '***' ? formData.cloudflare_api_token : ''
      const result = await testCloudflareConnection(tokenToUse, formData.cloudflare_account_id || undefined)
      if (result.success) {
        setCloudflareConnected(true)
        setNotification({ type: 'success', message: result.message || 'Connected to Cloudflare!' })
        await loadCloudflareOptions()
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

  const loadCloudflareOptions = async () => {
    try {
      const apiToken = formData.cloudflare_api_token !== '***' ? formData.cloudflare_api_token : undefined
      const options = await getCloudflareOptions(apiToken, formData.cloudflare_account_id || undefined)
      if (options.success) {
        setCloudflareOptions({
          tunnels: options.tunnels || [],
          zones: options.zones || []
        })
        setCloudflareConnected(true)
      }
    } catch (error) {
      console.error('Failed to load Cloudflare options:', error)
    }
  }

  const handleConfigureCloudflare = async () => {
    if (!formData.cloudflare_tunnel_id || !formData.cloudflare_zone_id || !hostnameSubdomain) {
      setNotification({ type: 'error', message: 'Please select a tunnel, zone, and enter a hostname' })
      return
    }
    setCloudflareLoading(true)
    try {
      const hostname = `${hostnameSubdomain}.${formData.cloudflare_zone_name}`
      const result = await configureCloudfareTunnel(
        formData.cloudflare_tunnel_id,
        formData.cloudflare_zone_id,
        hostname,
        formData.cloudflare_local_url || 'http://localhost:8080',
        formData.cloudflare_api_token !== '***' ? formData.cloudflare_api_token : undefined,
        formData.cloudflare_account_id || undefined
      )
      if (result.success) {
        setNotification({ type: 'success', message: result.message })
        setFormData({
          ...formData,
          cloudflare_enabled: true,
          cloudflare_hostname: result.hostname,
          cloudflare_local_url: result.local_url,
          cloudflare_tunnel_name: result.tunnel_name,
        })
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
    if (!window.confirm('Disconnect the Cloudflare tunnel? The DNS record will remain.')) return
    setCloudflareLoading(true)
    try {
      const result = await disconnectCloudfareTunnel()
      if (result.success) {
        setNotification({ type: 'success', message: result.message })
        setFormData({
          ...formData,
          cloudflare_enabled: false,
          cloudflare_tunnel_id: '',
          cloudflare_hostname: '',
        })
        queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      }
    } catch (error) {
      setNotification({ type: 'error', message: 'Failed to disconnect tunnel' })
    } finally {
      setCloudflareLoading(false)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  const isMasked = formData.cloudflare_api_token === '***' || formData.cloudflare_api_token?.startsWith('***')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Cloudflare Tunnel</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Securely expose your portal to the internet
          </p>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
              : notification.type === 'warning'
              ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
          }`}>
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <XCircle size={20} />}
          {notification.message}
        </div>
      )}

      {/* Info */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">What is Cloudflare Tunnel?</h4>
        <p className="text-sm text-blue-800 dark:text-blue-300">
          Cloudflare Tunnels allow you to securely expose your portal to the internet without opening firewall ports. 
          Perfect for splash page redirects and remote access.
        </p>
      </div>

      {/* Connection Status */}
      {formData.cloudflare_enabled && formData.cloudflare_hostname && (
        <div className="card bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle size={20} className="text-green-600 dark:text-green-400" />
              <span className="font-medium text-green-600 dark:text-green-400">Tunnel Active</span>
              <a
                href={`https://${formData.cloudflare_hostname}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm underline text-meraki-blue"
              >
                {formData.cloudflare_hostname}
                <ExternalLink size={14} />
              </a>
            </div>
            <button
              onClick={handleDisconnectCloudflare}
              disabled={cloudflareLoading}
              className="btn btn-outline text-sm border-red-600 dark:border-red-700 text-red-600 dark:text-red-400"
            >
              Disconnect
            </button>
          </div>
        </div>
      )}

      {/* API Configuration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Cloud size={20} className="text-meraki-blue" />
            API Configuration
          </h3>
        </div>

        <div className="form-group">
          <label className="form-label">Cloudflare API Token <span className="text-red-500">*</span></label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="password"
                value={isMasked ? '' : (formData.cloudflare_api_token || '')}
                onChange={(e) => setFormData({ ...formData, cloudflare_api_token: e.target.value })}
                className={`input ${isMasked ? 'bg-green-50 dark:bg-green-900/20 border-green-500 dark:border-green-700' : ''}`}
                placeholder={isMasked ? '••••••••••••  (saved)' : 'Enter Cloudflare API Token'}
              />
              {isMasked && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-green-600 dark:text-green-400 font-medium">
                  ✓ Saved
                </span>
              )}
            </div>
            <button
              onClick={handleTestCloudflare}
              disabled={cloudflareLoading || !formData.cloudflare_api_token}
              className="btn btn-outline min-w-[120px]"
            >
              {cloudflareLoading ? <RefreshCw className="animate-spin" size={16} /> : 'Test & Load'}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Create a token with "Cloudflare Tunnel:Edit" and "Zone:DNS:Edit" permissions
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Account ID</label>
          <input
            type="text"
            value={formData.cloudflare_account_id || ''}
            onChange={(e) => setFormData({ ...formData, cloudflare_account_id: e.target.value })}
            className="input"
            placeholder="1a14a76e949f7da9e9acd50dd93612ac"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Find in Cloudflare Dashboard URL. Required for account-scoped tokens.
          </p>
        </div>
      </div>

      {/* Tunnel Configuration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Tunnel Configuration</h3>
        </div>

        <div className="form-group">
          <label className="form-label">Select Tunnel <span className="text-red-500">*</span></label>
          <select
            value={formData.cloudflare_tunnel_id || ''}
            onChange={(e) => {
              const tunnel = cloudflareOptions.tunnels.find(t => t.id === e.target.value)
              setFormData({
                ...formData,
                cloudflare_tunnel_id: e.target.value,
                cloudflare_tunnel_name: tunnel?.name,
              })
            }}
            className="input"
            disabled={!cloudflareConnected || cloudflareOptions.tunnels.length === 0}
          >
            <option value="">
              {!cloudflareConnected ? 'Test connection first...' : cloudflareOptions.tunnels.length === 0 ? 'No tunnels found' : 'Select a tunnel...'}
            </option>
            {cloudflareOptions.tunnels.map((tunnel) => (
              <option key={tunnel.id} value={tunnel.id}>{tunnel.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Domain <span className="text-red-500">*</span></label>
          <select
            value={formData.cloudflare_zone_id || ''}
            onChange={(e) => {
              const zone = cloudflareOptions.zones.find(z => z.id === e.target.value)
              setFormData({
                ...formData,
                cloudflare_zone_id: e.target.value,
                cloudflare_zone_name: zone?.name,
              })
            }}
            className="input"
            disabled={!cloudflareConnected || cloudflareOptions.zones.length === 0}
          >
            <option value="">
              {!cloudflareConnected ? 'Test connection first...' : cloudflareOptions.zones.length === 0 ? 'No domains found' : 'Select a domain...'}
            </option>
            {cloudflareOptions.zones.map((zone) => (
              <option key={zone.id} value={zone.id}>{zone.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Public Hostname <span className="text-red-500">*</span></label>
          <div className="flex gap-2 items-center">
            <input
              type="text"
              value={hostnameSubdomain}
              onChange={(e) => setHostnameSubdomain(e.target.value.replace(/[^a-z0-9-]/gi, '').toLowerCase())}
              className="input max-w-[150px]"
              placeholder="portal"
              disabled={!formData.cloudflare_zone_id}
            />
            <span className="text-gray-600 dark:text-gray-400">.</span>
            <span className="text-gray-700 dark:text-gray-300">
              {formData.cloudflare_zone_name || 'example.com'}
            </span>
          </div>
          {hostnameSubdomain && formData.cloudflare_zone_name && (
            <p className="text-xs mt-1 text-meraki-blue">
              Portal will be accessible at: <strong>https://{hostnameSubdomain}.{formData.cloudflare_zone_name}</strong>
            </p>
          )}
        </div>

        <div className="form-group">
          <label className="form-label">Local Service URL</label>
          <input
            type="text"
            value={formData.cloudflare_local_url || ''}
            onChange={(e) => setFormData({ ...formData, cloudflare_local_url: e.target.value })}
            className="input"
            placeholder="http://localhost:8080"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            The local address where the portal is running
          </p>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={handleConfigureCloudflare}
            disabled={cloudflareLoading || !formData.cloudflare_tunnel_id || !formData.cloudflare_zone_id || !hostnameSubdomain}
            className="btn btn-primary"
          >
            {cloudflareLoading ? <RefreshCw className="animate-spin" size={16} /> : formData.cloudflare_enabled ? 'Update Configuration' : 'Configure Tunnel'}
          </button>
        </div>
      </div>
    </div>
  )
}
