import { useState } from 'react'
import { FileText, ExternalLink, X } from 'lucide-react'

interface AcceptableUseAgreementProps {
  enabled: boolean
  text?: string
  url?: string
  accepted: boolean
  onAcceptChange: (accepted: boolean) => void
  error?: string
}

export default function AcceptableUseAgreement({
  enabled,
  text,
  url,
  accepted,
  onAcceptChange,
  error,
}: AcceptableUseAgreementProps) {
  const [showModal, setShowModal] = useState(false)

  if (!enabled) {
    return null
  }

  const hasText = text && text.trim().length > 0
  const hasUrl = url && url.trim().length > 0

  return (
    <div className="form-group">
      <label className="form-label">
        <span className="form-label-icon">
          <FileText size={16} /> Acceptable Use Policy
        </span>
      </label>

      {/* Short preview if text is long */}
      {hasText && text.length > 200 && (
        <div className="mb-3">
          <div className="p-4 bg-gray-50 rounded-lg text-sm text-gray-700 border border-gray-200">
            <p className="line-clamp-3">{text}</p>
            <button
              type="button"
              onClick={() => setShowModal(true)}
              className="text-meraki-blue hover:underline mt-2 inline-flex items-center gap-1 font-medium"
            >
              Read full policy <ExternalLink size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Full text if short */}
      {hasText && text.length <= 200 && (
        <div className="mb-3">
          <div className="p-4 bg-gray-50 rounded-lg text-sm text-gray-700 border border-gray-200">
            <p className="whitespace-pre-wrap">{text}</p>
          </div>
        </div>
      )}

      {/* External URL link */}
      {hasUrl && (
        <div className="mb-3">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-meraki-blue hover:underline font-medium"
          >
            <FileText size={16} />
            View Acceptable Use Policy
            <ExternalLink size={14} />
          </a>
        </div>
      )}

      {/* Acceptance Checkbox */}
      <label className="flex items-start gap-3 cursor-pointer group">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => onAcceptChange(e.target.checked)}
          className="mt-1 w-5 h-5 text-meraki-blue border-gray-300 rounded focus:ring-meraki-blue focus:ring-2 cursor-pointer"
          style={{ minWidth: '20px', minHeight: '20px' }}
        />
        <span className="text-sm text-gray-700 select-none group-hover:text-gray-900">
          I have read and agree to the Acceptable Use Policy
          <span className="text-error ml-1">*</span>
        </span>
      </label>

      {error && <p className="form-error">{error}</p>}

      {/* Full Text Modal */}
      {showModal && hasText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h3 className="text-xl font-semibold text-gray-900">
                Acceptable Use Policy
              </h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Close"
              >
                <X size={24} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <div className="prose prose-sm max-w-none">
                <p className="whitespace-pre-wrap text-gray-700">{text}</p>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  onAcceptChange(true)
                  setShowModal(false)
                }}
                className="btn btn-primary"
              >
                I Accept
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
