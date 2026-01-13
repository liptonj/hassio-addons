import { useQuery } from '@tanstack/react-query'
import { listDevices } from '../api/client'

interface DeviceSelectorProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  error?: string
}

export default function DeviceSelector({
  value,
  onChange,
  disabled = false,
  error,
}: DeviceSelectorProps) {
  const { data: devices, isLoading } = useQuery({
    queryKey: ['ha-devices'],
    queryFn: listDevices,
  })

  return (
    <div className="form-group">
      <label className="form-label">Home Assistant Device</label>
      <select
        className={`form-select ${error ? 'error' : ''}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || isLoading}
      >
        <option value="">{isLoading ? 'Loading devices...' : 'Select a device...'}</option>
        {devices?.map((device) => (
          <option key={device.id} value={device.id}>
            {device.name_by_user || device.name}
            {device.manufacturer && ` (${device.manufacturer})`}
          </option>
        ))}
      </select>
      {error && <p className="form-error">{error}</p>}
    </div>
  )
}
