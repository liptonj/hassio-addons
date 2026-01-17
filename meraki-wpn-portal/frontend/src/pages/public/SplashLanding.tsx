import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Wifi, UserPlus, LogIn, ArrowRight, Smartphone, Shield } from 'lucide-react'
import { useBranding } from '../../context/BrandingContext'
import { isCaptivePortal, getCaptivePortalInstructions, getCaptivePortalType } from '../../utils/captivePortal'
import { getDeviceInfo } from '../../utils/deviceDetection'

export default function SplashLanding() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { 
    propertyName, 
    logoUrl, 
    primaryColor,
    // New registration modes
    openRegistrationEnabled,
    openRegistrationApprovalEnabled,
    accountOnlyEnabled,
    inviteCodeAccountEnabled,
    inviteCodeOnlyEnabled,
    // Login methods
    localAuthEnabled,
    oauthEnabled,
    isLoading 
  } = useBranding()

  // Captive portal and device detection
  const [inCaptivePortal, setInCaptivePortal] = useState(false)
  const [captivePortalInstructions, setCaptivePortalInstructions] = useState('')
  const [deviceInfo, setDeviceInfo] = useState<ReturnType<typeof getDeviceInfo> | null>(null)

  useEffect(() => {
    // Detect captive portal
    setInCaptivePortal(isCaptivePortal())
    setCaptivePortalInstructions(getCaptivePortalInstructions())
    
    // Log device info for debugging
    const info = getDeviceInfo()
    setDeviceInfo(info)
    
    if (isCaptivePortal()) {
      console.log('Captive portal detected:', getCaptivePortalType())
    }
    console.log('Device info:', info)
  }, [])

  // Capture splash page parameters from Meraki
  // login_url = Sign-on splash (POST credentials)
  // grant_url = Click-through splash (simple GET)
  const clientMac = searchParams.get('mac')
  const loginUrl = searchParams.get('login_url')
  const grantUrl = searchParams.get('grant_url')
  const continueUrl = searchParams.get('continue_url')

  // Build query string for passing to other pages
  const buildQueryString = () => {
    const params = new URLSearchParams()
    if (clientMac) params.set('mac', clientMac)
    if (loginUrl) params.set('login_url', loginUrl)
    if (grantUrl) params.set('grant_url', grantUrl)
    if (continueUrl) params.set('continue_url', continueUrl)
    return params.toString()
  }

  const handleNewUser = () => {
    const queryString = buildQueryString()
    navigate(`/register${queryString ? `?${queryString}` : ''}`)
  }

  const handleLogin = () => {
    const queryString = buildQueryString()
    navigate(`/user-auth${queryString ? `?${queryString}` : ''}`)
  }

  const handleUniversalLogin = () => {
    const queryString = buildQueryString()
    navigate(`/login${queryString ? `?${queryString}` : ''}`)
  }

  // Determine what options to show based on registration modes
  const canRegisterWithAccount = openRegistrationEnabled || openRegistrationApprovalEnabled || inviteCodeAccountEnabled
  const canUseInviteCodeOnly = inviteCodeOnlyEnabled
  const canLogin = localAuthEnabled || oauthEnabled || accountOnlyEnabled

  // Loading state
  if (isLoading) {
    return (
      <div 
        className="page-container" 
        style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <div className="card" style={{ maxWidth: '440px', width: '100%', textAlign: 'center' }}>
          <div className="loading-spinner" style={{ width: '48px', height: '48px' }} />
          <p className="mt-4 text-gray-600">Loading portal...</p>
        </div>
      </div>
    )
  }

  return (
    <div 
      className="page-container" 
      style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <div className="card" style={{ maxWidth: '440px', width: '100%' }}>
        {/* Header */}
        <div className="text-center mb-6">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={propertyName}
              className="mx-auto mb-4"
              style={{ maxWidth: '160px', height: 'auto', maxHeight: '80px', objectFit: 'contain' }}
            />
          ) : (
            <div
              className="mx-auto mb-4 flex items-center justify-center"
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${primaryColor}, var(--primary-color-dark))`,
              }}
            >
              <Wifi size={32} color="white" />
            </div>
          )}
          <h1 className="text-2xl font-bold mb-2">Welcome to {propertyName}</h1>
          <p className="text-gray-600">Get connected in seconds</p>
        </div>

        {/* Device Info */}
        {clientMac && (
          <div
            className="mb-6 p-3 flex items-center gap-3"
            style={{
              background: `rgba(var(--primary-color-rgb), 0.08)`,
              borderRadius: 'var(--radius-md, 10px)',
              border: `1px solid rgba(var(--primary-color-rgb), 0.2)`,
            }}
          >
            <Smartphone size={18} style={{ color: primaryColor }} />
            <div className="text-sm">
              <span className="opacity-70">Device: </span>
              <span className="font-mono">{clientMac}</span>
            </div>
          </div>
        )}

        {/* Invite Code Only - Quick access option */}
        {canUseInviteCodeOnly && (
          <button
            onClick={() => navigate(`/invite-code${buildQueryString() ? `?${buildQueryString()}` : ''}`)}
            data-testid="splash-invite-code-btn"
            className="w-full p-4 mb-3 flex items-center gap-4 text-left"
            style={{
              background: `linear-gradient(135deg, ${primaryColor}, var(--primary-color-dark))`,
              color: 'white',
              borderRadius: 'var(--radius-md, 10px)',
              border: 'none',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = `0 4px 12px rgba(var(--primary-color-rgb), 0.3)`
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <div
              className="flex items-center justify-center"
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'rgba(255, 255, 255, 0.2)',
              }}
            >
              <Wifi size={24} />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-lg">I Have an Invite Code</div>
              <div className="text-sm opacity-80">Enter your code to get connected</div>
            </div>
            <ArrowRight size={20} />
          </button>
        )}

        {/* New User Option - Registration with account (if any registration mode is enabled) */}
        {canRegisterWithAccount && (
          <button
            onClick={handleNewUser}
            data-testid="splash-new-user-btn"
            className="w-full p-4 mb-3 flex items-center gap-4 text-left"
            style={{
              background: `linear-gradient(135deg, ${primaryColor}, var(--primary-color-dark))`,
              color: 'white',
              borderRadius: 'var(--radius-md, 10px)',
              border: 'none',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = `0 4px 12px rgba(var(--primary-color-rgb), 0.3)`
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <div
              className="flex items-center justify-center"
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'rgba(255, 255, 255, 0.2)',
              }}
            >
              <UserPlus size={24} />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-lg">New User</div>
              <div className="text-sm opacity-80">
                {inviteCodeAccountEnabled && !openRegistrationEnabled
                  ? 'Register with your invite code'
                  : openRegistrationApprovalEnabled
                  ? 'Register (admin approval required)'
                  : 'Register to get your WiFi credentials'}
              </div>
            </div>
            <ArrowRight size={20} />
          </button>
        )}

        {/* Returning User - Login Option (if local auth is enabled) */}
        {canLogin && (
          <button
            onClick={handleLogin}
            data-testid="splash-login-btn"
            className="w-full p-4 flex items-center gap-4 text-left mb-3"
            style={{
              background: 'var(--gray-50, #fafbfc)',
              color: 'var(--gray-800, #2d3748)',
              borderRadius: 'var(--radius-md, 10px)',
              border: '1px solid var(--gray-200, #edf2f7)',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'var(--gray-100, #f7fafc)'
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'var(--gray-50, #fafbfc)'
            }}
          >
            <div
              className="flex items-center justify-center"
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'var(--gray-200, #edf2f7)',
              }}
            >
              <LogIn size={24} style={{ color: 'var(--gray-600, #718096)' }} />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-lg">Already Have an Account?</div>
              <div className="text-sm opacity-70">Login to view your credentials</div>
            </div>
            <ArrowRight size={20} style={{ color: 'var(--gray-400, #cbd5e0)' }} />
          </button>
        )}

        {/* OAuth/SSO Option (if enabled) */}
        {oauthEnabled && (
          <button
            onClick={handleUniversalLogin}
            data-testid="splash-sso-btn"
            className="w-full p-4 flex items-center gap-4 text-left"
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
            <div
              className="flex items-center justify-center"
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: `rgba(var(--primary-color-rgb), 0.15)`,
              }}
            >
              <Shield size={24} />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-lg">Sign in with SSO</div>
              <div className="text-sm opacity-70">Use your organization credentials</div>
            </div>
            <ArrowRight size={20} />
          </button>
        )}

        {/* Fallback message if nothing is enabled */}
        {!canRegisterWithAccount && !canUseInviteCodeOnly && !canLogin && (
          <div className="p-4 text-center text-gray-600" data-testid="splash-no-options">
            <p>WiFi registration is currently not available.</p>
            <p className="text-sm mt-2">Please contact your administrator for access.</p>
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

        {/* Device Info (for debugging - hidden in production) */}
        {deviceInfo && deviceInfo.type !== 'other' && (
          <div className="mt-4 text-center text-xs opacity-50">
            Detected: {deviceInfo.os} {deviceInfo.osVersion} • {deviceInfo.browser}
          </div>
        )}

        {/* Footer Note */}
        <div className="mt-4 text-center text-xs opacity-60">
          Connect once, and your device will remember the network
        </div>
      </div>
    </div>
  )
}
