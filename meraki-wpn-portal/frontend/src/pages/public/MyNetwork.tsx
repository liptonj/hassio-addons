import { useEffect, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Search, Wifi } from 'lucide-react'
import { getMyNetwork } from '../../api/client'
import QRCodeActions from '../../components/QRCodeActions'
import { isCaptivePortal, getCaptivePortalInstructions } from '../../utils/captivePortal'

export default function MyNetwork() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const state = location.state as { email?: string } | null
  const prefillEmail = state?.email || searchParams.get('email') || ''
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [hasAutoSubmitted, setHasAutoSubmitted] = useState(false)
  const inCaptivePortal = isCaptivePortal()
  const captivePortalInstructions = getCaptivePortalInstructions()

  const mutation = useMutation({
    mutationFn: () => getMyNetwork(email),
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
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

    mutation.mutate()
  }

  const data = mutation.data

  useEffect(() => {
    if (!prefillEmail || hasAutoSubmitted || mutation.isPending) {
      return
    }
    setEmail(prefillEmail)
    setHasAutoSubmitted(true)
    mutation.mutate()
  }, [prefillEmail, hasAutoSubmitted, mutation])

  return (
    <div className="animate-slide-up max-w-[480px] mx-auto">
      <div className="text-center mb-6">
        <h1 className="text-[1.75rem] mb-2">My Network</h1>
        <p className="text-muted">
          Enter your registered email to retrieve your WiFi credentials
        </p>
      </div>

      {/* Lookup Form */}
      {!data && (
        <form onSubmit={handleSubmit} className="card mb-6">
          {error && (
            <div className="mb-4 p-4 bg-error-light rounded-lg text-error">
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input
              type="email"
              className={`form-input ${error ? 'error' : ''}`}
              placeholder="john@example.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                setError('')
              }}
              disabled={mutation.isPending}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <span className="loading-spinner" /> Looking up...
              </>
            ) : (
              <>
                <Search size={18} /> Find My Credentials
              </>
            )}
          </button>
        </form>
      )}

      {/* Results */}
      {data && (
        <div className="card animate-fade-in">
          <div className="flex items-center gap-2 mb-4">
            <Wifi size={24} className="text-meraki-blue" />
            <h3 className="m-0">{data.ipsk_name}</h3>
            <span className={`badge badge-${data.status === 'active' ? 'success' : 'warning'}`}>
              {data.status}
            </span>
          </div>

          {/* Stats */}
          {data.connected_devices > 0 && (
            <p className="text-sm text-muted mb-4">
              Currently {data.connected_devices} device(s) connected
            </p>
          )}

          {/* QR Code with Actions */}
          {data.qr_code && (
            <QRCodeActions
              qrCodeDataUrl={data.qr_code}
              ssid={data.ssid_name}
              passphrase={data.passphrase}
            />
          )}

          {/* Account Link */}
          <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm text-blue-800 mb-2">
              <strong>Have an account?</strong>
            </p>
            <p className="text-sm text-blue-700 mb-3">
              Sign in to manage your devices, change your password, and more.
            </p>
            <a href="/user-auth" className="btn btn-secondary btn-sm">
              Sign In to Your Account
            </a>
          </div>

          {/* Back Button */}
          <button
            onClick={() => mutation.reset()}
            className="btn btn-secondary btn-full mt-6"
          >
            Look Up Another Email
          </button>
        </div>
      )}

      {/* Captive Portal Footer */}
      {inCaptivePortal && captivePortalInstructions && data && (
        <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200 text-center">
          <p className="text-sm text-blue-800 font-medium">
            {captivePortalInstructions}
          </p>
        </div>
      )}

      {/* Help */}
      <p className="text-center mt-6 text-muted text-sm">
        Don't have WiFi access yet?{' '}
        <a href="/register">Register here</a>
      </p>
    </div>
  )
}
