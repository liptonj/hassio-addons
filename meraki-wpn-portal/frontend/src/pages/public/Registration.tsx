import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Wifi, User, Mail, Building2, Ticket, Smartphone } from 'lucide-react'
import { register, getPortalOptions, getPublicAreas } from '../../api/client'
import type { RegistrationRequest } from '../../types/user'

export default function Registration() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Capture splash page parameters from Meraki
  // login_url = Sign-on splash, grant_url = Click-through splash
  const clientMac = searchParams.get('mac')
  const loginUrl = searchParams.get('login_url')
  const grantUrl = searchParams.get('grant_url')
  const continueUrl = searchParams.get('continue_url')

  const [formData, setFormData] = useState<RegistrationRequest>({
    name: '',
    email: '',
    unit: '',
    area_id: '',
    invite_code: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})

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

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
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
    <div className="animate-slide-up" style={{ maxWidth: '480px', margin: '0 auto' }}>
      {/* Property Logo/Title */}
      <div className="text-center mb-8">
        {options?.logo_url && (
          <img
            src={options.logo_url}
            alt={options.property_name}
            style={{ maxWidth: '200px', height: 'auto', margin: '0 auto 1rem' }}
          />
        )}
        <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>
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
          <div
            className="mb-4 p-4 flex items-center gap-3"
            style={{
              background: 'rgba(0, 164, 228, 0.1)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(0, 164, 228, 0.3)',
            }}
          >
            <Smartphone size={20} style={{ color: 'var(--meraki-blue)' }} />
            <div>
              <div className="text-sm font-medium">Registering This Device</div>
              <div className="text-xs opacity-70">MAC: {clientMac}</div>
            </div>
          </div>
        )}

        {errors.form && (
          <div
            className="mb-4 p-4"
            style={{
              background: 'var(--error-light)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--error)',
            }}
          >
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
                  <span className="text-muted" style={{ fontWeight: 'normal' }}>
                    {' '}(if provided)
                  </span>
                )}
              </span>
            </label>
            <input
              type="text"
              className={`form-input ${errors.invite_code ? 'error' : ''}`}
              placeholder="WELCOME2026"
              value={formData.invite_code}
              onChange={(e) => handleChange('invite_code', e.target.value.toUpperCase())}
              disabled={mutation.isPending}
              style={{ textTransform: 'uppercase' }}
            />
            {errors.invite_code && <p className="form-error">{errors.invite_code}</p>}
          </div>
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
