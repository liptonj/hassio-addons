import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Palette, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface BrandingSettings {
  property_name?: string
  logo_url?: string
  primary_color?: string
}

export default function Branding() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<BrandingSettings>({
    property_name: '',
    logo_url: '',
    primary_color: '#00A4E4',
  })
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
      setFormData({
        property_name: (settings as Record<string, unknown>).property_name as string,
        logo_url: (settings as Record<string, unknown>).logo_url as string,
        primary_color: (settings as Record<string, unknown>).primary_color as string || '#00A4E4',
      })
    }
  }, [settings])

  const handleSave = () => {
    saveMutation.mutate(formData)
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Portal Branding</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Customize the appearance of your portal
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saveMutation.isPending}
        >
          <Save size={16} />
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
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

      {/* Branding Form */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <Palette size={20} className="text-meraki-blue" />
            Portal Branding
          </h3>
        </div>

        <div className="form-group">
          <label className="form-label">Property Name</label>
          <input
            type="text"
            value={formData.property_name || ''}
            onChange={(e) => setFormData({ ...formData, property_name: e.target.value })}
            className="input"
            placeholder="My Property"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            The name of your property or organization
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Logo URL</label>
          <input
            type="url"
            value={formData.logo_url || ''}
            onChange={(e) => setFormData({ ...formData, logo_url: e.target.value })}
            className="input"
            placeholder="https://example.com/logo.png"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            URL to your logo image (PNG, SVG, or JPG recommended)
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Primary Color</label>
          <div className="flex gap-3 items-center">
            <input
              type="color"
              value={formData.primary_color || '#00A4E4'}
              onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
              className="w-16 h-12 cursor-pointer border-2 border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            />
            <input
              type="text"
              value={formData.primary_color || '#00A4E4'}
              onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
              className="input flex-1"
              placeholder="#00A4E4"
              pattern="^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
            />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Primary brand color used throughout the portal
          </p>
        </div>

        {/* Preview */}
        {formData.property_name && (
          <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Preview</h4>
            <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                {formData.logo_url && (
                  <img
                    src={formData.logo_url}
                    alt={formData.property_name}
                    className="h-10 w-auto object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none'
                    }}
                  />
                )}
                <span
                  className="text-xl font-bold"
                  style={{ color: formData.primary_color }}
                >
                  {formData.property_name}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
