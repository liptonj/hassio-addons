import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Wifi, CheckCircle, AlertTriangle, XCircle, Settings2, Wand2, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getAllSettings, updateSettings, getIPSKOptions } from '../../../api/client'

interface NetworkSettings {
  default_network_id?: string
  default_ssid_number?: number
}

export default function NetworkSelection() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<NetworkSettings>({})
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings-all'],
    queryFn: getAllSettings,
  })

  const { data: ipskOptions } = useQuery({
    queryKey: ['ipsk-options'],
    queryFn: getIPSKOptions,
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
        default_network_id: data.default_network_id as string,
        default_ssid_number: data.default_ssid_number as number,
      })
    }
  }, [settings])

  const handleSave = () => {
    if (!formData.default_network_id || formData.default_ssid_number === undefined) {
      setNotification({
        type: 'error',
        message: 'Please select both network and SSID',
      })
      return
    }
    saveMutation.mutate(formData)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  const networks = ipskOptions?.networks || []
  const ssids = ipskOptions?.ssids || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Network & SSID Selection</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Select the Meraki network and SSID for WPN configuration
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saveMutation.isPending || !formData.default_network_id || formData.default_ssid_number === undefined}
        >
          <Save size={16} />
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
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

      {/* Network Selection */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Wifi size={20} className="text-meraki-blue" />
            Network &amp; SSID Selection
          </h3>
        </div>

        {networks.length === 0 && (
          <div className="p-4 mb-4 rounded-lg bg-yellow-100 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-800">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              <strong>No connection to Meraki Dashboard.</strong> Configure your Meraki API key in the Meraki API settings page.
            </p>
          </div>
        )}

        <div className="form-group">
          <label className="form-label">
            Network <span className="text-red-500">*</span>
          </label>
          {networks.length > 0 ? (
            <select
              value={formData.default_network_id || ''}
              onChange={(e) => setFormData({ ...formData, default_network_id: e.target.value })}
              className="input"
            >
              <option value="">Select a network...</option>
              {networks.map((network: { id: string; name: string }) => (
                <option key={network.id} value={network.id}>
                  {network.name}
                </option>
              ))}
            </select>
          ) : (
            <select className="input bg-gray-100 dark:bg-gray-900" disabled>
              <option>Connect to Meraki to load networks</option>
            </select>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Select the Meraki network where you want to configure WPN
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">
            SSID <span className="text-red-500">*</span>
          </label>
          {ssids.length > 0 ? (
            <select
              value={formData.default_ssid_number ?? ''}
              onChange={(e) => setFormData({ ...formData, default_ssid_number: parseInt(e.target.value, 10) })}
              className="input"
            >
              <option value="">Select an SSID...</option>
              {ssids.map((ssid: { number: number; name: string }) => (
                <option key={ssid.number} value={ssid.number}>
                  {ssid.name}
                </option>
              ))}
            </select>
          ) : (
            <select className="input bg-gray-100 dark:bg-gray-900" disabled>
              <option>Select a network first</option>
            </select>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Must be configured with "Identity PSK without RADIUS" and WPN enabled
          </p>
        </div>
      </div>

      {/* Related Settings Navigation */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Related Settings</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            After selecting your network and SSID, configure these additional settings:
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Link
            to="/admin/settings/network/ssid"
            className="flex items-center gap-4 p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
            data-testid="ssid-config-link"
          >
            <div className="p-3 rounded-lg bg-teal-100 dark:bg-teal-900/30">
              <Settings2 size={24} className="text-teal-600 dark:text-teal-400" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900 dark:text-gray-100">SSID Configuration</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Configure group policies for user access control
              </p>
            </div>
            <ChevronRight size={20} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
          </Link>
          <Link
            to="/admin/settings/network/wpn-setup"
            className="flex items-center gap-4 p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
            data-testid="wpn-wizard-link"
          >
            <div className="p-3 rounded-lg bg-purple-100 dark:bg-purple-900/30">
              <Wand2 size={24} className="text-purple-600 dark:text-purple-400" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900 dark:text-gray-100">WPN Setup Wizard</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Generate WPN credentials and configuration
              </p>
            </div>
            <ChevronRight size={20} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
          </Link>
        </div>
      </div>
    </div>
  )
}
