import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Smartphone, Search, Calendar, User, Monitor } from 'lucide-react'
import api from '../../api/client'

interface RegisteredDevice {
  id: number
  mac_address: string
  device_type: string
  device_os: string
  device_model: string
  device_name: string | null
  registered_at: string
  last_seen_at: string | null
  is_active: boolean
  user_email: string
  user_name: string | null
  user_unit: string | null
}

export default function RegisteredDevices() {
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-devices'],
    queryFn: async () => {
      const response = await api.get('/admin/devices')
      return response.data as { success: boolean; total: number; devices: RegisteredDevice[] }
    },
  })

  const filteredDevices = data?.devices.filter(device =>
    device.mac_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
    device.user_email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (device.user_name && device.user_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (device.device_name && device.device_name.toLowerCase().includes(searchTerm.toLowerCase()))
  ) || []

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-600">Loading devices...</div>
      </div>
    )
  }

  if (error) {
    const errorMessage = error instanceof Error ? error.message : 'Failed to load devices'
    const isAuthError = errorMessage.includes('Unauthorized') || errorMessage.includes('Session expired') || errorMessage.includes('Authentication required')
    
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800 font-semibold mb-2">Failed to load devices</p>
        <p className="text-red-700 text-sm">{errorMessage}</p>
        {isAuthError && (
          <p className="text-red-600 text-sm mt-2">
            Please <a href="/login" className="underline">log in</a> to continue.
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Smartphone className="text-meraki-blue" />
            Registered Devices
          </h1>
          <p className="text-gray-600 mt-1">
            {data?.total || 0} device{(data?.total || 0) !== 1 ? 's' : ''} registered
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Search by MAC address, user email, or device name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent"
          />
        </div>
      </div>

      {/* Devices Table */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Device
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  MAC Address
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Registered
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Seen
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredDevices.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    {searchTerm ? 'No devices match your search' : 'No devices registered yet'}
                  </td>
                </tr>
              ) : (
                filteredDevices.map((device) => (
                  <tr key={device.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="flex-shrink-0">
                          {device.device_type === 'mobile' || device.device_type === 'tablet' ? (
                            <Smartphone className="text-gray-400" size={20} />
                          ) : (
                            <Monitor className="text-gray-400" size={20} />
                          )}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {device.device_name || device.device_model || 'Unknown Device'}
                          </div>
                          <div className="text-xs text-gray-500">
                            {device.device_os} • {device.device_type}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <User className="text-gray-400" size={16} />
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {device.user_name || device.user_email}
                          </div>
                          {device.user_name && (
                            <div className="text-xs text-gray-500">{device.user_email}</div>
                          )}
                          {device.user_unit && (
                            <div className="text-xs text-gray-500">Unit: {device.user_unit}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-mono text-gray-900">{device.mac_address}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Calendar size={14} />
                        {new Date(device.registered_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {device.last_seen_at
                        ? new Date(device.last_seen_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
