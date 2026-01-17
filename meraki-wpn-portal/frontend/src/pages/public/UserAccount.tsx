import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Wifi, Lock, Smartphone, Settings, LogOut, Shield } from 'lucide-react'
import { getUserDevices, removeUserDevice, getCurrentUser, clearUserToken } from '../../api/client'
import { useNavigate } from 'react-router-dom'
import DeviceList from '../../components/DeviceList'
import ChangePasswordForm from '../../components/ChangePasswordForm'
import ChangePSKForm from '../../components/ChangePSKForm'
import { isCaptivePortal, getCaptivePortalInstructions } from '../../utils/captivePortal'

export default function UserAccount() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'wifi' | 'devices' | 'security'>('wifi')
  const inCaptivePortal = isCaptivePortal()
  const captivePortalInstructions = getCaptivePortalInstructions()

  // Fetch user info
  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUser,
  })

  // Fetch devices
  const { data: devices, isLoading: devicesLoading } = useQuery({
    queryKey: ['user-devices'],
    queryFn: getUserDevices,
    enabled: !!user,
  })

  // Remove device mutation
  const removeDeviceMutation = useMutation({
    mutationFn: (deviceId: number) => {
      const device = devices?.find(d => d.id === deviceId)
      return removeUserDevice(device?.mac_address || '')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-devices'] })
    },
  })

  const handleLogout = () => {
    clearUserToken()
    navigate('/user-auth')
  }

  if (userLoading) {
    return (
      <div className="animate-slide-up max-w-[640px] mx-auto">
        <div className="card text-center p-12">
          <span className="loading-spinner" />
          <p className="mt-4 text-muted">Loading your account...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    navigate('/user-auth')
    return null
  }

  return (
    <div className="animate-slide-up max-w-[640px] mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl">My Account</h1>
          <div className="flex items-center gap-2">
            {user.is_admin && (
              <button
                onClick={() => navigate('/admin')}
                className="btn btn-primary btn-sm"
              >
                <Shield size={16} /> Admin Portal
              </button>
            )}
            <button
              onClick={handleLogout}
              className="btn btn-ghost btn-sm"
            >
              <LogOut size={16} /> Sign Out
            </button>
          </div>
        </div>
        <p className="text-muted">
          {user.name} • {user.email}
          {user.is_admin && <span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Admin</span>}
        </p>
      </div>

      {/* Tabs */}
      <div className="card mb-6">
        <div className="flex border-b border-gray-200 -mx-6 px-6">
          <button
            onClick={() => setActiveTab('wifi')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'wifi'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <Wifi size={16} className="inline mr-2" />
            WiFi Credentials
          </button>
          <button
            onClick={() => setActiveTab('devices')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'devices'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <Smartphone size={16} className="inline mr-2" />
            Devices
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'security'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <Lock size={16} className="inline mr-2" />
            Security
          </button>
        </div>
      </div>

      {/* WiFi Tab */}
      {activeTab === 'wifi' && (
        <div className="space-y-6">
          {user.has_ipsk && user.ssid_name && user.ipsk_name ? (
            <>
              <div className="card">
                <h3 className="text-lg font-semibold mb-4">
                  Your WiFi Credentials
                </h3>
                <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">Network: <span className="font-semibold">{user.ssid_name}</span></p>
                  <p className="text-sm text-gray-600">Profile: <span className="font-semibold">{user.ipsk_name}</span></p>
                </div>
                {/* QR code would come from an endpoint */}
                <p className="text-sm text-muted">
                  Use your credentials to connect your devices to the WiFi network.
                </p>
              </div>

              <div className="card">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Settings size={20} />
                  Change WiFi Password
                </h3>
                <ChangePSKForm 
                  currentSSID={user.ssid_name}
                  onSuccess={() => {
                    queryClient.invalidateQueries({ queryKey: ['current-user'] })
                  }}
                />
              </div>
            </>
          ) : (
            <div className="card text-center p-8">
              <p className="text-muted mb-4">
                You don't have WiFi access configured yet.
              </p>
              <a href="/register" className="btn btn-primary">
                Register for WiFi Access
              </a>
            </div>
          )}
        </div>
      )}

      {/* Devices Tab */}
      {activeTab === 'devices' && (
        <div className="space-y-6">
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">
              Registered Devices
            </h3>
            <p className="text-sm text-muted mb-4">
              Manage devices registered to your account.
            </p>
            <DeviceList
              devices={devices || []}
              loading={devicesLoading}
              onRemove={(deviceId) => removeDeviceMutation.mutate(deviceId)}
            />
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          <div className="card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Lock size={20} />
              Change Account Password
            </h3>
            <p className="text-sm text-muted mb-4">
              Update your account password. This is different from your WiFi password.
            </p>
            <ChangePasswordForm />
          </div>
        </div>
      )}

      {/* Captive Portal Footer */}
      {inCaptivePortal && captivePortalInstructions && (
        <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200 text-center">
          <p className="text-sm text-blue-800 font-medium">
            {captivePortalInstructions}
          </p>
        </div>
      )}
    </div>
  )
}
