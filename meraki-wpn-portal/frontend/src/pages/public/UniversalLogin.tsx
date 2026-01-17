import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Mail, Lock, ArrowRight, LogIn, Shield, Wifi } from 'lucide-react'
import { lookupEmail, userLogin, UserInfo } from '../../api/client'
import type { EmailLookupResponse } from '../../types/user'
import { useBranding } from '../../context/BrandingContext'
import { isCaptivePortal, getCaptivePortalInstructions } from '../../utils/captivePortal'

type FlowState = 'email' | 'password' | 'signup' | 'sso_redirect' | 'admin_choice'

export default function UniversalLogin() {
  const navigate = useNavigate()
  const { propertyName, logoUrl, primaryColor, selfRegistrationEnabled, isLoading: brandingLoading } = useBranding()
  const [flowState, setFlowState] = useState<FlowState>('email')

  // Captive portal detection
  const [inCaptivePortal, setInCaptivePortal] = useState(false)
  const [captivePortalInstructions, setCaptivePortalInstructions] = useState('')

  useEffect(() => {
    setInCaptivePortal(isCaptivePortal())
    setCaptivePortalInstructions(getCaptivePortalInstructions())
  }, [])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [lookupResult, setLookupResult] = useState<EmailLookupResponse | null>(null)
  const [loggedInUser, setLoggedInUser] = useState<UserInfo | null>(null)
  const [error, setError] = useState('')

  // Remember email in localStorage
  const saveEmail = (emailValue: string) => {
    if (emailValue) {
      localStorage.setItem('last_login_email', emailValue)
    }
  }

  // Load remembered email
  const loadRememberedEmail = () => {
    const remembered = localStorage.getItem('last_login_email')
    if (remembered) {
      setEmail(remembered)
    }
  }

  // Email lookup mutation
  const lookupMutation = useMutation({
    mutationFn: lookupEmail,
    onSuccess: (data) => {
      setLookupResult(data)
      saveEmail(email)
      
      if (data.suggested_action === 'login') {
        setFlowState('password')
      } else if (data.suggested_action === 'sso_redirect') {
        setFlowState('sso_redirect')
        // Auto-redirect to SSO
        if (!data.oauth_provider) {
          setError('SSO provider is not configured for this account')
          setFlowState('email')
          return
        }
        setTimeout(() => {
          window.location.href = `/api/auth/login/${data.oauth_provider}?username=${encodeURIComponent(email)}`
        }, 1500)
      } else if (data.suggested_action === 'signup') {
        setFlowState('signup')
      }
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: () => userLogin(email, password),
    onSuccess: (data) => {
      setLoggedInUser(data.user)
      
      // If user is admin, show them a choice
      if (data.user.is_admin) {
        // Also store the token as admin_token for admin routes
        const userToken = localStorage.getItem('user_token')
        if (userToken) {
          localStorage.setItem('admin_token', userToken)
        }
        setFlowState('admin_choice')
      } else {
        // Regular user - redirect to user account page
        navigate('/user-account')
      }
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError('Please enter your email address')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address')
      return
    }

    lookupMutation.mutate(email)
  }

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!password) {
      setError('Please enter your password')
      return
    }

    loginMutation.mutate()
  }

  const handleBack = () => {
    setFlowState('email')
    setPassword('')
    setError('')
    setLookupResult(null)
  }

  // Loading state
  if (brandingLoading) {
    return (
      <div className="animate-slide-up max-w-[480px] mx-auto text-center">
        <div className="card">
          <div className="loading-spinner" style={{ width: '48px', height: '48px' }} />
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-slide-up max-w-[480px] mx-auto">
      <div className="text-center mb-8">
        {logoUrl ? (
          <img
            src={logoUrl}
            alt={propertyName}
            className="mx-auto mb-4"
            style={{ maxWidth: '140px', height: 'auto', maxHeight: '70px', objectFit: 'contain' }}
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
        <h1 className="text-2xl mb-2">
          {flowState === 'admin_choice' ? 'Login Successful' : `Sign In to ${propertyName}`}
        </h1>
        <p className="text-muted">
          {flowState === 'email' && 'Enter your email to continue'}
          {flowState === 'password' && 'Enter your password'}
          {flowState === 'sso_redirect' && 'Redirecting to sign in...'}
          {flowState === 'signup' && 'Create your account'}
          {flowState === 'admin_choice' && 'Choose where to go'}
        </p>
      </div>

      {/* Email Step */}
      {flowState === 'email' && (
        <form onSubmit={handleEmailSubmit} className="card">
          {error && (
            <div className="mb-4 p-4 bg-error-light rounded-lg text-error">
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Mail size={16} /> Email Address
              </span>
            </label>
            <input
              type="email"
              className={`form-input ${error ? 'error' : ''}`}
              placeholder="john@example.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                setError('')
              }}
              onFocus={loadRememberedEmail}
              disabled={lookupMutation.isPending}
              autoFocus
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg btn-full"
            disabled={lookupMutation.isPending}
          >
            {lookupMutation.isPending ? (
              <>
                <span className="loading-spinner" /> Checking...
              </>
            ) : (
              <>
                Continue <ArrowRight size={20} />
              </>
            )}
          </button>

          <p className="text-center mt-6 text-muted text-sm">
            Don't have an account?{' '}
            <a href="/register">Register here</a>
          </p>
        </form>
      )}

      {/* Password Step */}
      {flowState === 'password' && (
        <form onSubmit={handlePasswordSubmit} className="card">
          {error && (
            <div className="mb-4 p-4 bg-error-light rounded-lg text-error">
              {error}
            </div>
          )}

          <div className="mb-4 p-3 bg-gray-50 rounded-lg dark:bg-gray-800">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Signing in as: <span className="font-semibold">{email}</span>
            </p>
            <button
              type="button"
              onClick={handleBack}
              className="text-xs hover:underline mt-1"
              style={{ color: primaryColor }}
            >
              Change email
            </button>
          </div>

          <div className="form-group">
            <label className="form-label">
              <span className="form-label-icon">
                <Lock size={16} /> Password
              </span>
            </label>
            <input
              type="password"
              className={`form-input ${error ? 'error' : ''}`}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setError('')
              }}
              disabled={loginMutation.isPending}
              autoFocus
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg btn-full"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? (
              <>
                <span className="loading-spinner" /> Signing in...
              </>
            ) : (
              <>
                <LogIn size={20} /> Sign In
              </>
            )}
          </button>

          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={handleBack}
              className="btn btn-ghost text-sm"
            >
              Back
            </button>
          </div>
        </form>
      )}

      {/* SSO Redirect */}
      {flowState === 'sso_redirect' && lookupResult && (
        <div className="card text-center">
          <div className="mb-4">
            <div 
              className="inline-block p-4 rounded-full mb-4"
              style={{ background: `rgba(var(--primary-color-rgb), 0.1)` }}
            >
              <LogIn size={32} style={{ color: primaryColor }} />
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Redirecting to {lookupResult.oauth_provider === 'duo' ? 'Duo' : 'Microsoft'}
            </h3>
            <p className="text-sm text-muted mb-4">
              Please wait while we redirect you to sign in...
            </p>
            <div className="flex justify-center">
              <span className="loading-spinner" />
            </div>
          </div>

          <button
            type="button"
            onClick={handleBack}
            className="btn btn-ghost text-sm"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Signup Flow */}
      {flowState === 'signup' && (
        <div className="card">
          <div 
            className="p-4 rounded-lg border mb-4"
            style={{ 
              background: `rgba(var(--primary-color-rgb), 0.08)`,
              borderColor: `rgba(var(--primary-color-rgb), 0.2)`
            }}
          >
            <p className="text-sm" style={{ color: 'var(--gray-700, #4a5568)' }}>
              We didn't find an account with <span className="font-semibold">{email}</span>.
            </p>
          </div>

          {selfRegistrationEnabled ? (
            <>
              <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
                Would you like to create an account or register for WiFi access?
              </p>

              <div className="space-y-3">
                <a
                  href={`/register?email=${encodeURIComponent(email)}`}
                  className="btn btn-primary btn-full"
                >
                  Register for WiFi Access
                </a>
                <a
                  href={`/user-auth?email=${encodeURIComponent(email)}`}
                  className="btn btn-secondary btn-full"
                >
                  Create User Account
                </a>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
              Self-registration is not available. Please contact your administrator for access.
            </p>
          )}

          <button
            type="button"
            onClick={handleBack}
            className="btn btn-ghost text-sm w-full mt-4"
          >
            Back
          </button>
        </div>
      )}

      {/* Admin Choice - shown after login if user is admin */}
      {flowState === 'admin_choice' && loggedInUser && (
        <div className="card">
          <div className="text-center mb-6">
            <div className="inline-block p-4 bg-green-50 rounded-full mb-4">
              <Shield size={32} className="text-green-600" />
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Welcome, {loggedInUser.name}!
            </h3>
            <p className="text-sm text-muted">
              You have admin access. Where would you like to go?
            </p>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => navigate('/admin')}
              className="btn btn-primary btn-full flex items-center justify-center gap-2"
            >
              <Shield size={20} /> Admin Dashboard
            </button>
            <button
              onClick={() => navigate('/user-account')}
              className="btn btn-secondary btn-full flex items-center justify-center gap-2"
            >
              <Wifi size={20} /> My WiFi Access
            </button>
            {!loggedInUser.has_ipsk && (
              <button
                onClick={() => navigate(`/register?email=${encodeURIComponent(email)}`)}
                className="btn btn-outline btn-full flex items-center justify-center gap-2"
              >
                <Wifi size={20} /> Register My Device
              </button>
            )}
          </div>
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
    </div>
  )
}
