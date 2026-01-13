import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Mail, Lock, User, ArrowLeft, Wifi, LogIn, UserPlus } from 'lucide-react'
import { userLogin, userSignup } from '../../api/client'

type AuthMode = 'login' | 'signup'

export default function UserAuth() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Capture splash page parameters to pass through
  const clientMac = searchParams.get('mac')
  const loginUrl = searchParams.get('login_url')
  const grantUrl = searchParams.get('grant_url')
  const continueUrl = searchParams.get('continue_url')

  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [unit, setUnit] = useState('')
  const [error, setError] = useState('')

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
        // No iPSK yet - redirect to register to create one
        const params = new URLSearchParams()
        if (clientMac) params.set('mac', clientMac)
        if (loginUrl) params.set('login_url', loginUrl)
        if (grantUrl) params.set('grant_url', grantUrl)
        if (continueUrl) params.set('continue_url', continueUrl)
        params.set('prefill_email', data.user.email)
        params.set('prefill_name', data.user.name)
        if (data.user.unit) params.set('prefill_unit', data.user.unit)

        navigate(`/register?${params.toString()}`)
      }
    },
    onError: (error: Error) => {
      setError(error.message)
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
    onError: (error: Error) => {
      setError(error.message)
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

  const isLoading = loginMutation.isPending || signupMutation.isPending

  return (
    <div
      className="page-container"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
        {/* Header */}
        <div className="text-center mb-6">
          <div
            className="mx-auto mb-4 flex items-center justify-center"
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--meraki-blue), var(--meraki-dark-blue))',
            }}
          >
            <Wifi size={28} color="white" />
          </div>
          <h1 className="text-xl font-bold mb-1">
            {mode === 'login' ? 'Welcome Back' : 'Create Account'}
          </h1>
          <p className="text-sm opacity-70">
            {mode === 'login'
              ? 'Login to access your WiFi credentials'
              : 'Sign up to get your personal WiFi access'}
          </p>
        </div>

        {/* Tab Switcher */}
        <div
          className="flex mb-6"
          style={{
            background: 'var(--gray-100)',
            borderRadius: 'var(--radius-md)',
            padding: '4px',
          }}
        >
          <button
            onClick={() => { setMode('login'); setError('') }}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium"
            style={{
              background: mode === 'login' ? 'white' : 'transparent',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              color: mode === 'login' ? 'var(--meraki-blue)' : 'var(--gray-600)',
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
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              color: mode === 'signup' ? 'var(--meraki-blue)' : 'var(--gray-600)',
              boxShadow: mode === 'signup' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              transition: 'all 0.2s',
            }}
          >
            <UserPlus size={16} />
            Sign Up
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div
            className="mb-4 p-3 text-sm"
            style={{
              background: 'rgba(220, 38, 38, 0.1)',
              color: '#dc2626',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(220, 38, 38, 0.2)',
            }}
          >
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Full Name</label>
              <div className="relative">
                <User
                  size={18}
                  className="absolute left-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--gray-400)' }}
                />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full"
                  style={{ paddingLeft: '40px' }}
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
                className="absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--gray-400)' }}
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full"
                style={{ paddingLeft: '40px' }}
                required
              />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Password</label>
            <div className="relative">
              <Lock
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--gray-400)' }}
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'signup' ? 'Create a password (8+ chars)' : 'Enter your password'}
                className="w-full"
                style={{ paddingLeft: '40px' }}
                required
                minLength={mode === 'signup' ? 8 : 1}
              />
            </div>
          </div>

          {mode === 'signup' && (
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Unit/Room (Optional)</label>
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g., Apt 101, Room 5B"
                className="w-full"
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

        {/* Back Link */}
        <button
          onClick={goBack}
          className="w-full mt-4 flex items-center justify-center gap-2 text-sm"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--gray-500)',
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
