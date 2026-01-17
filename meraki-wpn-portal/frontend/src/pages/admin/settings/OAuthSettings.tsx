import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Shield, Eye, EyeOff, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface OAuthSettings {
  enable_oauth?: boolean
  oauth_provider?: string
  oauth_admin_only?: boolean
  oauth_auto_provision?: boolean
  oauth_callback_url?: string
  duo_client_id?: string
  duo_client_secret?: string
  duo_api_hostname?: string
  entra_client_id?: string
  entra_client_secret?: string
  entra_tenant_id?: string
}

export default function OAuthSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<OAuthSettings>({
    enable_oauth: false,
    oauth_provider: 'none',
    oauth_admin_only: false,
    oauth_auto_provision: true,
  })
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
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
        enable_oauth: data.enable_oauth as boolean,
        oauth_provider: data.oauth_provider as string,
        oauth_admin_only: data.oauth_admin_only as boolean,
        oauth_auto_provision: data.oauth_auto_provision as boolean,
        oauth_callback_url: data.oauth_callback_url as string,
        duo_client_id: data.duo_client_id as string,
        duo_client_secret: data.duo_client_secret as string,
        duo_api_hostname: data.duo_api_hostname as string,
        entra_client_id: data.entra_client_id as string,
        entra_client_secret: data.entra_client_secret as string,
        entra_tenant_id: data.entra_tenant_id as string,
      })
    }
  }, [settings])

  const handleSave = () => {
    const sanitized = { ...formData }
    // Don't send masked secrets
    if (sanitized.duo_client_secret?.startsWith('***')) {
      delete sanitized.duo_client_secret
    }
    if (sanitized.entra_client_secret?.startsWith('***')) {
      delete sanitized.entra_client_secret
    }
    saveMutation.mutate(sanitized)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  const SecretInput = ({ field, placeholder }: { field: string; placeholder: string }) => {
    const isMasked = (formData as Record<string, string>)[field] === '***' || (formData as Record<string, string>)[field]?.startsWith('***')
    return (
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <input
            type={showSecrets[field] ? 'text' : 'password'}
            value={isMasked ? '' : ((formData as Record<string, string>)[field] || '')}
            onChange={(e) => setFormData({ ...formData, [field]: e.target.value })}
            className={`input ${isMasked ? 'bg-green-50 dark:bg-green-900/20 border-green-500 dark:border-green-700' : ''}`}
            placeholder={isMasked ? '••••••••••••  (saved - enter new to change)' : placeholder}
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
          onClick={() => setShowSecrets({ ...showSecrets, [field]: !showSecrets[field] })}
        >
          {showSecrets[field] ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">OAuth / SSO</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure single sign-on authentication providers
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

      {/* OAuth Configuration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Shield size={20} className="text-meraki-blue" />
            OAuth Configuration
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.enable_oauth ?? false}
              onChange={(e) => setFormData({ ...formData, enable_oauth: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Enable OAuth / SSO</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Allow users to authenticate using external OAuth providers
          </p>
        </div>

        {formData.enable_oauth && (
          <>
            <div className="form-group">
              <label className="form-label">OAuth Provider</label>
              <select
                value={formData.oauth_provider || 'none'}
                onChange={(e) => setFormData({ ...formData, oauth_provider: e.target.value })}
                className="input"
              >
                <option value="none">None</option>
                <option value="duo">Duo Security</option>
                <option value="entra">Microsoft Entra ID</option>
              </select>
            </div>

            <div className="form-group">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.oauth_admin_only ?? false}
                  onChange={(e) => setFormData({ ...formData, oauth_admin_only: e.target.checked })}
                  className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
                />
                <span className="form-label mb-0">Admin Only</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
                Restrict OAuth authentication to admin users only
              </p>
            </div>

            <div className="form-group">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.oauth_auto_provision ?? true}
                  onChange={(e) => setFormData({ ...formData, oauth_auto_provision: e.target.checked })}
                  className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
                />
                <span className="form-label mb-0">Auto-Provision Users</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
                Automatically create user accounts on first OAuth login
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Callback URL</label>
              <input
                type="url"
                value={formData.oauth_callback_url || ''}
                onChange={(e) => setFormData({ ...formData, oauth_callback_url: e.target.value })}
                className="input"
                placeholder="https://your-domain.com/api/auth/callback"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                OAuth redirect/callback URL (configure this in your OAuth provider)
              </p>
            </div>
          </>
        )}
      </div>

      {/* Duo Security */}
      {formData.enable_oauth && formData.oauth_provider === 'duo' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Duo Security Settings</h3>
          </div>

          <div className="form-group">
            <label className="form-label">Duo Client ID <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={formData.duo_client_id || ''}
              onChange={(e) => setFormData({ ...formData, duo_client_id: e.target.value })}
              className="input"
              placeholder="Enter Duo Client ID"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Duo Client Secret <span className="text-red-500">*</span></label>
            <SecretInput field="duo_client_secret" placeholder="Enter Duo Client Secret" />
          </div>

          <div className="form-group">
            <label className="form-label">Duo API Hostname <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={formData.duo_api_hostname || ''}
              onChange={(e) => setFormData({ ...formData, duo_api_hostname: e.target.value })}
              className="input"
              placeholder="api-xxxxxxxx.duosecurity.com"
            />
          </div>
        </div>
      )}

      {/* Microsoft Entra ID */}
      {formData.enable_oauth && formData.oauth_provider === 'entra' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Microsoft Entra ID Settings</h3>
          </div>

          <div className="form-group">
            <label className="form-label">Entra Client ID <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={formData.entra_client_id || ''}
              onChange={(e) => setFormData({ ...formData, entra_client_id: e.target.value })}
              className="input"
              placeholder="Enter Application (client) ID"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Entra Client Secret <span className="text-red-500">*</span></label>
            <SecretInput field="entra_client_secret" placeholder="Enter Client Secret Value" />
          </div>

          <div className="form-group">
            <label className="form-label">Entra Tenant ID <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={formData.entra_tenant_id || ''}
              onChange={(e) => setFormData({ ...formData, entra_tenant_id: e.target.value })}
              className="input"
              placeholder="Enter Directory (tenant) ID"
            />
          </div>
        </div>
      )}
    </div>
  )
}
