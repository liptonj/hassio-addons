import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Wifi, CheckCircle, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'
import { getAllSettings, updateSettings, getIPSKOptions } from '../../../api/client'

interface SSIDConfigSettings {
  default_group_policy_id?: string
  default_group_policy_name?: string
  default_guest_group_policy_id?: string
  default_guest_group_policy_name?: string
  default_network_id?: string
  default_ssid_number?: number
}

export default function SSIDConfiguration() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<SSIDConfigSettings>({})
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

  const merakiOptions = ipskOptions || { networks: [], ssids: [], group_policies: [] }

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
      setFormData({
        default_group_policy_id: settings.default_group_policy_id,
        default_group_policy_name: settings.default_group_policy_name,
        default_guest_group_policy_id: settings.default_guest_group_policy_id,
        default_guest_group_policy_name: settings.default_guest_group_policy_name,
        default_network_id: settings.default_network_id,
        default_ssid_number: settings.default_ssid_number,
      })
    }
  }, [settings])

  const handleSave = () => {
    if (!formData.default_group_policy_id) {
      setNotification({
        type: 'error',
        message: 'Registered Users Group Policy is required',
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
          <h1 className="text-2xl font-bold">SSID Configuration</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure group policies for your WPN-enabled SSID
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

      {/* Two-Tier Model Explanation */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200">
        <div className="flex items-start gap-3">
          <HelpCircle size={20} className="text-blue-600 flex-shrink-0 mt-1" />
          <div>
            <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
              Understanding the Two-Tier Access Model
            </h3>
            <div className="space-y-2 text-sm text-blue-800 dark:text-blue-200">
              <p>
                <strong>Registered Users:</strong> Users with personal iPSKs are assigned to the "Registered Users" group policy.
                This policy should have <strong>splash page bypass enabled</strong> for direct internet access.
              </p>
              <p>
                <strong>Guest/Default Users:</strong> Users connecting with the default PSK are assigned to the optional "Guest" group policy.
                They will see the splash page where they can register for a personal iPSK.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Form */}
      <div className="card">
        <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
          <Wifi size={20} className="text-meraki-blue" />
          Group Policy Assignment
        </h3>

        {!formData.default_network_id || formData.default_ssid_number === undefined ? (
          <div className="p-4 rounded-lg bg-yellow-100 border border-yellow-300">
            <p className="text-sm text-yellow-800">
              <strong>Please select a network and SSID first.</strong>
              <button
                onClick={() => navigate('/admin/settings/network/selection')}
                className="underline ml-2"
              >
                Go to Network Selection →
              </button>
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Registered Users Policy */}
            <div className="form-group">
              <label className="form-label">
                Registered Users Group Policy <span className="text-red-600">*</span>
              </label>
              {merakiOptions.group_policies.length > 0 ? (
                <select
                  value={formData.default_group_policy_id || ''}
                  onChange={(e) => {
                    const selectedPolicy = merakiOptions.group_policies.find(
                      (p) => p.id === e.target.value
                    )
                    setFormData({
                      ...formData,
                      default_group_policy_id: e.target.value,
                      default_group_policy_name: selectedPolicy?.name,
                    })
                  }}
                  className={`input ${!formData.default_group_policy_id ? 'border-yellow-500' : ''}`}
                >
                  <option value="">Select a group policy...</option>
                  {merakiOptions.group_policies.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name}
                    </option>
                  ))}
                </select>
              ) : (
                <select className="input bg-gray-100" disabled>
                  <option>Create group policies in Meraki Dashboard first</option>
                </select>
              )}
              <p className="text-xs text-gray-500 mt-1">
                For users with personal iPSKs. <strong>Should have splash bypass enabled.</strong>
              </p>
            </div>

            {/* Guest/Default Policy */}
            <div className="form-group">
              <label className="form-label">Guest/Default Users Group Policy</label>
              {merakiOptions.group_policies.length > 0 ? (
                <select
                  value={formData.default_guest_group_policy_id || ''}
                  onChange={(e) => {
                    const selectedPolicy = merakiOptions.group_policies.find(
                      (p) => p.id === e.target.value
                    )
                    setFormData({
                      ...formData,
                      default_guest_group_policy_id: e.target.value,
                      default_guest_group_policy_name: selectedPolicy?.name,
                    })
                  }}
                  className="input"
                >
                  <option value="">None (splash page only)</option>
                  {merakiOptions.group_policies.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name}
                    </option>
                  ))}
                </select>
              ) : (
                <select className="input bg-gray-100" disabled>
                  <option>Select a network first</option>
                </select>
              )}
              <p className="text-xs text-gray-500 mt-1">
                Optional. For users connecting with the default PSK. Leave empty to use splash page only.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
