import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, Wifi, Copy, Check } from 'lucide-react'
import { getMyNetwork } from '../../api/client'
import QRCode from '../../components/QRCode'

export default function MyNetwork() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [copiedField, setCopiedField] = useState<string | null>(null)

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

  const handleCopy = async (field: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 2000)
  }

  const data = mutation.data

  return (
    <div className="animate-slide-up" style={{ maxWidth: '480px', margin: '0 auto' }}>
      <div className="text-center mb-6">
        <h1 style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>My Network</h1>
        <p className="text-muted">
          Enter your registered email to retrieve your WiFi credentials
        </p>
      </div>

      {/* Lookup Form */}
      {!data && (
        <form onSubmit={handleSubmit} className="card mb-6">
          {error && (
            <div
              className="mb-4 p-4"
              style={{
                background: 'var(--error-light)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--error)',
              }}
            >
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
            <Wifi size={24} style={{ color: 'var(--meraki-blue)' }} />
            <h3 style={{ margin: 0 }}>{data.ipsk_name}</h3>
            <span className={`badge badge-${data.status === 'active' ? 'success' : 'warning'}`}>
              {data.status}
            </span>
          </div>

          {/* Network Name */}
          <div className="form-group">
            <label className="form-label">Network Name (SSID)</label>
            <div className="credential-box">
              <span className="credential-value">{data.ssid_name}</span>
              <button
                onClick={() => handleCopy('ssid', data.ssid_name)}
                className="credential-copy"
                title="Copy"
              >
                {copiedField === 'ssid' ? (
                  <Check size={16} color="var(--success)" />
                ) : (
                  <Copy size={16} />
                )}
              </button>
            </div>
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="credential-box">
              <span className="credential-value">{data.passphrase}</span>
              <button
                onClick={() => handleCopy('password', data.passphrase)}
                className="credential-copy"
                title="Copy"
              >
                {copiedField === 'password' ? (
                  <Check size={16} color="var(--success)" />
                ) : (
                  <Copy size={16} />
                )}
              </button>
            </div>
          </div>

          {/* Stats */}
          {data.connected_devices > 0 && (
            <p className="text-sm text-muted mt-4">
              Currently {data.connected_devices} device(s) connected
            </p>
          )}

          {/* QR Code */}
          {data.qr_code && (
            <div className="mt-6">
              <QRCode
                dataUrl={data.qr_code}
                size={180}
                hint="Scan to connect"
              />
            </div>
          )}

          {/* Back Button */}
          <button
            onClick={() => mutation.reset()}
            className="btn btn-secondary btn-full mt-6"
          >
            Look Up Another Email
          </button>
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
