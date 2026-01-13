import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Copy, Check, Clock, AlertCircle } from 'lucide-react'
import { listInviteCodes, createInviteCode, deleteInviteCode } from '../../api/client'
import type { InviteCodeCreate } from '../../types/device'

export default function InviteCodes() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [copiedCode, setCopiedCode] = useState<string | null>(null)
  const [showExpired, setShowExpired] = useState(false)

  const { data: codes, isLoading } = useQuery({
    queryKey: ['invite-codes', showExpired],
    queryFn: () => listInviteCodes({ include_expired: showExpired }),
  })

  const createMutation = useMutation({
    mutationFn: createInviteCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      setShowCreateModal(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteInviteCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
    },
  })

  const handleCopy = async (code: string) => {
    await navigator.clipboard.writeText(code)
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const isExpired = (expiresAt?: string) => {
    if (!expiresAt) return false
    return new Date(expiresAt) < new Date()
  }

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1>Invite Codes</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          <Plus size={18} /> Generate Code
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showExpired}
            onChange={(e) => setShowExpired(e.target.checked)}
          />
          Show expired codes
        </label>
      </div>

      {/* Codes Table */}
      {isLoading ? (
        <div className="flex items-center justify-center p-8">
          <span className="loading-spinner" style={{ width: '32px', height: '32px' }} />
        </div>
      ) : codes?.length === 0 ? (
        <div className="card text-center p-8">
          <AlertCircle size={48} className="text-muted" style={{ margin: '0 auto 1rem' }} />
          <h3>No Invite Codes</h3>
          <p className="text-muted">Generate codes to allow controlled access to WiFi registration.</p>
          <button
            className="btn btn-primary mt-4"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={18} /> Generate First Code
          </button>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Usage</th>
                <th>Expires</th>
                <th>Note</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {codes?.map((code) => (
                <tr key={code.code} style={{ opacity: !code.is_active ? 0.5 : 1 }}>
                  <td>
                    <div className="flex items-center gap-2">
                      <code
                        className="font-medium"
                        style={{
                          background: 'var(--gray-100)',
                          padding: '0.25rem 0.5rem',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.875rem',
                        }}
                      >
                        {code.code}
                      </code>
                      <button
                        className="btn btn-icon btn-ghost"
                        onClick={() => handleCopy(code.code)}
                        title="Copy code"
                      >
                        {copiedCode === code.code ? (
                          <Check size={14} color="var(--success)" />
                        ) : (
                          <Copy size={14} />
                        )}
                      </button>
                    </div>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        code.uses >= code.max_uses ? 'badge-error' : 'badge-info'
                      }`}
                    >
                      {code.uses} / {code.max_uses}
                    </span>
                  </td>
                  <td>
                    {code.expires_at ? (
                      <span
                        className={`flex items-center gap-1 text-sm ${
                          isExpired(code.expires_at) ? 'text-error' : 'text-muted'
                        }`}
                      >
                        <Clock size={14} />
                        {formatDate(code.expires_at)}
                      </span>
                    ) : (
                      <span className="text-sm text-muted">Never</span>
                    )}
                  </td>
                  <td className="text-sm text-muted">{code.note || '—'}</td>
                  <td className="text-sm text-muted">{formatDate(code.created_at)}</td>
                  <td>
                    <button
                      className="btn btn-icon btn-ghost"
                      title="Delete code"
                      style={{ color: 'var(--error)' }}
                      onClick={() => {
                        if (confirm(`Delete invite code "${code.code}"?`)) {
                          deleteMutation.mutate(code.code)
                        }
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateCodeModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}
    </div>
  )
}

function CreateCodeModal({
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  onClose: () => void
  onSubmit: (data: InviteCodeCreate) => void
  isLoading: boolean
  error?: string
}) {
  const [formData, setFormData] = useState<InviteCodeCreate>({
    max_uses: 1,
    expires_in_hours: undefined,
    note: '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <div
      className="loading-overlay"
      onClick={onClose}
      style={{ background: 'rgba(0, 0, 0, 0.5)' }}
    >
      <div
        className="card animate-slide-up"
        style={{ maxWidth: '400px', width: '100%', margin: '2rem' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4">Generate Invite Code</h2>

        {error && (
          <div
            className="mb-4 p-4"
            style={{
              background: 'var(--error-light)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--error)',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Maximum Uses</label>
            <input
              type="number"
              className="form-input"
              value={formData.max_uses}
              onChange={(e) =>
                setFormData({ ...formData, max_uses: parseInt(e.target.value) || 1 })
              }
              min={1}
              max={1000}
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Expires In (hours)
              <span className="text-muted" style={{ fontWeight: 'normal' }}>
                {' '}(leave blank for no expiration)
              </span>
            </label>
            <input
              type="number"
              className="form-input"
              placeholder="e.g., 168 for 1 week"
              value={formData.expires_in_hours || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  expires_in_hours: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              min={1}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Note (optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., For new tenants in Building A"
              value={formData.note}
              onChange={(e) => setFormData({ ...formData, note: e.target.value })}
            />
          </div>

          <div className="flex gap-4 mt-6">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={isLoading}
              style={{ flex: 1 }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
              style={{ flex: 1 }}
            >
              {isLoading ? (
                <>
                  <span className="loading-spinner" /> Generating...
                </>
              ) : (
                'Generate Code'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
