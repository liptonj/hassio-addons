import { Smartphone, Tablet, Laptop, Monitor, Edit2, Trash2 } from 'lucide-react'
import type { UserDevice } from '../types/user'

interface DeviceCardProps {
  device: UserDevice
  onRename?: (deviceId: number, newName: string) => void
  onRemove?: (deviceId: number) => void
}

function getDeviceIcon(deviceType: string) {
  const type = deviceType.toLowerCase()
  if (type.includes('phone')) return Smartphone
  if (type.includes('tablet')) return Tablet
  if (type.includes('laptop')) return Laptop
  return Monitor
}

function getDeviceName(device: UserDevice): string {
  if (device.device_name) {
    return device.device_name
  }
  
  // Generate friendly name from model and OS
  if (device.device_model && device.device_model !== 'Unknown') {
    return device.device_model
  }
  
  return `${device.device_os} ${device.device_type}`
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

export default function DeviceCard({ device, onRename, onRemove }: DeviceCardProps) {
  const Icon = getDeviceIcon(device.device_type)
  const deviceName = getDeviceName(device)
  const isRecent = device.last_seen_at ? 
    (new Date().getTime() - new Date(device.last_seen_at).getTime()) < 3600000 : false

  const handleRename = () => {
    const newName = prompt('Enter a new name for this device:', deviceName)
    if (newName && newName.trim() && onRename) {
      onRename(device.id, newName.trim())
    }
  }

  const handleRemove = () => {
    if (confirm(`Are you sure you want to remove "${deviceName}"?`)) {
      if (onRemove) {
        onRemove(device.id)
      }
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-start gap-3">
        {/* Device Icon */}
        <div className={`p-3 rounded-lg flex-shrink-0 ${
          device.is_active ? 'bg-meraki-blue/10' : 'bg-gray-100 dark:bg-gray-700'
        }`}>
          <Icon 
            size={24} 
            className={device.is_active ? 'text-meraki-blue' : 'text-gray-400 dark:text-gray-500'} 
          />
        </div>

        {/* Device Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
              {deviceName}
            </h4>
            {isRecent && (
              <span className="badge badge-success text-xs flex-shrink-0">
                Active
              </span>
            )}
          </div>
          
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
            {device.device_os} {device.device_type}
          </p>
          
          <p className="text-xs text-gray-500 dark:text-gray-500 font-mono">
            MAC: {device.mac_address}
          </p>

          {device.last_seen_at && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
              Last seen: {formatDate(device.last_seen_at)}
            </p>
          )}

          {!device.last_seen_at && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
              Registered: {formatDate(device.registered_at)}
            </p>
          )}
        </div>
      </div>

      {/* Actions */}
      {(onRename || onRemove) && (
        <div className="flex gap-2 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          {onRename && (
            <button
              onClick={handleRename}
              className="btn btn-secondary btn-sm flex-1"
            >
              <Edit2 size={14} /> Rename
            </button>
          )}
          {onRemove && (
            <button
              onClick={handleRemove}
              className="btn btn-secondary btn-sm flex-1 text-error hover:bg-error-light"
            >
              <Trash2 size={14} /> Remove
            </button>
          )}
        </div>
      )}
    </div>
  )
}
