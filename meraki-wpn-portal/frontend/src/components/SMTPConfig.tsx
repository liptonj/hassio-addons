import { useState } from 'react'
import { Mail, Server, Key, Send, Check, AlertCircle, Info } from 'lucide-react'

interface SMTPSettings {
  smtp_enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password: string
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
  smtp_from_email: string
  smtp_from_name: string
  smtp_timeout: number
}

interface SMTPConfigProps {
  settings: SMTPSettings
  onChange: (settings: Partial<SMTPSettings>) => void
  onSave: () => Promise<void>
  onTest: (recipient: string) => Promise<{ success: boolean; message: string }>
  isSaving: boolean
}

// SMTP Provider Presets
const SMTP_PRESETS = {
  office365: {
    name: 'Microsoft 365 / Office 365',
    smtp_host: 'smtp.office365.com',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Use your full email address as username. For MFA accounts, create an app password.',
    docs_url: 'https://support.microsoft.com/en-us/office/pop-imap-and-smtp-settings-8361e398-8af4-4e97-b147-6c6c4ac95353'
  },
  gmail: {
    name: 'Gmail',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Enable 2-Step Verification, then generate an App Password. Use your Gmail address and the app password.',
    docs_url: 'https://support.google.com/mail/answer/185833'
  },
  amazonses: {
    name: 'Amazon SES',
    smtp_host: 'email-smtp.us-east-1.amazonaws.com',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Use your SMTP username and password from AWS SES console. Change region in hostname if needed.',
    docs_url: 'https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html'
  },
  sendgrid: {
    name: 'SendGrid',
    smtp_host: 'smtp.sendgrid.net',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Use "apikey" as username and your SendGrid API key as password.',
    docs_url: 'https://docs.sendgrid.com/for-developers/sending-email/integrating-with-the-smtp-api'
  },
  mailgun: {
    name: 'Mailgun',
    smtp_host: 'smtp.mailgun.org',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Find SMTP credentials in your Mailgun domain settings.',
    docs_url: 'https://documentation.mailgun.com/en/latest/user_manual.html#sending-via-smtp'
  },
  custom: {
    name: 'Custom SMTP Server',
    smtp_host: '',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_use_ssl: false,
    instructions: 'Enter your custom SMTP server details.',
    docs_url: ''
  }
}

