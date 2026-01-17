import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Shield, Key, Eye, EyeOff, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface AdvancedSettings {
  admin_username?: string
  admin_notification_email?: string
  secret_key?: string
  access_token_expire_minutes?: number
  ha_url?: string
  ha_token?: string
  cors_origins?: string
  database_url?: string
}

export default function AdvancedSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<AdvancedSettings>({
    access_token_expire_minutes: 30,
    cors_origins: '*',
  })
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current: '', new: '', confirm: '' })
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
      setTimeout(() => setNotification(null), 5000)
    },
  })

  useEffect(() => {
    if (settings) {
      const data = settings as Record<string, unknown>
      setFormData({
        admin_username: data.admin_username as string,
        admin_notification_email: data.admin_notification_email as string,
        secret_key: data.secret_key as string,
        access_token_expire_minutes: data.access_token_expire_minutes as number,
        ha_url: data.ha_url as string,
        ha_token: data.ha_token as string,
        cors_origins: data.cors_origins as string,
        database_url: data.database_url as string,
      })
    }
  }, [settings])

  const handleSave = () => {
    const sanitized = { ...formData }
    // Don't send masked secrets
    if (sanitized.secret_key?.startsWith('***')) {
      delete sanitized.secret_key
    }
    if (sanitized.ha_token?.startsWith('***')) {
      delete sanitized.ha_token
    }
    delete sanitized.database_url // Read-only
    saveMutation.mutate(sanitized)
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
            placeholder={isMasked ? '••••••••••••  (saved)' : placeholder}
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Advanced Settings</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Admin security, session management, and technical configuration
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

      {/* Admin Security */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Shield size={20} className="text-meraki-blue" />
            Admin Security
          </h3>
        </div>

        <div className="form-group">
          <label className="form-label">Admin Username</label>
          <input
            type="text"
            value={formData.admin_username || ''}
            onChange={(e) => setFormData({ ...formData, admin_username: e.target.value })}
            className="input"
            placeholder="admin"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Admin Notification Email</label>
          <input
            type="email"
            value={formData.admin_notification_email || ''}
            onChange={(e) => setFormData({ ...formData, admin_notification_email: e.target.value })}
            className="input"
            placeholder="admin@example.com"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Receive notifications about system events
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Application Secret Key</label>
          <SecretInput field="secret_key" placeholder="Enter a secure random secret" />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Used for JWT token signing and encryption
          </p>
        </div>

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
        <div className="card-header">
          <h3 className="card-title">Session Settings</h3>
        </div>

        <div className="form-group">
          <label className="form-label">Access Token Expiry (minutes)</label>
          <input
            type="number"
            value={formData.access_token_expire_minutes ?? 30}
            onChange={(e) => setFormData({ ...formData, access_token_expire_minutes: parseInt(e.target.value, 10) })}
            className="input"
            min="5"
            max="1440"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            How long admin sessions remain active (5-1440 minutes)
          </p>
        </div>
      </div>

      {/* Home Assistant */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Home Assistant Integration</h3>
        </div>

        <div className="form-group">
          <label className="form-label">Home Assistant URL</label>
          <input
            type="url"
            value={formData.ha_url || ''}
            onChange={(e) => setFormData({ ...formData, ha_url: e.target.value })}
            className="input"
            placeholder="http://supervisor/core"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            URL of your Home Assistant instance
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Home Assistant Token</label>
          <SecretInput field="ha_token" placeholder="Enter Home Assistant long-lived token" />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Long-lived access token for Home Assistant API
          </p>
        </div>
      </div>

      {/* CORS */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">CORS Configuration</h3>
        </div>

        <div className="form-group">
          <label className="form-label">Allowed Origins</label>
          <input
            type="text"
            value={formData.cors_origins ?? '*'}
            onChange={(e) => setFormData({ ...formData, cors_origins: e.target.value })}
            className="input"
            placeholder="* or https://example.com"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Comma-separated list of allowed origins, or * for all
          </p>
        </div>
      </div>

      {/* Database */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Database</h3>
        </div>

        <div className="form-group">
          <label className="form-label">Database URL</label>
          <input
            type="text"
            value={formData.database_url || ''}
            className="input bg-gray-100 dark:bg-gray-900 cursor-not-allowed"
            disabled
            readOnly
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Database location is configured via environment variable (read-only)
          </p>
        </div>
      </div>

      {/* Password Change Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Change Admin Password</h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">Current Password <span className="text-red-500">*</span></label>
                <input
                  type="password"
                  value={passwordForm.current}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })}
                  className="input"
                  placeholder="Enter current password"
                />
              </div>
              <div className="form-group">
                <label className="form-label">New Password <span className="text-red-500">*</span></label>
                <input
                  type="password"
                  value={passwordForm.new}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new: e.target.value })}
                  className="input"
                  placeholder="Min 8 characters"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Confirm New Password <span className="text-red-500">*</span></label>
                <input
                  type="password"
                  value={passwordForm.confirm}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })}
                  className="input"
                  placeholder="Confirm new password"
                />
              </div>
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
