import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X,
  User,
  Key,
  Smartphone,
  Shield,
  Save,
  RefreshCw,
  Eye,
  EyeOff,
} from 'lucide-react'
import {
  getAdminUserDevices,
  updateUserIpsk,
  resetUserPassword,
  updateUser,
  type AdminUserInfo,
  type DeviceInfo,
} from '../api/client'

interface UserEditDialogProps {
  user: AdminUserInfo
  onClose: () => void
  onSave: () => void
}

type TabType = 'profile' | 'ipsk' | 'devices' | 'security'

export default function UserEditDialog({ user, onClose, onSave }: UserEditDialogProps) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('profile')
  const [notification, setNotification] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    name: user.name,
    unit: user.unit || '',
    is_admin: user.is_admin,
  })

  // IPSK form state
  const [ipskForm, setIpskForm] = useState({
    newPassphrase: '',
    confirmPassphrase: '',
  })
  const [showIpskPassphrase, setShowIpskPassphrase] = useState(false)

  // Security form state
  const [securityForm, setSecurityForm] = useState({
    newPassword: '',
    confirmPassword: '',
  })
  const [showPassword, setShowPassword] = useState(false)

  // Fetch user devices
  const { data: devicesData, isLoading: devicesLoading } = useQuery({
    queryKey: ['user-devices', user.id],
    queryFn: () => getAdminUserDevices(user.id),
    enabled: activeTab === 'devices',
  })

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: () => updateUser(user.id, profileForm),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Profile updated successfully' })
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setTimeout(() => {
        onSave()
      }, 1000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message })
    },
  })

  // Update IPSK mutation
  const updateIpskMutation = useMutation({
    mutationFn: () => updateUserIpsk(user.id, ipskForm.newPassphrase),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'IPSK passphrase updated successfully' })
      setIpskForm({ newPassphrase: '', confirmPassphrase: '' })
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message })
    },
  })

  // Reset password mutation
  const resetPasswordMutation = useMutation({
    mutationFn: () => resetUserPassword(user.id, securityForm.newPassword),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Password reset successfully' })
      setSecurityForm({ newPassword: '', confirmPassword: '' })
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message })
    },
  })

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateProfileMutation.mutate()
  }

  const handleIpskSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (ipskForm.newPassphrase !== ipskForm.confirmPassphrase) {
      setNotification({ type: 'error', message: 'Passphrases do not match' })
      return
    }
    if (ipskForm.newPassphrase.length < 8) {
      setNotification({ type: 'error', message: 'Passphrase must be at least 8 characters' })
      return
    }
    updateIpskMutation.mutate()
  }

  const handleSecuritySubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (securityForm.newPassword !== securityForm.confirmPassword) {
      setNotification({ type: 'error', message: 'Passwords do not match' })
      return
    }
    if (securityForm.newPassword.length < 8) {
      setNotification({ type: 'error', message: 'Password must be at least 8 characters' })
      return
    }
    resetPasswordMutation.mutate()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Edit User</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{user.email}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Notification */}
        {notification && (
          <div
            className={`mx-6 mt-4 p-3 rounded-lg ${
              notification.type === 'success'
                ? 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                : 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
            }`}
          >
            {notification.message}
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 px-6">
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'profile'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            <User size={16} />
            Profile
          </button>
          {user.has_ipsk && (
            <button
              onClick={() => setActiveTab('ipsk')}
              className={`px-4 py-3 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'ipsk'
                  ? 'border-meraki-blue text-meraki-blue'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Key size={16} />
              IPSK
            </button>
          )}
          <button
            onClick={() => setActiveTab('devices')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'devices'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            <Smartphone size={16} />
            Devices
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'security'
                ? 'border-meraki-blue text-meraki-blue'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            <Shield size={16} />
            Security
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Unit
                </label>
                <input
                  type="text"
                  value={profileForm.unit}
                  onChange={(e) => setProfileForm({ ...profileForm, unit: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                  placeholder="e.g., Apt 101"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={profileForm.is_admin}
                  onChange={(e) => setProfileForm({ ...profileForm, is_admin: e.target.checked })}
                  className="w-4 h-4 text-meraki-blue focus:ring-meraki-blue border-gray-300 rounded"
                />
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Admin privileges
                </label>
              </div>
              <button
                type="submit"
                disabled={updateProfileMutation.isPending}
                className="w-full btn btn-primary flex items-center justify-center gap-2"
              >
                {updateProfileMutation.isPending ? (
                  <RefreshCw className="animate-spin" size={16} />
                ) : (
                  <Save size={16} />
                )}
                Save Changes
              </button>
            </form>
          )}

          {/* IPSK Tab */}
          {activeTab === 'ipsk' && user.has_ipsk && (
            <div className="space-y-4">
              <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-1">
                  Current IPSK: {user.ipsk_name || 'Unknown'}
                </h4>
                <p className="text-sm text-blue-700 dark:text-blue-400">
                  SSID: {user.ssid_name || 'Not configured'}
                </p>
              </div>
              <form onSubmit={handleIpskSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    New Passphrase
                  </label>
                  <div className="relative">
                    <input
                      type={showIpskPassphrase ? 'text' : 'password'}
                      value={ipskForm.newPassphrase}
                      onChange={(e) =>
                        setIpskForm({ ...ipskForm, newPassphrase: e.target.value })
                      }
                      className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                      placeholder="Minimum 8 characters"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowIpskPassphrase(!showIpskPassphrase)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showIpskPassphrase ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Confirm Passphrase
                  </label>
                  <input
                    type={showIpskPassphrase ? 'text' : 'password'}
                    value={ipskForm.confirmPassphrase}
                    onChange={(e) =>
                      setIpskForm({ ...ipskForm, confirmPassphrase: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                    placeholder="Re-enter passphrase"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={updateIpskMutation.isPending}
                  className="w-full btn btn-primary flex items-center justify-center gap-2"
                >
                  {updateIpskMutation.isPending ? (
                    <RefreshCw className="animate-spin" size={16} />
                  ) : (
                    <Key size={16} />
                  )}
                  Update IPSK Passphrase
                </button>
              </form>
            </div>
          )}

          {/* Devices Tab */}
          {activeTab === 'devices' && (
            <div>
              {devicesLoading ? (
                <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                  Loading devices...
                </div>
              ) : devicesData && devicesData.devices.length > 0 ? (
                <div className="space-y-3">
                  {devicesData.devices.map((device: DeviceInfo) => (
                    <div
                      key={device.id}
                      className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900 dark:text-white">
                            {device.device_name || device.device_model || 'Unknown Device'}
                          </h4>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            {device.device_os} • {device.device_type}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-500 font-mono mt-1">
                            {device.mac_address}
                          </p>
                        </div>
                        <div className="text-right text-sm text-gray-500 dark:text-gray-400">
                          <p>Registered: {new Date(device.registered_at).toLocaleDateString()}</p>
                          {device.last_seen_at && (
                            <p>Last seen: {new Date(device.last_seen_at).toLocaleDateString()}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                  No devices registered
                </div>
              )}
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <form onSubmit={handleSecuritySubmit} className="space-y-4">
              <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <p className="text-sm text-yellow-800 dark:text-yellow-300">
                  This will reset the user's account password. They will need to use the new
                  password to log in.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={securityForm.newPassword}
                    onChange={(e) =>
                      setSecurityForm({ ...securityForm, newPassword: e.target.value })
                    }
                    className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                    placeholder="Minimum 8 characters"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Confirm Password
                </label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={securityForm.confirmPassword}
                  onChange={(e) =>
                    setSecurityForm({ ...securityForm, confirmPassword: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                  placeholder="Re-enter password"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={resetPasswordMutation.isPending}
                className="w-full btn btn-primary flex items-center justify-center gap-2"
              >
                {resetPasswordMutation.isPending ? (
                  <RefreshCw className="animate-spin" size={16} />
                ) : (
                  <Shield size={16} />
                )}
                Reset Password
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