export default function SMTPConfig({ settings, onChange, onSave, onTest, isSaving }: SMTPConfigProps) {
  const [selectedPreset, setSelectedPreset] = useState<string>('custom')
  const [testEmail, setTestEmail] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [isTesting, setIsTesting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handlePresetChange = (presetKey: string) => {
    setSelectedPreset(presetKey)
    const preset = SMTP_PRESETS[presetKey as keyof typeof SMTP_PRESETS]
    if (preset) {
      onChange({
        smtp_host: preset.smtp_host,
        smtp_port: preset.smtp_port,
        smtp_use_tls: preset.smtp_use_tls,
        smtp_use_ssl: preset.smtp_use_ssl,
      })
    }
  }

  const handleTestEmail = async () => {
    if (!testEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(testEmail)) {
      setTestResult({ success: false, message: 'Please enter a valid email address' })
      return
    }

    setIsTesting(true)
    setTestResult(null)

    try {
      const result = await onTest(testEmail)
      setTestResult(result)
    } catch (error) {
      setTestResult({
        success: false,
        message: error instanceof Error ? error.message : 'Failed to send test email'
      })
    } finally {
      setIsTesting(false)
    }
  }

  const currentPreset = SMTP_PRESETS[selectedPreset as keyof typeof SMTP_PRESETS]

  return (
    <div className="space-y-6">
      {/* Enable/Disable Toggle */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center gap-3">
          <Mail size={24} className="text-meraki-blue" />
          <div>
            <h3 className="font-semibold text-lg">Email Notifications</h3>
            <p className="text-sm text-gray-600">
              Send automated emails for iPSK expiration warnings and notifications
            </p>
          </div>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={settings.smtp_enabled}
            onChange={(e) => onChange({ smtp_enabled: e.target.checked })}
          />
          <div className="w-14 h-7 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-meraki-blue"></div>
        </label>
      </div>

      {settings.smtp_enabled && (
        <>
          {/* Provider Preset Selector */}
          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Server size={16} /> Email Provider
              </span>
            </label>
            <select
              className="form-input"
              value={selectedPreset}
              onChange={(e) => handlePresetChange(e.target.value)}
            >
              <option value="office365">🏢 {SMTP_PRESETS.office365.name}</option>
              <option value="gmail">📧 {SMTP_PRESETS.gmail.name}</option>
              <option value="amazonses">☁️ {SMTP_PRESETS.amazonses.name}</option>
              <option value="sendgrid">📨 {SMTP_PRESETS.sendgrid.name}</option>
              <option value="mailgun">✉️ {SMTP_PRESETS.mailgun.name}</option>
              <option value="custom">⚙️ {SMTP_PRESETS.custom.name}</option>
            </select>

            {/* Provider Instructions */}
            {currentPreset && currentPreset.instructions && (
              <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex gap-3">
                  <Info size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm text-blue-900 mb-2">{currentPreset.instructions}</p>
                    {currentPreset.docs_url && (
                      <a
                        href={currentPreset.docs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-600 hover:underline inline-flex items-center gap-1"
                      >
                        View setup guide →
                      </a>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* SMTP Host & Port */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="form-group md:col-span-2">
              <label className="form-label">
                <span className="form-label-icon">
                  <Server size={16} /> SMTP Host
                </span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="smtp.example.com"
                value={settings.smtp_host}
                onChange={(e) => onChange({ smtp_host: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                <span className="form-label-icon">
                  <Server size={16} /> Port
                </span>
              </label>
              <input
                type="number"
                className="form-input"
                placeholder="587"
                value={settings.smtp_port}
                onChange={(e) => onChange({ smtp_port: parseInt(e.target.value) || 587 })}
              />
            </div>
          </div>

          {/* Encryption Options */}
          <div className="form-group">
            <label className="form-label mb-3">Encryption</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="encryption"
                  checked={settings.smtp_use_tls && !settings.smtp_use_ssl}
                  onChange={() => onChange({ smtp_use_tls: true, smtp_use_ssl: false })}
                  className="w-4 h-4 text-meraki-blue"
                />
                <span className="text-sm">TLS (Port 587) - Recommended</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="encryption"
                  checked={settings.smtp_use_ssl}
                  onChange={() => onChange({ smtp_use_tls: false, smtp_use_ssl: true })}
                  className="w-4 h-4 text-meraki-blue"
                />
                <span className="text-sm">SSL (Port 465)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="encryption"
                  checked={!settings.smtp_use_tls && !settings.smtp_use_ssl}
                  onChange={() => onChange({ smtp_use_tls: false, smtp_use_ssl: false })}
                  className="w-4 h-4 text-meraki-blue"
                />
                <span className="text-sm">None (Port 25) - Not recommended</span>
              </label>
            </div>
          </div>

          {/* Authentication */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">
                <span className="form-label-icon">
                  <Mail size={16} /> Username / Email
                </span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="your-email@example.com"
                value={settings.smtp_username}
                onChange={(e) => onChange({ smtp_username: e.target.value })}
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                <span className="form-label-icon">
                  <Key size={16} /> Password / App Password
                </span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="form-input pr-10"
                  placeholder="••••••••••••"
                  value={settings.smtp_password}
                  onChange={(e) => onChange({ smtp_password: e.target.value })}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showPassword ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
            </div>
          </div>

          {/* From Email & Name */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">
                <span className="form-label-icon">
                  <Mail size={16} /> From Email Address
                </span>
              </label>
              <input
                type="email"
                className="form-input"
                placeholder="noreply@example.com"
                value={settings.smtp_from_email}
                onChange={(e) => onChange({ smtp_from_email: e.target.value })}
              />
              <p className="form-help">Email address that notifications will be sent from</p>
            </div>
            <div className="form-group">
              <label className="form-label">
                <span className="form-label-icon">
                  <Mail size={16} /> From Name
                </span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="WiFi Portal"
                value={settings.smtp_from_name}
                onChange={(e) => onChange({ smtp_from_name: e.target.value })}
              />
              <p className="form-help">Display name for sent emails</p>
            </div>
          </div>

          {/* Test Email Section */}
          <div className="p-6 bg-gray-50 rounded-lg border border-gray-200 space-y-4">
            <div className="flex items-center gap-2 mb-3">
              <Send size={20} className="text-meraki-blue" />
              <h4 className="font-semibold">Test Email Configuration</h4>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Send a test email to verify your SMTP settings are working correctly.
            </p>
            <div className="flex gap-3">
              <input
                type="email"
                className="form-input flex-1"
                placeholder="recipient@example.com"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
              <button
                type="button"
                onClick={handleTestEmail}
                disabled={isTesting || !testEmail}
                className="btn btn-secondary whitespace-nowrap"
              >
                {isTesting ? (
                  <>
                    <span className="loading-spinner" /> Sending...
                  </>
                ) : (
                  <>
                    <Send size={18} /> Send Test
                  </>
                )}
              </button>
            </div>

            {/* Test Result */}
            {testResult && (
              <div className={`p-4 rounded-lg border ${
                testResult.success
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-start gap-3">
                  {testResult.success ? (
                    <Check size={20} className="text-green-600 flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle size={20} className="text-red-600 flex-shrink-0 mt-0.5" />
                  )}
                  <p className={`text-sm ${
                    testResult.success ? 'text-green-800' : 'text-red-800'
                  }`}>
                    {testResult.message}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4 border-t">
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving}
              className="btn btn-primary"
            >
              {isSaving ? (
                <>
                  <span className="loading-spinner" /> Saving...
                </>
              ) : (
                <>
                  <Check size={18} /> Save SMTP Settings
                </>
              )}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
