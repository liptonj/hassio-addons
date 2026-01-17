import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, LogIn, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface LoginMethodsSettings {
  universal_login_enabled?: boolean
  show_login_method_selector?: boolean
  auth_method_local?: boolean
  auth_method_oauth?: boolean
  auth_method_invite_code?: boolean
  auth_method_self_registration?: boolean
  registration_mode?: 'open' | 'invite_only' | 'approval_required'
  approval_notification_email?: string
}

export default function LoginMethods() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<LoginMethodsSettings>({
    universal_login_enabled: true,
    show_login_method_selector: false,
    auth_method_local: true,
    auth_method_oauth: false,
    auth_method_invite_code: true,
    auth_method_self_registration: true,
    registration_mode: 'open',
    approval_notification_email: '',
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
        universal_login_enabled: data.universal_login_enabled as boolean,
        show_login_method_selector: data.show_login_method_selector as boolean,
        auth_method_local: data.auth_method_local as boolean,
        auth_method_oauth: data.auth_method_oauth as boolean,
        auth_method_invite_code: data.auth_method_invite_code as boolean,
        auth_method_self_registration: data.auth_method_self_registration as boolean,
        registration_mode: (data.registration_mode as 'open' | 'invite_only' | 'approval_required') || 'open',
        approval_notification_email: (data.approval_notification_email as string) || '',
      })
    }
  }, [settings])

  const handleSave = () => {
    // Validation: At least one auth method must be enabled
    const hasMethod = formData.auth_method_local || 
                      formData.auth_method_oauth || 
                      formData.auth_method_invite_code || 
                      formData.auth_method_self_registration

    if (!hasMethod) {
      setNotification({
        type: 'error',
        message: 'At least one authentication method must be enabled',
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Login Methods</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure available authentication methods for users
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

      {/* Universal Login */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <LogIn size={20} className="text-meraki-blue" />
            Universal Login Options
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.universal_login_enabled ?? true}
              onChange={(e) => setFormData({ ...formData, universal_login_enabled: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Enable Universal Login</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Allow users to log in from a dedicated login page (not just splash page)
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.show_login_method_selector ?? false}
              onChange={(e) => setFormData({ ...formData, show_login_method_selector: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Show Login Method Selector</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Display a method selector on the login page (useful when multiple methods are enabled)
          </p>
        </div>
      </div>

      {/* Registration Mode */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Registration Mode</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Control how new users can register for WiFi access
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Registration Mode</label>
          <select
            value={formData.registration_mode || 'open'}
            onChange={(e) => setFormData({ 
              ...formData, 
              registration_mode: e.target.value as 'open' | 'invite_only' | 'approval_required' 
            })}
            className="input"
          >
            <option value="open">Open Registration</option>
            <option value="invite_only">Invite Code Required</option>
            <option value="approval_required">Admin Approval Required</option>
          </select>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-2 space-y-1">
            <p><strong>Open:</strong> Anyone can register and get immediate WiFi access</p>
            <p><strong>Invite Code Required:</strong> Users must have a valid invite code to register</p>
            <p><strong>Admin Approval:</strong> New registrations are pending until an admin approves</p>
          </div>
        </div>

        {formData.registration_mode === 'approval_required' && (
          <div className="form-group mt-4">
            <label className="form-label">Notification Email (Optional)</label>
            <input
              type="email"
              value={formData.approval_notification_email || ''}
              onChange={(e) => setFormData({ ...formData, approval_notification_email: e.target.value })}
              placeholder="admin@example.com"
              className="input"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Receive email notifications when new registrations are pending approval
            </p>
          </div>
        )}
      </div>

      {/* Allowed Authentication Methods */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Allowed Authentication Methods</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Select which authentication methods users can use to access the portal
          </p>
        </div>

        <div className="space-y-4">
          <div className="form-group">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.auth_method_local ?? true}
                onChange={(e) => setFormData({ ...formData, auth_method_local: e.target.checked })}
                className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
              />
              <span className="form-label mb-0">Local Password</span>
            </label>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
              Traditional username and password authentication
            </p>
          </div>

          <div className="form-group">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.auth_method_oauth ?? false}
                onChange={(e) => setFormData({ ...formData, auth_method_oauth: e.target.checked })}
                className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
              />
              <span className="form-label mb-0">OAuth / SSO</span>
            </label>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
              Single Sign-On via OAuth providers (Duo, Microsoft Entra ID)
            </p>
            {formData.auth_method_oauth && (
              <div className="mt-2 ml-7 p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
                <p className="text-xs text-yellow-800 dark:text-yellow-200">
                  ⚠️ Make sure to configure OAuth settings in the OAuth / SSO page
                </p>
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.auth_method_invite_code ?? true}
                onChange={(e) => setFormData({ ...formData, auth_method_invite_code: e.target.checked })}
                className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
              />
              <span className="form-label mb-0">Invite Code</span>
            </label>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
              Registration via invite codes generated by administrators
            </p>
          </div>

          <div className="form-group">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.auth_method_self_registration ?? true}
                onChange={(e) => setFormData({ ...formData, auth_method_self_registration: e.target.checked })}
                className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
              />
              <span className="form-label mb-0">Self-Registration</span>
            </label>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
              Allow users to create their own accounts without invite codes
            </p>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">About Login Methods</h4>
        <div className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
          <p>
            <strong>Universal Login:</strong> Provides a dedicated login page separate from the Meraki splash page.
          </p>
          <p>
            <strong>Method Selector:</strong> Shows a chooser when multiple authentication methods are available.
          </p>
          <p>
            <strong>At least one method must be enabled</strong> for users to authenticate.
          </p>
        </div>
      </div>
    </div>
  )
}
