import { useSearchParams, useNavigate } from 'react-router-dom'
import { Wifi, UserPlus, LogIn, ArrowRight, Smartphone } from 'lucide-react'

export default function SplashLanding() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

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

  return (
    <div className="page-container" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '440px', width: '100%' }}>
        {/* Header */}
        <div className="text-center mb-6">
          <div
            className="mx-auto mb-4 flex items-center justify-center"
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--meraki-blue), var(--meraki-dark-blue))',
            }}
          >
            <Wifi size={32} color="white" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Welcome to WiFi</h1>
          <p className="text-gray-600">Get connected in seconds</p>
        </div>

        {/* Device Info */}
        {clientMac && (
          <div
            className="mb-6 p-3 flex items-center gap-3"
            style={{
              background: 'rgba(0, 164, 228, 0.08)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(0, 164, 228, 0.2)',
            }}
          >
            <Smartphone size={18} style={{ color: 'var(--meraki-blue)' }} />
            <div className="text-sm">
              <span className="opacity-70">Device: </span>
              <span className="font-mono">{clientMac}</span>
            </div>
          </div>
        )}

        {/* New User Option - Primary */}
        <button
          onClick={handleNewUser}
          className="w-full p-4 mb-3 flex items-center gap-4 text-left"
          style={{
            background: 'linear-gradient(135deg, var(--meraki-blue), var(--meraki-dark-blue))',
            color: 'white',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            cursor: 'pointer',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 164, 228, 0.3)'
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
            <div className="text-sm opacity-80">Register to get your WiFi credentials</div>
          </div>
          <ArrowRight size={20} />
        </button>

        {/* Returning User - Login Option */}
        <button
          onClick={handleLogin}
          className="w-full p-4 flex items-center gap-4 text-left"
          style={{
            background: 'var(--gray-50)',
            color: 'var(--gray-800)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--gray-200)',
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = 'var(--gray-100)'
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = 'var(--gray-50)'
          }}
        >
          <div
            className="flex items-center justify-center"
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'var(--gray-200)',
            }}
          >
            <LogIn size={24} style={{ color: 'var(--gray-600)' }} />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-lg">Already Have an Account?</div>
            <div className="text-sm opacity-70">Login to view your credentials</div>
          </div>
          <ArrowRight size={20} style={{ color: 'var(--gray-400)' }} />
        </button>

        {/* Footer Note */}
        <div className="mt-6 text-center text-xs opacity-60">
          Connect once, and your device will remember the network
        </div>
      </div>
    </div>
  )
}
