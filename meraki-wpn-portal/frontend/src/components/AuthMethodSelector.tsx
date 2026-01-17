import { Shield, Key, Lock, Info } from 'lucide-react'

interface AuthMethodSelectorProps {
  ipskEnabled: boolean
  eapEnabled: boolean
  selectedMethod: 'ipsk' | 'eap-tls' | 'both'
  onMethodChange: (method: 'ipsk' | 'eap-tls' | 'both') => void
  certificatePassword: string
  onCertificatePasswordChange: (password: string) => void
  errors?: {
    auth_method?: string
    certificate_password?: string
  }
}

export default function AuthMethodSelector({
  ipskEnabled,
  eapEnabled,
  selectedMethod,
  onMethodChange,
  certificatePassword,
  onCertificatePasswordChange,
  errors = {},
}: AuthMethodSelectorProps) {
  // Track available methods to decide rendering behavior
  const availableMethods = []
  if (ipskEnabled) availableMethods.push('ipsk')
  if (eapEnabled) availableMethods.push('eap-tls')

  // If only IPSK is available, skip rendering the selector entirely
  if (availableMethods.length === 1 && availableMethods[0] === 'ipsk') {
    return null
  }

  const needsCertPassword = selectedMethod === 'eap-tls' || selectedMethod === 'both'

  return (
    <div className="space-y-4">
      {/* Authentication Method Selection */}
      <div>
        <label className="form-label mb-3">
          <span className="form-label-icon">
            <Shield size={16} /> WiFi Authentication Method
          </span>
        </label>

        <div className="space-y-2">
          {/* IPSK Option */}
          {ipskEnabled && (
            <label className="flex items-start gap-3 p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg cursor-pointer transition-all hover:border-blue-300 dark:hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-blue-900/20 dark:bg-gray-800">
              <input
                type="radio"
                name="auth_method"
                value="ipsk"
                checked={selectedMethod === 'ipsk'}
                onChange={() => onMethodChange('ipsk')}
                className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-gray-900 dark:text-gray-100">
                  <Key size={18} className="text-blue-600" />
                  Pre-Shared Key (IPSK)
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Simple password-based WiFi. Works with all devices. Easy setup with QR code.
                </p>
              </div>
            </label>
          )}

          {/* EAP-TLS Option */}
          {eapEnabled && (
            <label className="flex items-start gap-3 p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg cursor-pointer transition-all hover:border-blue-300 dark:hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-blue-900/20 dark:bg-gray-800">
              <input
                type="radio"
                name="auth_method"
                value="eap-tls"
                checked={selectedMethod === 'eap-tls'}
                onChange={() => onMethodChange('eap-tls')}
                className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-gray-900 dark:text-gray-100">
                  <Lock size={18} className="text-green-600" />
                  Certificate (EAP-TLS)
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Enterprise-grade security using certificates. More secure, requires certificate installation.
                </p>
              </div>
            </label>
          )}

          {/* Both Option */}
          {ipskEnabled && eapEnabled && (
            <label className="flex items-start gap-3 p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg cursor-pointer transition-all hover:border-blue-300 dark:hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-blue-900/20 dark:bg-gray-800">
              <input
                type="radio"
                name="auth_method"
                value="both"
                checked={selectedMethod === 'both'}
                onChange={() => onMethodChange('both')}
                className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-gray-900 dark:text-gray-100">
                  <Shield size={18} className="text-purple-600" />
                  Both Methods (Recommended)
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Get both password and certificate. Use password for quick access, certificate for maximum security.
                </p>
              </div>
            </label>
          )}
        </div>

        {errors.auth_method && (
          <p className="text-sm text-red-600 mt-2">{errors.auth_method}</p>
        )}
      </div>

      {/* Certificate Password Field (shown if EAP-TLS selected) */}
      {needsCertPassword && (
        <div className="animate-slide-up">
          <label className="form-label">
            <span className="form-label-icon">
              <Lock size={16} /> Certificate Password
            </span>
          </label>
          <input
            type="password"
            value={certificatePassword}
            onChange={(e) => onCertificatePasswordChange(e.target.value)}
            placeholder="Choose a password for your certificate"
            className={`form-input ${errors.certificate_password ? 'error' : ''}`}
            minLength={8}
            required
          />
          {errors.certificate_password ? (
            <p className="text-sm text-red-600 mt-1">{errors.certificate_password}</p>
          ) : (
            <div className="flex items-start gap-2 mt-2 text-sm text-gray-600">
              <Info size={16} className="mt-0.5 flex-shrink-0" />
              <p>
                This password will protect your certificate file. You'll need it when installing the certificate on your device.
                Minimum 8 characters.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-900 dark:text-blue-200">
            {selectedMethod === 'ipsk' && (
              <p>
                <strong>IPSK:</strong> You'll receive a WiFi password and QR code. Simply scan the QR code or manually enter the password on your device.
              </p>
            )}
            {selectedMethod === 'eap-tls' && (
              <p>
                <strong>EAP-TLS:</strong> You'll receive a certificate file to download. Install it on your device and select it when connecting to WiFi.
              </p>
            )}
            {selectedMethod === 'both' && (
              <p>
                <strong>Both Methods:</strong> You'll receive both a password (for quick setup) and a certificate (for maximum security). Choose whichever method works best for your device.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
