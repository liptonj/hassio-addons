import { useLocation, Navigate } from 'react-router-dom'
import { CheckCircle, Copy, Check, Mail, Download, Wifi, Smartphone, Apple, QrCode } from 'lucide-react'
import { useState, useEffect } from 'react'
import QRCode from '../../components/QRCode'
import type { RegistrationResponse } from '../../types/user'
import { grantNetworkAccess } from '../../api/client'

// Extended response type with splash parameters
interface SuccessState extends RegistrationResponse {
  client_mac?: string | null
  login_url?: string | null
  grant_url?: string | null
  continue_url?: string | null
  is_returning_user?: boolean
}

// Detect device type
function getDeviceType(): 'ios' | 'android' | 'other' {
  const ua = navigator.userAgent.toLowerCase()
  if (/iphone|ipad|ipod|macintosh/.test(ua) && 'ontouchend' in document) {
    return 'ios'
  }
  if (/android/.test(ua)) {
    return 'android'
  }
  return 'other'
}

export default function Success() {
  const location = useLocation()
  const data = location.state as SuccessState | null
  const [deviceType, setDeviceType] = useState<'ios' | 'android' | 'other'>('other')
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [showAllOptions, setShowAllOptions] = useState(false)
  const [networkGranted, setNetworkGranted] = useState(false)
  const [grantingAccess, setGrantingAccess] = useState(false)

  useEffect(() => {
    setDeviceType(getDeviceType())
  }, [])

  // Grant network access if coming from splash page (via Meraki login_url or grant_url)
  useEffect(() => {
    const grantAccess = async () => {
      const hasGrantUrl = data?.login_url || data?.grant_url
      if (hasGrantUrl && !networkGranted && !grantingAccess) {
        setGrantingAccess(true)
        try {
          const result = await grantNetworkAccess({
            loginUrl: data?.login_url || undefined,
            grantUrl: data?.grant_url || undefined,
            clientMac: data?.client_mac || undefined,
            continueUrl: data?.continue_url || undefined,
          })
          setNetworkGranted(true)
          console.log('Network access granted:', result)
        } catch (error) {
          console.error('Failed to grant network access:', error)
        } finally {
          setGrantingAccess(false)
        }
      }
    }
    grantAccess()
  }, [data, networkGranted, grantingAccess])

  // Redirect if no data
  if (!data) {
    return <Navigate to="/register" replace />
  }

  const handleCopy = async (field: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 2000)
  }

  const handleDownloadConfig = () => {
    // Create a simple text file with WiFi config
    const content = `WiFi Network: ${data.ssid_name}\nPassword: ${data.passphrase}\n\nYou can also scan the QR code to connect automatically.`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'wifi-credentials.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleInstallProfile = () => {
    // Trigger mobileconfig download for iOS
    if (data.ipsk_id) {
      window.location.href = `/api/wifi-config/${data.ipsk_id}/mobileconfig`
    }
  }

  return (
    <div className="animate-slide-up" style={{ maxWidth: '480px', margin: '0 auto' }}>
      {/* Success Header */}
      <div className="text-center mb-6">
        <div
          style={{
            width: '80px',
            height: '80px',
            background: 'var(--success-light)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.5rem',
          }}
        >
          <CheckCircle size={48} color="var(--success)" />
        </div>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>You're All Set!</h1>
        <p className="text-muted">Your personal WiFi credentials are ready</p>
      </div>

      {/* Credentials Card */}
      <div className="card mb-6">
        <h3 className="mb-4" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Wifi size={20} style={{ color: 'var(--meraki-blue)' }} />
          Your WiFi Credentials
        </h3>

        {/* Network Name */}
        <div className="form-group">
          <label className="form-label">Network Name (SSID)</label>
          <div className="credential-box">
            <span className="credential-value">{data.ssid_name}</span>
            <button
              onClick={() => handleCopy('ssid', data.ssid_name)}
              className="credential-copy"
              title="Copy network name"
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
              title="Copy password"
            >
              {copiedField === 'password' ? (
                <Check size={16} color="var(--success)" />
              ) : (
                <Copy size={16} />
              )}
            </button>
          </div>
        </div>

        {/* QR Code */}
        {data.qr_code && (
          <div className="mt-6">
            <QRCode
              dataUrl={data.qr_code}
              size={200}
              hint="Scan with your phone's camera to connect automatically"
            />
          </div>
        )}
      </div>

      {/* Device Configuration Section */}
      <div className="card mb-6">
        <h3 className="mb-4" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Smartphone size={20} style={{ color: 'var(--meraki-blue)' }} />
          Configure This Device
        </h3>

        {/* iOS Device */}
        {deviceType === 'ios' && data.ipsk_id && (
          <div className="mb-4">
            <p className="text-sm text-muted mb-3">
              We detected you're on an Apple device. Install the WiFi profile to automatically configure your connection:
            </p>
            <button
              className="btn btn-primary"
              style={{ width: '100%' }}
              onClick={handleInstallProfile}
            >
              <Apple size={18} /> Install WiFi Profile
            </button>
            <p className="text-sm text-muted mt-2" style={{ fontSize: '0.75rem' }}>
              Opens Settings → Profile Downloaded → Install
            </p>
          </div>
        )}

        {/* Android Device */}
        {deviceType === 'android' && (
          <div className="mb-4">
            <p className="text-sm text-muted mb-3">
              We detected you're on an Android device. Scan this QR code with your camera to connect:
            </p>
            {data.qr_code && (
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <QRCode dataUrl={data.qr_code} size={180} hint="" />
              </div>
            )}
          </div>
        )}

        {/* Other Device / Show All Options */}
        {(deviceType === 'other' || showAllOptions) && (
          <div className="mb-4">
            <p className="text-sm text-muted mb-3">
              Choose how to connect this device:
            </p>
            <div className="flex flex-col gap-2">
              {data.ipsk_id && (
                <button
                  className="btn btn-secondary"
                  onClick={handleInstallProfile}
                >
                  <Apple size={18} /> Apple Profile (.mobileconfig)
                </button>
              )}
              <button
                className="btn btn-secondary"
                onClick={handleDownloadConfig}
              >
                <Download size={18} /> Download Credentials
              </button>
            </div>
          </div>
        )}

        {!showAllOptions && deviceType !== 'other' && (
          <button
            className="btn btn-ghost text-sm"
            onClick={() => setShowAllOptions(true)}
            style={{ width: '100%' }}
          >
            Show all connection options
          </button>
        )}
      </div>

      {/* QR Code for Future Devices */}
      <div className="card mb-6">
        <h3 className="mb-4" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <QrCode size={20} style={{ color: 'var(--meraki-blue)' }} />
          For Other Devices
        </h3>
        <p className="text-sm text-muted mb-4">
          Scan this QR code with any phone or tablet to connect additional devices:
        </p>
        {data.qr_code && (
          <QRCode
            dataUrl={data.qr_code}
            size={200}
            hint="Works with iPhone, Android, and most modern devices"
          />
        )}
      </div>

      {/* Email Button */}
      <div className="flex gap-4 mb-6">
        <button className="btn btn-secondary" style={{ flex: 1 }}>
          <Mail size={18} /> Email Me These Credentials
        </button>
      </div>

      {/* Help Text */}
      <div
        className="text-center p-4 text-sm"
        style={{
          background: 'var(--gray-100)',
          borderRadius: 'var(--radius-lg)',
        }}
      >
        <p className="text-muted mb-2">
          <strong>Need help connecting?</strong>
        </p>
        <p className="text-muted" style={{ marginBottom: 0 }}>
          Contact your property manager for assistance.
        </p>
      </div>
    </div>
  )
}
