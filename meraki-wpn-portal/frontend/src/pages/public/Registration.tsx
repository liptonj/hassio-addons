import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Wifi, User, Mail, Building2, Ticket, Smartphone } from 'lucide-react'
import { register, getPortalOptions, getPublicAreas } from '../../api/client'
import type { RegistrationRequest } from '../../types/user'
import AcceptableUseAgreement from '../../components/AcceptableUseAgreement'
import PSKCustomizer from '../../components/PSKCustomizer'
import CustomFieldRenderer from '../../components/CustomFieldRenderer'
import AuthMethodSelector from '../../components/AuthMethodSelector'
import { getUserAgent } from '../../utils/deviceDetection'
import { validatePSK } from '../../utils/pskValidation'

export default function Registration() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Capture splash page parameters from Meraki
  // login_url = Sign-on splash, grant_url = Click-through splash
  const clientMac = searchParams.get('mac')
  const loginUrl = searchParams.get('login_url')
  const grantUrl = searchParams.get('grant_url')
  const continueUrl = searchParams.get('continue_url')
  const inviteCodeFromQuery = searchParams.get('code') || searchParams.get('invite_code') || ''
  const emailFromQuery = searchParams.get('email') || ''
  const prefillEmail = searchParams.get('prefill_email') || ''
  const prefillName = searchParams.get('prefill_name') || ''
  const prefillUnit = searchParams.get('prefill_unit') || ''
  const resolvedEmail = emailFromQuery || prefillEmail

  const [formData, setFormData] = useState<RegistrationRequest>({
    name: prefillName,
    email: resolvedEmail,
    unit: prefillUnit,
    area_id: '',
    invite_code: inviteCodeFromQuery.toUpperCase(),
    mac_address: clientMac || undefined,
    custom_passphrase: '',
    accept_aup: false,
    custom_fields: {},
    user_agent: getUserAgent(),
    auth_method: 'ipsk', // Default to IPSK
    certificate_password: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [customFieldErrors, setCustomFieldErrors] = useState<Record<string, string>>({})

  // Log splash params for debugging
  useEffect(() => {
    if (clientMac || loginUrl || grantUrl) {
      console.log('Splash page parameters:', { clientMac, loginUrl, grantUrl, continueUrl })
    }
  }, [clientMac, loginUrl, grantUrl, continueUrl])

  const { data: options } = useQuery({
    queryKey: ['portal-options'],
    queryFn: getPortalOptions,
  })

  const { data: areas } = useQuery({
    queryKey: ['public-areas'],
    queryFn: getPublicAreas,
    enabled: options?.unit_source === 'ha_areas',
  })

  useEffect(() => {
    if (!options) {
      return
    }
    const ipskEnabled = options.auth_ipsk_enabled !== false
    const eapEnabled = options.auth_eap_enabled === true
    const allowedMethods: Array<'ipsk' | 'eap-tls'> = []
    if (ipskEnabled) {
      allowedMethods.push('ipsk')
    }
    if (eapEnabled) {
      allowedMethods.push('eap-tls')
    }
    if (allowedMethods.length === 0) {
      return
    }
    const currentMethod = formData.auth_method || 'ipsk'
    const isBothAllowed = ipskEnabled && eapEnabled
    const isCurrentAllowed =
      allowedMethods.includes(currentMethod as 'ipsk' | 'eap-tls') ||
      (currentMethod === 'both' && isBothAllowed)
    if (!isCurrentAllowed) {
      setFormData((prev) => ({
        ...prev,
        auth_method: allowedMethods[0],
      }))
    }
  }, [options, formData.auth_method])

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (data) => {
      // Pass splash parameters to success page for network grant
      navigate('/success', { 
        state: {
          ...data,
          client_mac: clientMac,
          login_url: loginUrl ? decodeURIComponent(loginUrl) : null,
          grant_url: grantUrl ? decodeURIComponent(grantUrl) : null,
          continue_url: continueUrl ? decodeURIComponent(continueUrl) : null,
        }
      })
    },
    onError: (error: Error) => {
      setErrors({ form: error.message })
    },
  })

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    } else if (formData.name.trim().length < 2) {
      newErrors.name = 'Name must be at least 2 characters'
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address'
    }

    if (options?.require_unit_number) {
      if (options.unit_source === 'ha_areas' && !formData.area_id) {
        newErrors.unit = 'Please select your unit'
      } else if (options.unit_source === 'manual_list' && !formData.unit) {
        newErrors.unit = 'Please select your unit'
      } else if (options.unit_source === 'free_text' && !formData.unit) {
        newErrors.unit = 'Please enter your unit number'
      }
    }

    if (options?.auth_methods.invite_codes && !options.auth_methods.self_registration) {
      if (!formData.invite_code?.trim()) {
        newErrors.invite_code = 'Invite code is required'
      }
    }

    // Validate AUP if enabled
    if (options?.aup_enabled && !formData.accept_aup) {
      newErrors.aup = 'You must accept the Acceptable Use Policy to continue'
    }

    // Validate custom PSK if provided
    if (options?.allow_custom_psk && formData.custom_passphrase) {
      const pskValidation = validatePSK(
        formData.custom_passphrase,
        options.psk_requirements.min_length,
        options.psk_requirements.max_length
      )
      if (!pskValidation.valid) {
        newErrors.custom_passphrase = pskValidation.errors[0]
      }
    }

    // Validate certificate password if EAP-TLS is selected
    if (formData.auth_method === 'eap-tls' || formData.auth_method === 'both') {
      if (!formData.certificate_password || formData.certificate_password.length < 8) {
        newErrors.certificate_password = 'Certificate password must be at least 8 characters'
      }
    }

    // Validate custom fields
    const fieldErrors: Record<string, string> = {}
    if (options?.custom_fields && options.custom_fields.length > 0) {
      options.custom_fields.forEach((field) => {
        if (field.required && !formData.custom_fields?.[field.id]?.trim()) {
          fieldErrors[field.id] = `${field.label} is required`
        }
      })
    }

    setErrors(newErrors)
    setCustomFieldErrors(fieldErrors)
    return Object.keys(newErrors).length === 0 && Object.keys(fieldErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (validate()) {
      mutation.mutate(formData)
    }
  }

  const handleChange = (field: keyof RegistrationRequest, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }))
    }
  }

  return (
    <div className="animate-slide-up max-w-[480px] mx-auto">
      {/* Property Logo/Title */}
      <div className="text-center mb-8">
        {options?.logo_url && (
          <img
            src={options.logo_url}
            alt={options.property_name}
            className="max-w-[200px] h-auto mx-auto mb-4"
          />
        )}
        <h1 className="text-2xl mb-2">
          {options?.property_name || 'Welcome'}
        </h1>
        <p className="text-muted">
          Register below to get your personal WiFi credentials
        </p>
      </div>

      {/* Registration Form */}
      <form onSubmit={handleSubmit} className="card">
        {/* Show device info if coming from splash page */}
        {clientMac && (
          <div className="mb-4 p-4 flex items-center gap-3 bg-meraki-blue/10 rounded-lg border border-meraki-blue/30">
            <Smartphone size={20} className="text-meraki-blue" />
            <div>
              <div className="text-sm font-medium">Registering This Device</div>
              <div className="text-xs opacity-70">MAC: {clientMac}</div>
            </div>
          </div>
        )}

        {errors.form && (
          <div className="mb-4 p-4 bg-error-light rounded-lg text-error">
            {errors.form}
          </div>
        )}

        {/* Name Field */}
        <div className="form-group">
          <label className="form-label">
            <span className="form-label-icon">
              <User size={16} /> Full Name
            </span>
          </label>
          <input
            type="text"
            className={`form-input ${errors.name ? 'error' : ''}`}
            placeholder="John Smith"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            disabled={mutation.isPending}
          />
          {errors.name && <p className="form-error">{errors.name}</p>}
        </div>

        {/* Email Field */}
        <div className="form-group">
          <label className="form-label">
            <span className="form-label-icon">
              <Mail size={16} /> Email Address
            </span>
          </label>
          <input
            type="email"
            className={`form-input ${errors.email ? 'error' : ''}`}
            placeholder="john@example.com"
            value={formData.email}
            onChange={(e) => handleChange('email', e.target.value)}
            disabled={mutation.isPending}
          />
          {errors.email && <p className="form-error">{errors.email}</p>}
        </div>

        {/* Unit Selection */}
        {options?.unit_source === 'ha_areas' && (
          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Building2 size={16} /> Unit / Room
              </span>
            </label>
            <select
              className={`form-select ${errors.unit ? 'error' : ''}`}
              value={formData.area_id}
              onChange={(e) => handleChange('area_id', e.target.value)}
              disabled={mutation.isPending}
            >
              <option value="">Select your unit...</option>
              {areas?.map((area) => (
                <option key={area.area_id} value={area.area_id}>
                  {area.name}
                </option>
              ))}
            </select>
            {errors.unit && <p className="form-error">{errors.unit}</p>}
          </div>
        )}

        {options?.unit_source === 'manual_list' && (
          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Building2 size={16} /> Unit / Room
              </span>
            </label>
            <select
              className={`form-select ${errors.unit ? 'error' : ''}`}
              value={formData.unit}
              onChange={(e) => handleChange('unit', e.target.value)}
              disabled={mutation.isPending}
            >
              <option value="">Select your unit...</option>
              {options.units?.map((unit) => (
                <option key={unit.area_id} value={unit.area_id}>
                  {unit.name}
                </option>
              ))}
            </select>
            {errors.unit && <p className="form-error">{errors.unit}</p>}
          </div>
        )}

        {options?.unit_source === 'free_text' && (
          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Building2 size={16} /> Unit / Room
              </span>
            </label>
            <input
              type="text"
              className={`form-input ${errors.unit ? 'error' : ''}`}
              placeholder="e.g., 201"
              value={formData.unit}
              onChange={(e) => handleChange('unit', e.target.value)}
              disabled={mutation.isPending}
            />
            {errors.unit && <p className="form-error">{errors.unit}</p>}
          </div>
        )}

        {/* Invite Code */}
        {options?.auth_methods.invite_codes && (
          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Ticket size={16} /> Invitation Code
                {options.auth_methods.self_registration && (
                  <span className="text-muted font-normal">
                    {' '}(if provided)
                  </span>
                )}
              </span>
            </label>
            <input
              type="text"
              className={`form-input uppercase ${errors.invite_code ? 'error' : ''}`}
              placeholder="WELCOME2026"
              value={formData.invite_code}
              onChange={(e) => handleChange('invite_code', e.target.value.toUpperCase())}
              disabled={mutation.isPending}
            />
            {errors.invite_code && <p className="form-error">{errors.invite_code}</p>}
          </div>
        )}

        {/* Authentication Method Selector */}
        {options && (
          <AuthMethodSelector
            ipskEnabled={options.auth_ipsk_enabled !== false}
            eapEnabled={options.auth_eap_enabled === true}
            selectedMethod={formData.auth_method as 'ipsk' | 'eap-tls' | 'both'}
            onMethodChange={(method) => {
              setFormData({ ...formData, auth_method: method })
              if (errors.auth_method) {
                setErrors({ ...errors, auth_method: '' })
              }
            }}
            certificatePassword={formData.certificate_password || ''}
            onCertificatePasswordChange={(password) => {
              setFormData({ ...formData, certificate_password: password })
              if (errors.certificate_password) {
                setErrors({ ...errors, certificate_password: '' })
              }
            }}
            errors={{
              auth_method: errors.auth_method,
              certificate_password: errors.certificate_password,
            }}
          />
        )}

        {/* Custom Fields */}
        {options?.custom_fields && options.custom_fields.length > 0 && (
          <CustomFieldRenderer
            fields={options.custom_fields}
            values={formData.custom_fields || {}}
            onChange={(fieldId, value) => {
              setFormData({
                ...formData,
                custom_fields: { ...formData.custom_fields, [fieldId]: value }
              })
              if (customFieldErrors[fieldId]) {
                setCustomFieldErrors({ ...customFieldErrors, [fieldId]: '' })
              }
            }}
            errors={customFieldErrors}
          />
        )}

        {/* PSK Customizer */}
        {options?.allow_custom_psk && (
          <PSKCustomizer
            enabled={true}
            minLength={options.psk_requirements.min_length}
            maxLength={options.psk_requirements.max_length}
            value={formData.custom_passphrase || ''}
            onChange={(value) => {
              setFormData({ ...formData, custom_passphrase: value })
              if (errors.custom_passphrase) {
                setErrors({ ...errors, custom_passphrase: '' })
              }
            }}
            error={errors.custom_passphrase}
          />
        )}

        {/* Acceptable Use Agreement */}
        {options?.aup_enabled && (
          <AcceptableUseAgreement
            enabled={true}
            text={options.aup_text}
            url={options.aup_url}
            accepted={formData.accept_aup || false}
            onAcceptChange={(accepted) => {
              setFormData({ ...formData, accept_aup: accepted })
              if (errors.aup) {
                setErrors({ ...errors, aup: '' })
              }
            }}
            error={errors.aup}
          />
        )}

        {/* Submit Button */}
        <button
          type="submit"
          className="btn btn-primary btn-lg btn-full mt-4"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <>
              <span className="loading-spinner" /> Processing...
            </>
          ) : (
            <>
              <Wifi size={20} /> Get My WiFi Access
            </>
          )}
        </button>
      </form>

      {/* Already Registered Link */}
      <p className="text-center mt-6 text-muted">
        Already have access?{' '}
        <a href="/my-network">View My Network</a>
      </p>
    </div>
  )
}
