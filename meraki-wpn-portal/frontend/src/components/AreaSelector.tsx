import { useQuery } from '@tanstack/react-query'
import { getPublicAreas } from '../api/client'

interface AreaSelectorProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  error?: string
  placeholder?: string
}

export default function AreaSelector({
  value,
  onChange,
  disabled = false,
  error,
  placeholder = 'Select your unit...',
}: AreaSelectorProps) {
  const { data: areas, isLoading } = useQuery({
    queryKey: ['public-areas'],
    queryFn: getPublicAreas,
  })

  return (
    <div className="form-group">
      <label className="form-label">
        <span className="form-label-icon">
          🏠 Unit / Room
        </span>
      </label>
      <select
        className={`form-select ${error ? 'error' : ''}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || isLoading}
      >
        <option value="">{isLoading ? 'Loading...' : placeholder}</option>
        {areas?.map((area) => (
          <option key={area.area_id} value={area.area_id}>
            {area.name}
          </option>
        ))}
      </select>
      {error && <p className="form-error">{error}</p>}
    </div>
  )
}
