import { useState } from 'react'
import { Eye, EyeOff, RefreshCw, Lock } from 'lucide-react'
import { validatePSK, getPSKStrength, getStrengthColor, getStrengthText, getStrengthPercentage, generateRandomPSK } from '../utils/pskValidation'

interface PSKCustomizerProps {
  enabled: boolean
  minLength: number
  maxLength: number
  value: string
  onChange: (value: string) => void
  error?: string
}

export default function PSKCustomizer({
  enabled,
  minLength,
  maxLength,
  value,
  onChange,
  error,
}: PSKCustomizerProps) {
  const [useCustom, setUseCustom] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  if (!enabled) {
    return null
  }

  const validation = validatePSK(value, minLength, maxLength)
  const strength = value ? getPSKStrength(value) : 'weak'
  const strengthColor = getStrengthColor(strength)
  const strengthText = getStrengthText(strength)
  const strengthPercentage = getStrengthPercentage(strength)

  const handleToggleCustom = (custom: boolean) => {
    setUseCustom(custom)
    if (!custom) {
      // Clear custom value when switching to auto-generate
      onChange('')
    }
  }

  const handleGenerate = () => {
    const newPSK = generateRandomPSK(16)
    onChange(newPSK)
  }

  return (
    <div className="form-group">
      <label className="form-label">
        <span className="form-label-icon">
          <Lock size={16} /> WiFi Password
        </span>
      </label>

      {/* Toggle between auto and custom */}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => handleToggleCustom(false)}
          className={`flex-1 py-2 px-4 rounded-lg border-2 transition-all ${
            !useCustom
              ? 'border-meraki-blue bg-meraki-blue/10 text-meraki-blue font-semibold'
              : 'border-gray-300 text-gray-600 hover:border-gray-400'
          }`}
        >
          Auto-generate
        </button>
        <button
          type="button"
          onClick={() => handleToggleCustom(true)}
          className={`flex-1 py-2 px-4 rounded-lg border-2 transition-all ${
            useCustom
              ? 'border-meraki-blue bg-meraki-blue/10 text-meraki-blue font-semibold'
              : 'border-gray-300 text-gray-600 hover:border-gray-400'
          }`}
        >
          Choose my own
        </button>
      </div>

      {/* Custom PSK input */}
      {useCustom && (
        <>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              className={`form-input pr-24 ${error || !validation.valid ? 'error' : ''}`}
              placeholder="Enter your password"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              minLength={minLength}
              maxLength={maxLength}
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
              {/* Generate button */}
              <button
                type="button"
                onClick={handleGenerate}
                className="p-2 text-gray-500 hover:text-meraki-blue transition-colors"
                title="Generate random password"
              >
                <RefreshCw size={18} />
              </button>
              {/* Show/Hide button */}
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Password strength indicator */}
          {value && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium" style={{ color: strengthColor }}>
                  {strengthText}
                </span>
                <span className="text-xs text-gray-500">
                  {value.length}/{maxLength} characters
                </span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full transition-all duration-300 rounded-full"
                  style={{
                    width: `${strengthPercentage}%`,
                    backgroundColor: strengthColor,
                  }}
                />
              </div>
            </div>
          )}

          {/* Requirements */}
          <div className="mt-3 text-xs text-gray-600 space-y-1">
            <p>Password requirements:</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li className={value.length >= minLength ? 'text-success' : ''}>
                At least {minLength} characters
              </li>
              <li className={value.length <= maxLength ? 'text-success' : ''}>
                No more than {maxLength} characters
              </li>
              <li className={!/[^\x20-\x7E]/.test(value) || !value ? 'text-success' : 'text-error'}>
                Only printable ASCII characters
              </li>
            </ul>
          </div>

          {/* Validation errors */}
          {!validation.valid && value && (
            <div className="mt-2">
              {validation.errors.map((err, idx) => (
                <p key={idx} className="form-error">{err}</p>
              ))}
            </div>
          )}

          {error && <p className="form-error">{error}</p>}
        </>
      )}

      {/* Auto-generate info */}
      {!useCustom && (
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm text-blue-800">
            A secure random password will be automatically generated for you.
          </p>
        </div>
      )}
    </div>
  )
}
