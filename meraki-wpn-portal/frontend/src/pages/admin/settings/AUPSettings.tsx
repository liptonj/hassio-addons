import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, FileText, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { getAllSettings, updateSettings } from '../../../api/client'

interface AUPSettings {
  aup_enabled?: boolean
  aup_text?: string
  aup_url?: string
  aup_version?: number
}

export default function AUPSettings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<AUPSettings>({
    aup_enabled: false,
    aup_text: '',
    aup_url: '',
    aup_version: 1,
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
      const data = settings as Record<string, unknown>
      setFormData({
        aup_enabled: data.aup_enabled as boolean,
        aup_text: data.aup_text as string,
        aup_url: data.aup_url as string,
        aup_version: data.aup_version as number,
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Acceptable Use Policy</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure terms of service and acceptable use policy
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

      {/* AUP Configuration */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title flex items-center gap-2">
            <FileText size={20} className="text-meraki-blue" />
            AUP Configuration
          </h3>
        </div>

        <div className="form-group">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.aup_enabled ?? false}
              onChange={(e) => setFormData({ ...formData, aup_enabled: e.target.checked })}
              className="w-5 h-5 text-meraki-blue border-gray-300 dark:border-gray-600 rounded focus:ring-meraki-blue dark:bg-gray-700"
            />
            <span className="form-label mb-0">Enable Acceptable Use Policy</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-7">
            Require users to accept AUP before accessing WiFi
          </p>
        </div>

        {formData.aup_enabled && (
          <>
            <div className="form-group">
              <label className="form-label">AUP Text</label>
              <textarea
                value={formData.aup_text || ''}
                onChange={(e) => setFormData({ ...formData, aup_text: e.target.value })}
                className="input min-h-[200px]"
                placeholder="Enter your acceptable use policy text here..."
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                The full text of your acceptable use policy that users must read and accept
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">AUP URL (optional)</label>
              <input
                type="url"
                value={formData.aup_url || ''}
                onChange={(e) => setFormData({ ...formData, aup_url: e.target.value })}
                className="input"
                placeholder="https://example.com/aup"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Link to external AUP document (optional, displayed alongside the text)
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">AUP Version</label>
              <input
                type="number"
                value={formData.aup_version ?? 1}
                onChange={(e) => setFormData({ ...formData, aup_version: parseInt(e.target.value, 10) })}
                className="input"
                min="1"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Version number (increment when you update the AUP to require users to re-accept)
              </p>
            </div>
          </>
        )}
      </div>

      {/* Preview */}
      {formData.aup_enabled && formData.aup_text && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Preview</h3>
          </div>
          <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="prose dark:prose-invert max-w-none">
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {formData.aup_text}
              </p>
              {formData.aup_url && (
                <p className="text-sm mt-4">
                  <a
                    href={formData.aup_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-meraki-blue hover:underline"
                  >
                    View full policy document →
                  </a>
                </p>
              )}
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="w-4 h-4 text-meraki-blue border-gray-300 dark:border-gray-600 rounded"
                  disabled
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  I have read and agree to the Acceptable Use Policy (v{formData.aup_version ?? 1})
                </span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Help */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">About AUP</h4>
        <div className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
          <p>
            <strong>Why use an AUP?</strong> Acceptable Use Policies help establish clear guidelines for network usage and protect your organization from liability.
          </p>
          <p>
            <strong>Version tracking:</strong> When you update your AUP, increment the version number. Users who previously accepted will be prompted to accept the new version.
          </p>
          <p>
            <strong>External URL:</strong> Use this to link to a detailed policy document hosted elsewhere, while keeping a short summary in the text field.
          </p>
        </div>
      </div>
    </div>
  )
}
