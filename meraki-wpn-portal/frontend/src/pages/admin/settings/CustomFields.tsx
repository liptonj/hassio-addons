import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Settings, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface CustomFieldsSettings {
  custom_registration_fields?: string
}

export default function CustomFields() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<CustomFieldsSettings>({
    custom_registration_fields: '[]',
  })
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings-all'],
    queryFn: getAllSettings,
  })

  const saveMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      setNotification({
        type: data.requires_restart ? 'warning' : 'success',
        message: data.message,
      })
      queryClient.invalidateQueries({ queryKey: ['settings-all'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to save settings',
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  useEffect(() => {
    if (settings) {
      const data = settings as Record<string, unknown>
      const fields = data.custom_registration_fields as string
      setFormData({
        custom_registration_fields: fields || '[]',
      })
    }
  }, [settings])

  const handleChange = (value: string) => {
    setFormData({ custom_registration_fields: value })
    // Validate JSON in real-time
    if (value.trim()) {
      try {
        JSON.parse(value)
        setJsonError(null)
      } catch (error) {
        setJsonError((error as Error).message)
      }
    } else {
      setJsonError(null)
    }
  }

  const handleSave = () => {
    // Validate JSON before saving
    if (formData.custom_registration_fields?.trim()) {
      try {
        JSON.parse(formData.custom_registration_fields)
      } catch (error) {
        setNotification({
          type: 'error',
          message: 'Custom registration fields must be valid JSON',
        })
        return
      }
    }
    saveMutation.mutate(formData)
  }

  const formatJSON = () => {
    try {
      const parsed = JSON.parse(formData.custom_registration_fields || '[]')
      const formatted = JSON.stringify(parsed, null, 2)
      setFormData({ custom_registration_fields: formatted })
      setJsonError(null)
    } catch (error) {
      setNotification({
        type: 'error',
        message: 'Cannot format invalid JSON',
      })
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Custom Registration Fields</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Add custom fields to the user registration form
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn btn-secondary"
            onClick={formatJSON}
          >
            Format JSON
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saveMutation.isPending || !!jsonError}
          >
            <Save size={16} />
            {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
              : notification.type === 'warning'
              ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
          }`}
        >
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <XCircle size={20} />}
          {notification.message}
        </div>
      )}

      {/* JSON Editor */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Settings size={20} className="text-meraki-blue" />
            Field Configuration (JSON)
          </h3>
        </div>

        <div className="form-group">
          <label className="form-label">Custom Fields JSON</label>
          <textarea
            value={formData.custom_registration_fields || '[]'}
            onChange={(e) => handleChange(e.target.value)}
            className={`input font-mono text-sm min-h-[300px] ${jsonError ? 'border-red-500 dark:border-red-700' : ''}`}
            placeholder='[{"id":"unit_number","label":"Unit Number","type":"text","required":true}]'
          />
          {jsonError && (
            <p className="form-error">{jsonError}</p>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Define custom fields as a JSON array. Click "Format JSON" to prettify.
          </p>
        </div>
      </div>

      {/* Documentation */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Field Types &amp; Options</h3>
        </div>

        <div className="space-y-4 text-sm">
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Supported Field Types:</h4>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">text</code> - Single line text input</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">number</code> - Numeric input</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">email</code> - Email address input</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">select</code> - Dropdown selection (requires <code className="font-mono">options</code> array)</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">tel</code> - Phone number input</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">textarea</code> - Multi-line text input</li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Required Properties:</h4>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">id</code> - Unique field identifier</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">label</code> - Display label for the field</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">type</code> - Field type (see above)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Optional Properties:</h4>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">required</code> - Boolean, whether the field is required</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">placeholder</code> - Placeholder text</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">options</code> - Array of options for <code className="font-mono">select</code> type</li>
              <li><code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">min</code> / <code className="font-mono">max</code> - Min/max values for <code className="font-mono">number</code> type</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Examples */}
      <div className="card bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700">
        <div className="card-header">
          <h3 className="card-title">Example Configuration</h3>
        </div>

        <pre className="text-xs font-mono text-gray-800 dark:text-gray-200 overflow-x-auto p-4 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
{`[
  {
    "id": "unit_number",
    "label": "Unit Number",
    "type": "text",
    "required": true,
    "placeholder": "e.g., 101"
  },
  {
    "id": "building",
    "label": "Building",
    "type": "select",
    "required": true,
    "options": ["North Tower", "South Tower", "East Wing"]
  },
  {
    "id": "parking_spot",
    "label": "Parking Spot Number",
    "type": "number",
    "required": false,
    "min": 1,
    "max": 500
  },
  {
    "id": "emergency_contact",
    "label": "Emergency Contact Phone",
    "type": "tel",
    "required": false,
    "placeholder": "+1 (555) 555-5555"
  }
]`}
        </pre>
      </div>
    </div>
  )
}
