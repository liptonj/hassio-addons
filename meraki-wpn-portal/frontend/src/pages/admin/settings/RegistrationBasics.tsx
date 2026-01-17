import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Users, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface RegistrationBasicsSettings {
  // Registration Modes (can enable multiple)
  auth_open_registration?: boolean           // Open registration, immediate access
  auth_open_registration_approval?: boolean  // Open registration + admin approval
  auth_account_only?: boolean                // Existing accounts only, no new registrations
  auth_invite_code_account?: boolean         // Invite code required to create account
  auth_invite_code_only?: boolean            // Enter code → get PSK (no account needed)
  
  // Verification
  auth_email_verification?: boolean
  auth_sms_verification?: boolean
  
  // Unit Settings
  require_unit_number?: boolean
  unit_source?: string
  manual_units?: string
}

export default function RegistrationBasics() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<RegistrationBasicsSettings>({
    // Registration modes
    auth_open_registration: true,
    auth_open_registration_approval: false,
    auth_account_only: false,
    auth_invite_code_account: false,
    auth_invite_code_only: false,
    // Verification
    auth_email_verification: false,
    auth_sms_verification: false,
    // Units
    require_unit_number: true,
    unit_source: 'manual_list',
    manual_units: '',
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
        // Registration modes
        auth_open_registration: data.auth_open_registration as boolean ?? data.auth_self_registration as boolean ?? true,
        auth_open_registration_approval: data.auth_open_registration_approval as boolean ?? false,
        auth_account_only: data.auth_account_only as boolean ?? false,
        auth_invite_code_account: data.auth_invite_code_account as boolean ?? data.auth_invite_codes as boolean ?? false,
        auth_invite_code_only: data.auth_invite_code_only as boolean ?? false,
        // Verification
        auth_email_verification: data.auth_email_verification as boolean,
        auth_sms_verification: data.auth_sms_verification as boolean,
        // Units
        require_unit_number: data.require_unit_number as boolean,
        unit_source: data.unit_source as string,
        manual_units: data.manual_units as string,
      })
    }
  }, [settings])

  const handleSave = () => {
    // Validate manual units JSON if unit_source is manual_list
    if (formData.unit_source === 'manual_list' && formData.manual_units?.trim()) {
      try {
        const units = JSON.parse(formData.manual_units)
        if (!Array.isArray(units) || units.some((unit) => typeof unit !== 'string')) {
          throw new Error('Invalid unit list')
        }
      } catch (error) {
        setNotification({
          type: 'error',
          message: 'Manual units must be a JSON array of strings',
        })
        return
      }
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Registration Basics</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure basic registration and signup options
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

      {/* Registration Options */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Users size={20} className="text-meraki-blue" />
            Registration Options
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_open_registration ?? true}
              onChange={(e) => setFormData({ ...formData, auth_open_registration: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Open Registration</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Anyone can sign up and get immediate access
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_open_registration_approval ?? false}
              onChange={(e) => setFormData({ ...formData, auth_open_registration_approval: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Open Registration + Admin Approval</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Anyone can sign up, but admin must approve before access is granted
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_account_only ?? false}
              onChange={(e) => setFormData({ ...formData, auth_account_only: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Account Only</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            No new registrations - only existing accounts can login
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_invite_code_account ?? false}
              onChange={(e) => setFormData({ ...formData, auth_invite_code_account: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Invite Code + Account</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Invite code required to create an account
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_invite_code_only ?? false}
              onChange={(e) => setFormData({ ...formData, auth_invite_code_only: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Invite Code Only</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Enter invite code to get PSK credentials (no account needed)
          </p>
        </div>
      </div>

      {/* Verification */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Verification Options</h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_email_verification ?? false}
              onChange={(e) => setFormData({ ...formData, auth_email_verification: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Require Email Verification</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Users must verify their email address before accessing WiFi
          </p>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.auth_sms_verification ?? false}
              onChange={(e) => setFormData({ ...formData, auth_sms_verification: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Require SMS Verification</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Users must verify their phone number via SMS
          </p>
        </div>
      </div>

      {/* Unit Number Configuration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Unit Number Configuration</h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.require_unit_number ?? true}
              onChange={(e) => setFormData({ ...formData, require_unit_number: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Require Unit Number</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Require users to provide a unit/apartment number during registration
          </p>
        </div>

        {formData.require_unit_number && (
          <>
            <div className="form-group">
              <label className="form-label">Unit Source</label>
              <select
                value={formData.unit_source || 'manual_list'}
                onChange={(e) => setFormData({ ...formData, unit_source: e.target.value })}
                className="input"
              >
                <option value="manual_list">Manual List (JSON)</option>
                <option value="free_text">Free Text Entry</option>
                <option value="ha_areas">Home Assistant Areas</option>
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Choose how unit numbers are provided or validated
              </p>
            </div>

            {formData.unit_source === 'manual_list' && (
              <div className="form-group">
                <label className="form-label">Unit List (JSON array)</label>
                <textarea
                  value={formData.manual_units || ''}
                  onChange={(e) => setFormData({ ...formData, manual_units: e.target.value })}
                  className="input font-mono text-sm min-h-[120px]"
                  placeholder='["101", "102", "103", "201", "202", "203"]'
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Provide a JSON array of valid unit numbers
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
