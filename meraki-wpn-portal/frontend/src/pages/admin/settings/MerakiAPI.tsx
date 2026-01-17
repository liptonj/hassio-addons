import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Key, Eye, EyeOff, TestTube, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings, testConnection, getIPSKOptions } from '../../../api/client'

interface MerakiSettings {
  meraki_api_key?: string
  meraki_org_id?: string
}

export default function MerakiAPI() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<MerakiSettings>({})
  const [showApiKey, setShowApiKey] = useState(false)
  const [merakiOrganizations, setMerakiOrganizations] = useState<Array<{ id: string; name: string }>>([])
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

  useEffect(() => {
    if (ipskOptions?.organizations) {
      setMerakiOrganizations(ipskOptions.organizations)
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
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const testMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) => testConnection(settings),
    onSuccess: (data) => {
      const merakiTest = data.tests?.meraki_api as
        | { organizations?: Array<{ id: string; name: string }> }
        | undefined

      if (merakiTest?.organizations?.length) {
        setMerakiOrganizations(merakiTest.organizations)
        if (!formData.meraki_org_id) {
          setFormData(prev => ({ ...prev, meraki_org_id: merakiTest.organizations[0].id }))
        }
      }

      const resultMessages = Object.entries(data.tests || {})
        .map(([key, val]) => `${key}: ${val.message}`)
        .join('; ')

      setNotification({
        type: data.overall_success ? 'success' : 'error',
        message: resultMessages || (data.overall_success ? 'Connection successful' : 'Connection failed'),
      })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Connection test failed',
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  useEffect(() => {
    if (settings) {
      setFormData({
        meraki_api_key: (settings as Record<string, unknown>).meraki_api_key as string,
        meraki_org_id: (settings as Record<string, unknown>).meraki_org_id as string,
      })
    }
  }, [settings])

  const handleSave = () => {
    const sanitized = { ...formData }
    // Don't send masked secrets
    if (sanitized.meraki_api_key?.startsWith('***')) {
      delete sanitized.meraki_api_key
    }
    saveMutation.mutate(sanitized)
  }

  const handleTest = () => {
    const testData = { ...formData }
    // Don't send masked secrets for test
    if (testData.meraki_api_key?.startsWith('***')) {
      delete testData.meraki_api_key
    }
    testMutation.mutate(testData)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  const isMasked = formData.meraki_api_key === '***' || formData.meraki_api_key?.startsWith('***')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Meraki Dashboard API</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure API access to Meraki Dashboard
          </p>
        </div>
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

      {/* API Configuration */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <h3 className="card-title flex items-center gap-2">
              <Key size={20} className="text-meraki-blue" />
              API Configuration
            </h3>
            {merakiOrganizations.length > 0 && (
              <span className="badge badge-success">
                Connected ({merakiOrganizations.length} orgs)
              </span>
            )}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">
            API Key <span className="text-red-500">*</span>
          </label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={isMasked ? '' : (formData.meraki_api_key || '')}
                onChange={(e) => setFormData({ ...formData, meraki_api_key: e.target.value })}
                className={`input ${isMasked ? 'bg-green-50 dark:bg-green-900/20 border-green-500 dark:border-green-700' : ''}`}
                placeholder={isMasked ? '••••••••••••  (saved - enter new to change)' : 'Enter Meraki Dashboard API key'}
              />
              {isMasked && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-green-600 dark:text-green-400 font-medium">
                  ✓ Saved
                </span>
              )}
            </div>
            <button
              type="button"
              className="btn btn-secondary px-3"
              onClick={() => setShowApiKey(!showApiKey)}
            >
              {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Get your API key from Meraki Dashboard: Organization → Settings → Dashboard API access
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Organization</label>
          {merakiOrganizations.length > 0 ? (
            <select
              value={formData.meraki_org_id || ''}
              onChange={(e) => setFormData({ ...formData, meraki_org_id: e.target.value })}
              className="input"
            >
              <option value="">Select an organization...</option>
              {merakiOrganizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          ) : (
            <select className="input bg-gray-100 dark:bg-gray-900" disabled>
              <option>Run Test Connection to load organizations</option>
            </select>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Select the organization to manage
          </p>
        </div>
      </div>

      {/* Help */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">How to get your API key:</h4>
        <ol className="text-sm text-blue-800 dark:text-blue-300 space-y-1 ml-4 list-decimal">
          <li>Log in to your Meraki Dashboard</li>
          <li>Navigate to Organization → Settings</li>
          <li>Scroll down to "Dashboard API access"</li>
          <li>Enable API access if not already enabled</li>
          <li>Generate a new API key or copy your existing key</li>
          <li>Paste the key above and click "Test Connection"</li>
        </ol>
      </div>
    </div>
  )
}
