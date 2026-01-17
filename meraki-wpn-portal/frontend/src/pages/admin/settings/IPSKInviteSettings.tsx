import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Clock, Ticket, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface IPSKInviteSettings {
  // IPSK Expiration
  ipsk_expiration_check_enabled?: boolean
  ipsk_expiration_check_interval_hours?: number
  ipsk_cleanup_action?: string
  ipsk_expiration_warning_days?: string
  ipsk_expiration_email_enabled?: boolean
  // Invite Codes
  auth_invite_codes?: boolean
  invite_code_email_restriction?: boolean
  invite_code_single_use?: boolean
}

export default function IPSKInviteSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<IPSKInviteSettings>({
    ipsk_expiration_check_enabled: true,
    ipsk_expiration_check_interval_hours: 1,
    ipsk_cleanup_action: 'soft_delete',
    ipsk_expiration_warning_days: '7,3,1',
    ipsk_expiration_email_enabled: false,
    auth_invite_codes: true,
    invite_code_email_restriction: false,
    invite_code_single_use: false,
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
        ipsk_expiration_check_enabled: data.ipsk_expiration_check_enabled as boolean,
        ipsk_expiration_check_interval_hours: data.ipsk_expiration_check_interval_hours as number,
        ipsk_cleanup_action: data.ipsk_cleanup_action as string,
        ipsk_expiration_warning_days: data.ipsk_expiration_warning_days as string,
        ipsk_expiration_email_enabled: data.ipsk_expiration_email_enabled as boolean,
        auth_invite_codes: data.auth_invite_codes as boolean,
        invite_code_email_restriction: data.invite_code_email_restriction as boolean,
        invite_code_single_use: data.invite_code_single_use as boolean,
      })
    }
  }, [settings])

  const handleSave = () => {
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">IPSK & Invite Settings</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure IPSK expiration monitoring and invite code behavior
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

      {/* IPSK Expiration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Clock size={20} className="text-meraki-blue" />
            IPSK Expiration Monitoring
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.ipsk_expiration_check_enabled ?? true}
              onChange={(e) => setFormData({ ...formData, ipsk_expiration_check_enabled: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Enable Expiration Monitoring</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Automatically check for and handle expired IPSKs
          </p>
        </div>

        {formData.ipsk_expiration_check_enabled && (
          <>
            <div className="form-group">
              <label className="form-label">Check Interval (hours)</label>
              <input
                type="number"
                value={formData.ipsk_expiration_check_interval_hours ?? 1}
                onChange={(e) => setFormData({ ...formData, ipsk_expiration_check_interval_hours: parseInt(e.target.value, 10) })}
                className="input"
                min="1"
                max="168"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                How often to check for expired IPSKs (1-168 hours)
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Cleanup Action</label>
              <select
                value={formData.ipsk_cleanup_action || 'soft_delete'}
                onChange={(e) => setFormData({ ...formData, ipsk_cleanup_action: e.target.value })}
                className="input"
              >
                <option value="soft_delete">Soft Delete (mark as inactive)</option>
                <option value="hard_delete">Hard Delete (remove from database)</option>
                <option value="disable">Disable (keep but deactivate)</option>
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                What to do with expired IPSKs when found
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Warning Days (comma-separated)</label>
              <input
                type="text"
                value={formData.ipsk_expiration_warning_days || '7,3,1'}
                onChange={(e) => setFormData({ ...formData, ipsk_expiration_warning_days: e.target.value })}
                className="input"
                placeholder="7,3,1"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Send warnings this many days before expiration (e.g., "7,3,1" warns at 7, 3, and 1 day before)
              </p>
            </div>

            <div className="form-group">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.ipsk_expiration_email_enabled ?? false}
                  onChange={(e) => setFormData({ ...formData, ipsk_expiration_email_enabled: e.target.checked })}
                  className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
                />
                <span className="form-label mb-0">Email Expiration Warnings</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
                Send email notifications to users before their IPSK expires
              </p>
            </div>
          </>
        )}
      </div>

      {/* Invite Codes */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Ticket size={20} className="text-meraki-blue" />
            Invite Code Settings
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_invite_codes ?? true}
              onChange={(e) => setFormData({ ...formData, auth_invite_codes: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Enable Invite Codes</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Allow registration via invite codes generated by admins
          </p>
        </div>

        {formData.auth_invite_codes && (
          <>
            <div className="form-group">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.invite_code_email_restriction ?? false}
                  onChange={(e) => setFormData({ ...formData, invite_code_email_restriction: e.target.checked })}
                  className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
                />
                <span className="form-label mb-0">Restrict Email to Invite</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
                Require user to register with the email address specified when the invite was created
              </p>
            </div>

            <div className="form-group">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.invite_code_single_use ?? false}
                  onChange={(e) => setFormData({ ...formData, invite_code_single_use: e.target.checked })}
                  className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
                />
                <span className="form-label mb-0">Single Use Codes</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
                Invite codes can only be used once and become invalid after first use
              </p>
            </div>
          </>
        )}
      </div>

      {/* Info Box */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">About IPSK Expiration & Invites</h4>
        <div className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
          <p>
            <strong>Expiration Monitoring:</strong> Automatically tracks IPSK lifetimes and can clean up or warn users before expiration.
          </p>
          <p>
            <strong>Cleanup Actions:</strong>
          </p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li><strong>Soft Delete:</strong> Marks as deleted but keeps in database (recommended)</li>
            <li><strong>Hard Delete:</strong> Permanently removes from database</li>
            <li><strong>Disable:</strong> Keeps but marks as inactive</li>
          </ul>
          <p>
            <strong>Invite Codes:</strong> Generate one-time or reusable codes for controlled user registration. Admins create these from the Invite Codes page.
          </p>
        </div>
      </div>
    </div>
  )
}
