import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Mail, Lock, User, ArrowLeft, Wifi, LogIn, UserPlus, Shield } from 'lucide-react'
import { userLogin, userSignup, createUserIPSK } from '../../api/client'
import { useBranding } from '../../context/BrandingContext'
import { isCaptivePortal, getCaptivePortalInstructions } from '../../utils/captivePortal'

type AuthMode = 'login' | 'signup'

export default function UserAuth() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const {
    propertyName,
    logoUrl,
    primaryColor,
    selfRegistrationEnabled,
    localAuthEnabled,
    oauthEnabled,
    isLoading: brandingLoading
  } = useBranding()

  // Captive portal detection
  const [inCaptivePortal, setInCaptivePortal] = useState(false)
  const [captivePortalInstructions, setCaptivePortalInstructions] = useState('')

  useEffect(() => {
    setInCaptivePortal(isCaptivePortal())
    setCaptivePortalInstructions(getCaptivePortalInstructions())
  }, [])

  // Capture splash page parameters to pass through
  const clientMac = searchParams.get('mac')
  const loginUrl = searchParams.get('login_url')
  const grantUrl = searchParams.get('grant_url')
  const continueUrl = searchParams.get('continue_url')

  const prefillEmail = searchParams.get('email') || ''
  const prefillName = searchParams.get('prefill_name') || ''
  const prefillUnit = searchParams.get('prefill_unit') || ''

  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState(prefillEmail)
  const [password, setPassword] = useState('')
  const [name, setName] = useState(prefillName)
  const [unit, setUnit] = useState(prefillUnit)
  const [error, setError] = useState('')
  const [isCreatingIPSK, setIsCreatingIPSK] = useState(false)

  const createIPSKMutation = useMutation({
    mutationFn: createUserIPSK,
    onSuccess: (data) => {
      // iPSK created! Redirect to success page with credentials
      navigate('/success', {
        state: {
          ipsk_id: data.ipsk_id,
          ipsk_name: data.ipsk_name,
          ssid_name: data.ssid_name,
          passphrase: data.passphrase,
          qr_code: data.qr_code,
          wifi_config_string: data.wifi_config_string,
          email,
          client_mac: clientMac,
          login_url: loginUrl ? decodeURIComponent(loginUrl) : null,
          grant_url: grantUrl ? decodeURIComponent(grantUrl) : null,
          continue_url: continueUrl ? decodeURIComponent(continueUrl) : null,
        }
      })
      setIsCreatingIPSK(false)
    },
    onError: (err: Error) => {
      setError(err.message)
      setIsCreatingIPSK(false)
    },
  })

  const loginMutation = useMutation({
    mutationFn: () => userLogin(email, password),
    onSuccess: (data) => {
      // User logged in - check if they have an iPSK
      if (data.user.has_ipsk) {
        // Redirect to success with their existing credentials
        navigate('/my-network', {
          state: {
            email: data.user.email,
            client_mac: clientMac,
            login_url: loginUrl ? decodeURIComponent(loginUrl) : null,
            grant_url: grantUrl ? decodeURIComponent(grantUrl) : null,
            continue_url: continueUrl ? decodeURIComponent(continueUrl) : null,
          }
        })
      } else {
        // No iPSK yet - auto-create one!
        setIsCreatingIPSK(true)
        setError('')
        createIPSKMutation.mutate()
      }
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const signupMutation = useMutation({
    mutationFn: () => userSignup({ email, password, name, unit: unit || undefined }),
    onSuccess: () => {
      // User signed up - redirect to register to create iPSK
      const params = new URLSearchParams()
      if (clientMac) params.set('mac', clientMac)
      if (loginUrl) params.set('login_url', loginUrl)
      if (grantUrl) params.set('grant_url', grantUrl)
      if (continueUrl) params.set('continue_url', continueUrl)
      params.set('prefill_email', email)
      params.set('prefill_name', name)
      if (unit) params.set('prefill_unit', unit)

      navigate(`/register?${params.toString()}`)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (mode === 'login') {
      loginMutation.mutate()
    } else {
      signupMutation.mutate()
    }
  }

  const goBack = () => {
    // Go back to splash landing with all params
    const params = new URLSearchParams()
    if (clientMac) params.set('mac', clientMac)
    if (loginUrl) params.set('login_url', loginUrl)
    if (grantUrl) params.set('grant_url', grantUrl)
    if (continueUrl) params.set('continue_url', continueUrl)

    navigate(`/splash-landing?${params.toString()}`)
  }

  const handleSSOLogin = () => {
    const params = new URLSearchParams()
    if (clientMac) params.set('mac', clientMac)
    if (loginUrl) params.set('login_url', loginUrl)
    if (grantUrl) params.set('grant_url', grantUrl)
    if (continueUrl) params.set('continue_url', continueUrl)
    navigate(`/login?${params.toString()}`)
  }

  const isLoading = loginMutation.isPending || signupMutation.isPending || isCreatingIPSK

  // Loading state while branding loads
  if (brandingLoading) {
    return (
      <div
        className="page-container min-h-screen flex items-center justify-center"
      >
        <div className="card max-w-[400px] w-full text-center">
          <div className="loading-spinner w-12 h-12 mx-auto" />
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  // Determine if signup tab should be shown
  const showSignupTab = selfRegistrationEnabled

  return (
    <div
      className="page-container min-h-screen flex items-center justify-center"
    >
      <div className="card max-w-[400px] w-full">
        {/* Header */}
        <div className="text-center mb-6">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={propertyName}
              className="mx-auto mb-4 max-w-[120px] h-auto max-h-[60px] object-contain"
            />
          ) : (
            <div
              className="mx-auto mb-4 flex items-center justify-center"
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${primaryColor}, var(--primary-color-dark))`,
              }}
            >
              <Wifi size={28} color="white" />
            </div>
          )}
          <h1 className="text-xl font-bold mb-1">
            {mode === 'login' ? 'Welcome Back' : 'Create Account'}
          </h1>
          <p className="text-sm opacity-70">
            {mode === 'login'
              ? 'Login to access your WiFi credentials'
              : 'Sign up to get your personal WiFi access'}
          </p>
        </div>

        {/* Tab Switcher - only show if both login and signup are available */}
        {localAuthEnabled && showSignupTab && (
          <div
            className="flex mb-6"
            style={{
              background: 'var(--gray-100, #f7fafc)',
              borderRadius: 'var(--radius-md, 10px)',
              padding: '4px',
            }}
          >
            <button
              onClick={() => { setMode('login'); setError('') }}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium"
              style={{
                background: mode === 'login' ? 'white' : 'transparent',
                borderRadius: 'var(--radius-sm, 8px)',
                border: 'none',
                cursor: 'pointer',
                color: mode === 'login' ? primaryColor : 'var(--gray-600, #718096)',
                boxShadow: mode === 'login' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              <LogIn size={16} />
              Login
            </button>
            <button
              onClick={() => { setMode('signup'); setError('') }}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium"
              style={{
                background: mode === 'signup' ? 'white' : 'transparent',
                borderRadius: 'var(--radius-sm, 8px)',
                border: 'none',
                cursor: 'pointer',
                color: mode === 'signup' ? primaryColor : 'var(--gray-600, #718096)',
                boxShadow: mode === 'signup' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              <UserPlus size={16} />
              Sign Up
            </button>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div
            className="mb-4 p-3 text-sm"
            style={{
              background: 'rgba(220, 38, 38, 0.1)',
              color: '#dc2626',
              borderRadius: 'var(--radius-md, 10px)',
              border: '1px solid rgba(220, 38, 38, 0.2)',
            }}
          >
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {mode === 'signup' && showSignupTab && (
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Full Name</label>
              <div className="relative">
                <User
                  size={18}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500"
                />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full form-input pl-10"
                  required
                  minLength={2}
                />
              </div>
            </div>
          )}

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Email</label>
            <div className="relative">
              <Mail
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500"
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full form-input pl-10"
                required
              />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Password</label>
            <div className="relative">
              <Lock
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'signup' ? 'Create a password (8+ chars)' : 'Enter your password'}
                className="w-full form-input pl-10"
                required
                minLength={mode === 'signup' ? 8 : 1}
              />
            </div>
          </div>

          {mode === 'signup' && showSignupTab && (
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Unit/Room (Optional)</label>
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g., Apt 101, Room 5B"
                className="w-full form-input"
              />
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary w-full"
            disabled={isLoading}
          >
            {isLoading
              ? (mode === 'login' ? 'Logging in...' : 'Creating account...')
              : (mode === 'login' ? 'Login' : 'Create Account')}
          </button>
        </form>

        {/* SSO Option */}
        {oauthEnabled && (
          <div className="mt-4">
            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-500 uppercase">or</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>
            <button
              onClick={handleSSOLogin}
              className="w-full p-3 flex items-center justify-center gap-2 text-sm font-medium"
              style={{
                background: 'transparent',
                color: primaryColor,
                borderRadius: 'var(--radius-md, 10px)',
                border: `2px solid ${primaryColor}`,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.background = `rgba(var(--primary-color-rgb), 0.1)`
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              <Shield size={18} />
              Sign in with SSO
            </button>
          </div>
        )}

        {/* Captive Portal Instructions */}
        {inCaptivePortal && captivePortalInstructions && (
          <div 
            className="mt-4 p-3 rounded-lg text-center"
            style={{
              background: `rgba(var(--primary-color-rgb), 0.1)`,
              border: `1px solid rgba(var(--primary-color-rgb), 0.2)`,
            }}
          >
            <p className="text-sm font-medium" style={{ color: primaryColor }}>
              {captivePortalInstructions}
            </p>
          </div>
        )}

        {/* Back Link */}
        <button
          onClick={goBack}
          className="w-full mt-4 flex items-center justify-center gap-2 text-sm"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--gray-500, #a0aec0)',
            cursor: 'pointer',
            padding: '8px',
          }}
        >
          <ArrowLeft size={16} />
          Back to options
        </button>
      </div>
    </div>
  )
}
