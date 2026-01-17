import { useLocation, Navigate } from 'react-router-dom'
import { CheckCircle, Mail } from 'lucide-react'
import { useState, useEffect } from 'react'
import QRCodeActions from '../../components/QRCodeActions'
import DeviceProvisioningPrompt from '../../components/DeviceProvisioningPrompt'
import type { RegistrationResponse } from '../../types/user'
import { grantNetworkAccess } from '../../api/client'
import { isCaptivePortal, getCaptivePortalInstructions } from '../../utils/captivePortal'

// Extended response type with splash parameters
interface SuccessState extends RegistrationResponse {
  client_mac?: string | null
  login_url?: string | null
  grant_url?: string | null
  continue_url?: string | null
}

export default function Success() {
  const location = useLocation()
  const data = location.state as SuccessState | null
  const [networkGranted, setNetworkGranted] = useState(false)
  const [grantingAccess, setGrantingAccess] = useState(false)
  const [inCaptivePortal, setInCaptivePortal] = useState(false)
  const [captivePortalInstructions, setCaptivePortalInstructions] = useState('')

  // Detect captive portal
  useEffect(() => {
    setInCaptivePortal(isCaptivePortal())
    setCaptivePortalInstructions(getCaptivePortalInstructions())
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

  const ssidName = data.ssid_name || ''
  const passphrase = data.passphrase || ''
  const qrCodeDataUrl = data.qr_code || ''
  const hasWifiCredentials = Boolean(data.ssid_name && data.passphrase && data.qr_code)

  return (
    <div className="animate-slide-up max-w-[480px] mx-auto">
      {/* Success Header */}
      <div className="text-center mb-6">
        <div className="w-20 h-20 bg-success-light dark:bg-green-900/50 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle size={48} className="text-success dark:text-green-400" />
        </div>
        <h1 className="text-[2rem] mb-2 dark:text-gray-100">
          {data.is_returning_user ? 'Welcome Back!' : 'You\'re All Set!'}
        </h1>
        <p className="text-muted dark:text-gray-400">
          {data.is_returning_user 
            ? 'Here are your credentials for this device' 
            : 'Your personal WiFi credentials are ready'}
        </p>
      </div>

      {/* Returning User Alert */}
      {data.is_returning_user && (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            We recognized your invitation code and email. You can use the same credentials on this new device.
          </p>
        </div>
      )}

      {/* Credentials Card with QR Actions */}
      <div className="card mb-6">
        <h3 className="mb-4 flex items-center gap-2 text-xl font-semibold dark:text-gray-100">
          Your WiFi Credentials
        </h3>

        {hasWifiCredentials ? (
          <QRCodeActions
            qrCodeDataUrl={qrCodeDataUrl}
            ssid={ssidName}
            passphrase={passphrase}
            ipskId={data.ipsk_id || undefined}
          />
        ) : (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            WiFi credentials are not available for this session. Please contact your property manager.
          </div>
        )}
      </div>

      {/* Device Provisioning */}
      {data.ipsk_id && hasWifiCredentials && (
        <DeviceProvisioningPrompt
          ipskId={data.ipsk_id}
          ssid={ssidName}
          passphrase={passphrase}
          mobileconfigUrl={data.mobileconfig_url || undefined}
        />
      )}

      {/* Email Button */}
      <div className="flex gap-4 my-6">
        <button className="btn btn-secondary flex-1">
          <Mail size={18} /> Email Me These Credentials
        </button>
      </div>

      {/* Captive Portal Footer */}
      {inCaptivePortal && captivePortalInstructions && (
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 text-center">
          <p className="text-sm text-blue-800 dark:text-blue-200 font-medium">
            {captivePortalInstructions}
          </p>
        </div>
      )}

      {/* Help Text */}
      <div className="text-center p-4 text-sm bg-gray-100 dark:bg-gray-800 rounded-lg">
        <p className="text-muted dark:text-gray-400 mb-2">
          <strong>Need help connecting?</strong>
        </p>
        <p className="text-muted dark:text-gray-400 mb-0">
          Contact your property manager for assistance.
        </p>
      </div>
    </div>
  )
}
