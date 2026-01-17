import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Key, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface IPSKSettings {
  default_ipsk_duration_hours?: number
  passphrase_length?: number
  allow_custom_psk?: boolean
  psk_min_length?: number
  psk_max_length?: number
}

export default function IPSKSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<IPSKSettings>({
    default_ipsk_duration_hours: 0,
    passphrase_length: 12,
    allow_custom_psk: true,
    psk_min_length: 8,
    psk_max_length: 63,
  })
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
        default_ipsk_duration_hours: data.default_ipsk_duration_hours as number,
        passphrase_length: data.passphrase_length as number,
        allow_custom_psk: data.allow_custom_psk as boolean,
        psk_min_length: data.psk_min_length as number,
        psk_max_length: data.psk_max_length as number,
      })
    }
  }, [settings])

  const handleSave = () => {
    // Validation
    if (formData.psk_min_length && formData.psk_max_length && formData.psk_min_length > formData.psk_max_length) {
      setNotification({
        type: 'error',
        message: 'PSK minimum length cannot be greater than maximum length',
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">IPSK Settings</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure Identity Pre-Shared Key defaults and validation
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saveMutation.isPending}
        >
          <Save size={16} />
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
              : notification.type === 'warning'
              ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
          }`}
        >
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <XCircle size={20} />}
          {notification.message}
        </div>
      )}

      {/* IPSK Defaults */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Key size={20} className="text-meraki-blue" />
            IPSK Defaults
          </h3>
        </div>

        <div className="form-group">
          <label className="form-label">Default IPSK Duration (hours)</label>
          <input
            type="number"
            value={formData.default_ipsk_duration_hours ?? 0}
            onChange={(e) => setFormData({ ...formData, default_ipsk_duration_hours: parseInt(e.target.value, 10) })}
            className="input"
            min="0"
            max="8760"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Default expiration time for new IPSKs (0 = never expires, max 8760 = 1 year)
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Generated Passphrase Length</label>
          <input
            type="number"
            value={formData.passphrase_length ?? 12}
            onChange={(e) => setFormData({ ...formData, passphrase_length: parseInt(e.target.value, 10) })}
            className="input"
            min="8"
            max="64"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Length of auto-generated passphrases (8-64 characters)
          </p>
        </div>
      </div>

      {/* Custom PSK Settings */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Custom PSK Settings</h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.allow_custom_psk ?? true}
              onChange={(e) => setFormData({ ...formData, allow_custom_psk: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Allow Custom PSK</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Allow users to enter their own PSK during registration
          </p>
        </div>

        {formData.allow_custom_psk && (
          <>
            <div className="form-group">
              <label className="form-label">PSK Minimum Length</label>
              <input
                type="number"
                value={formData.psk_min_length ?? 8}
                onChange={(e) => setFormData({ ...formData, psk_min_length: parseInt(e.target.value, 10) })}
                className="input"
                min="8"
                max="63"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Minimum length for custom PSKs (WPA2/WPA3 minimum is 8)
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">PSK Maximum Length</label>
              <input
                type="number"
                value={formData.psk_max_length ?? 63}
                onChange={(e) => setFormData({ ...formData, psk_max_length: parseInt(e.target.value, 10) })}
                className="input"
                min="8"
                max="63"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Maximum length for custom PSKs (WPA2/WPA3 maximum is 63)
              </p>
            </div>
          </>
        )}
      </div>

      {/* Info Box */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">About IPSK Settings</h4>
        <div className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
          <p>
            <strong>Default Duration:</strong> Sets how long newly created IPSKs remain valid. Set to 0 for no expiration.
          </p>
          <p>
            <strong>Passphrase Length:</strong> Controls the length of automatically generated passphrases. Longer is more secure.
          </p>
          <p>
            <strong>Custom PSK:</strong> When enabled, users can choose their own memorable password during registration (subject to min/max length requirements).
          </p>
        </div>
      </div>
    </div>
  )
}
