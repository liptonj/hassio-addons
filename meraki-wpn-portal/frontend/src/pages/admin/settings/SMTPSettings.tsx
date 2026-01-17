import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Mail } from 'lucide-react'
import SMTPConfig from '../../../components/SMTPConfig'
import { sendTestEmail } from '../../../api/client'
import type { AllSettings } from '../../../types/settings'

interface SMTPSettingsProps {
  settings: AllSettings
  onChange: (updates: Partial<AllSettings>) => void
  onSave: () => Promise<void>
  isSaving: boolean
}

export default function SMTPSettings({ settings, onChange, onSave, isSaving }: SMTPSettingsProps) {
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  // Test email mutation
  const testMutation = useMutation({
    mutationFn: (recipient: string) => sendTestEmail(recipient),
    onSuccess: (data) => {
      setTestResult(data)
    },
    onError: (error: Error) => {
      setTestResult({
        success: false,
        message: error.message || 'Failed to send test email'
      })
    }
  })

  const handleTest = async (recipient: string) => {
    setTestResult(null)
    const result = await testMutation.mutateAsync(recipient)
    return result
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 bg-blue-100 rounded-lg">
          <Mail size={24} className="text-blue-600" />
        </div>
        <div>
          <h2 className="text-2xl font-bold">Email / SMTP Settings</h2>
          <p className="text-gray-600">Configure email notifications for iPSK expiration warnings</p>
        </div>
      </div>

      {/* SMTP Configuration */}
      <SMTPConfig
        settings={{
          smtp_enabled: settings.smtp_enabled,
          smtp_host: settings.smtp_host,
          smtp_port: settings.smtp_port,
          smtp_username: settings.smtp_username,
          smtp_password: settings.smtp_password,
          smtp_use_tls: settings.smtp_use_tls,
          smtp_use_ssl: settings.smtp_use_ssl,
          smtp_from_email: settings.smtp_from_email,
          smtp_from_name: settings.smtp_from_name,
          smtp_timeout: settings.smtp_timeout
        }}
        onChange={(updates) => onChange(updates)}
        onSave={onSave}
        onTest={handleTest}
        isSaving={isSaving}
      />

      {/* Additional Email Settings */}
      {settings.smtp_enabled && (
        <div className="mt-8 p-6 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Email Notification Settings</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium">iPSK Expiration Warnings</h4>
                <p className="text-sm text-gray-600">
                  Automatically send email notifications when iPSKs are about to expire
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={settings.ipsk_expiration_email_enabled}
                  onChange={(e) => onChange({ ipsk_expiration_email_enabled: e.target.checked })}
                />
                <div className="w-14 h-7 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>

            {settings.ipsk_expiration_email_enabled && (
              <div className="pl-4 border-l-4 border-blue-300">
                <div className="form-group">
                  <label className="form-label">Warning Days</label>
                  <input
                    type="text"
                    className="form-input max-w-xs"
                    placeholder="7,3,1"
                    value={settings.ipsk_expiration_warning_days}
                    onChange={(e) => onChange({ ipsk_expiration_warning_days: e.target.value })}
                  />
                  <p className="form-help">
                    Comma-separated list of days before expiration to send warnings (e.g., 7,3,1)
                  </p>
                </div>

                <div className="form-group">
                  <label className="form-label">Admin Notification Email</label>
                  <input
                    type="email"
                    className="form-input max-w-md"
                    placeholder="admin@example.com"
                    value={settings.admin_notification_email}
                    onChange={(e) => onChange({ admin_notification_email: e.target.value })}
                  />
                  <p className="form-help">
                    Email address for admin notifications (optional, in addition to user notifications)
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
