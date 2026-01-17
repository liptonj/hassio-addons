import { Smartphone } from 'lucide-react'
import type { UserDevice } from '../types/user'
import DeviceCard from './DeviceCard'

interface DeviceListProps {
  devices: UserDevice[]
  onRename?: (deviceId: number, newName: string) => void
  onRemove?: (deviceId: number) => void
  loading?: boolean
}

export default function DeviceList({ devices, onRename, onRemove, loading }: DeviceListProps) {
  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center">
          <span className="loading-spinner" />
          <span className="ml-2 text-muted">Loading devices...</span>
        </div>
      </div>
    )
  }

  if (!devices || devices.length === 0) {
    return (
      <div className="card p-6 text-center">
        <div className="inline-block p-4 bg-gray-100 rounded-full mb-4">
          <Smartphone size={32} className="text-gray-400" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          No Devices Registered
        </h3>
        <p className="text-sm text-muted">
          Register a device when you connect to the WiFi network.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {devices.map((device) => (
        <DeviceCard
          key={device.id}
          device={device}
          onRename={onRename}
          onRemove={onRemove}
        />
      ))}
    </div>
  )
}
