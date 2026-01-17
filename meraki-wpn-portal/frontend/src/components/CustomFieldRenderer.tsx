import { Settings } from 'lucide-react'
import type { CustomField } from '../types/user'

interface CustomFieldRendererProps {
  fields: CustomField[]
  values: Record<string, string>
  onChange: (fieldId: string, value: string) => void
  errors: Record<string, string>
}

export default function CustomFieldRenderer({
  fields,
  values,
  onChange,
  errors,
}: CustomFieldRendererProps) {
  if (!fields || fields.length === 0) {
    return null
  }

  return (
    <div className="form-group">
      <label className="form-label mb-4">
        <span className="form-label-icon">
          <Settings size={16} /> Additional Information
        </span>
      </label>

      <div className="space-y-4">
        {fields.map((field) => (
          <div key={field.id} className="form-group">
            <label className="form-label">
              {field.label}
              {field.required && <span className="text-error ml-1">*</span>}
            </label>

            {/* Text input */}
            {field.type === 'text' && (
              <input
                type="text"
                className={`form-input ${errors[field.id] ? 'error' : ''}`}
                value={values[field.id] || ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                placeholder={`Enter ${field.label.toLowerCase()}`}
                required={field.required}
              />
            )}

            {/* Number input */}
            {field.type === 'number' && (
              <input
                type="number"
                className={`form-input ${errors[field.id] ? 'error' : ''}`}
                value={values[field.id] || ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                placeholder={`Enter ${field.label.toLowerCase()}`}
                required={field.required}
              />
            )}

            {/* Select dropdown */}
            {field.type === 'select' && (
              <select
                className={`form-select ${errors[field.id] ? 'error' : ''}`}
                value={values[field.id] || ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                required={field.required}
              >
                <option value="">Select {field.label.toLowerCase()}...</option>
                {field.options?.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            )}

            {/* Error message */}
            {errors[field.id] && (
              <p className="form-error">{errors[field.id]}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
