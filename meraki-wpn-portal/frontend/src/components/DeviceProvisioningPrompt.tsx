import { useEffect, useState } from 'react'
import { Apple, Smartphone, QrCode as QrCodeIcon, Download } from 'lucide-react'
import { getDeviceType, getDeviceDescription } from '../utils/deviceDetection'
import type { DeviceType } from '../utils/deviceDetection'
import QRCode from './QRCode'

interface DeviceProvisioningPromptProps {
  ipskId: string
  ssid: string
  passphrase: string
  mobileconfigUrl?: string
}

export default function DeviceProvisioningPrompt({
  ipskId,
  ssid,
  passphrase,
  mobileconfigUrl,
}: DeviceProvisioningPromptProps) {
  const [deviceType, setDeviceType] = useState<DeviceType>('other')
  const [deviceDescription, setDeviceDescription] = useState<string>('')

  useEffect(() => {
    setDeviceType(getDeviceType())
    setDeviceDescription(getDeviceDescription())
  }, [])

  const handleInstallProfile = () => {
    if (mobileconfigUrl) {
      window.location.href = mobileconfigUrl
    } else {
      // Fallback to API endpoint
      window.location.href = `/api/wifi-config/${ipskId}/mobileconfig`
    }
  }

  // iOS/macOS device with profile support
  if (deviceType === 'ios' || deviceType === 'macos') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <Apple size={24} className="text-blue-600 flex-shrink-0" />
          <div>
            <p className="font-semibold text-blue-900">Apple Device Detected</p>
            <p className="text-sm text-blue-700">
              {deviceDescription}
            </p>
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Download size={20} className="text-meraki-blue" />
            Install WiFi Profile
          </h3>
          <p className="text-sm text-muted mb-4">
            Download and install the WiFi profile to automatically configure your device.
          </p>
          <button
            onClick={handleInstallProfile}
            className="btn btn-primary w-full"
          >
            <Apple size={18} /> Download WiFi Profile
          </button>
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600 font-semibold mb-2">Installation Steps:</p>
            <ol className="text-xs text-gray-600 space-y-1 list-decimal list-inside">
              {deviceType === 'ios' ? (
                <>
                  <li>Tap the button above to download the profile</li>
                  <li>Go to Settings → General → VPN & Device Management</li>
                  <li>Tap the downloaded profile and select "Install"</li>
                  <li>Enter your device passcode if prompted</li>
                  <li>Tap "Install" to confirm</li>
                </>
              ) : (
                <>
                  <li>Click the button above to download the profile</li>
                  <li>Open System Preferences → Profiles</li>
                  <li>Double-click the downloaded profile</li>
                  <li>Click "Install" and enter your password</li>
                </>
              )}
            </ol>
          </div>
        </div>
      </div>
    )
  }

  // Android device with QR code
  if (deviceType === 'android') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-200">
          <Smartphone size={24} className="text-green-600 flex-shrink-0" />
          <div>
            <p className="font-semibold text-green-900">Android Device Detected</p>
            <p className="text-sm text-green-700">
              {deviceDescription}
            </p>
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <QrCodeIcon size={20} className="text-meraki-blue" />
            Scan QR Code
          </h3>
          <p className="text-sm text-muted mb-4">
            Open your camera app and point it at the QR code below to connect automatically.
          </p>
          <div className="flex justify-center mb-4">
            <QRCode
              dataUrl={`data:image/svg+xml;base64,${btoa(`<svg xmlns="http://www.w3.org/2000/svg"></svg>`)}`}
              size={180}
              hint=""
            />
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600 font-semibold mb-2">Connection Steps:</p>
            <ol className="text-xs text-gray-600 space-y-1 list-decimal list-inside">
              <li>Open your Camera app</li>
              <li>Point it at the QR code above</li>
              <li>Tap the WiFi notification that appears</li>
              <li>Confirm to connect to the network</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  // Other devices - show generic instructions
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        <Smartphone size={20} className="text-meraki-blue" />
        Connect This Device
      </h3>
      <p className="text-sm text-muted mb-4">
        {deviceDescription ? `Device: ${deviceDescription}` : 'Use the QR code or manual connection.'}
      </p>

      <div className="space-y-4">
        <div>
          <p className="font-semibold mb-2">Option 1: Manual Connection</p>
          <ol className="text-sm text-gray-600 space-y-1 list-decimal list-inside ml-2">
            <li>Open WiFi settings on your device</li>
            <li>Select network: <span className="font-mono font-semibold">{ssid}</span></li>
            <li>Enter password: <span className="font-mono font-semibold">{passphrase}</span></li>
            <li>Tap Connect</li>
          </ol>
        </div>

        <div>
          <p className="font-semibold mb-2">Option 2: QR Code (Mobile Devices)</p>
          <p className="text-sm text-gray-600 mb-2">
            Scan the QR code shown earlier with your mobile device's camera to connect automatically.
          </p>
        </div>
      </div>
    </div>
  )
}
