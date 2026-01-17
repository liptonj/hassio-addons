import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Filter, Trash2, Ban, Eye, Building2, Tv, User, Shield } from 'lucide-react'
import {
  listIPSKs,
  createIPSK,
  deleteIPSK,
  revokeIPSK,
  revealIPSKPassphrase,
  getIPSKOptions,
} from '../../api/client'
import type { IPSK, IPSKCreate } from '../../types/ipsk'

export default function IPSKManager() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [revealedPassphrases, setRevealedPassphrases] = useState<Record<string, string>>({})

  const { data: ipsks, isLoading } = useQuery({
    queryKey: ['ipsks', statusFilter],
    queryFn: () => listIPSKs(statusFilter ? { status: statusFilter } : undefined),
  })

  const createMutation = useMutation({
    mutationFn: createIPSK,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
      setShowCreateModal(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteIPSK,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: revokeIPSK,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
    },
  })

  const handleReveal = async (ipskId: string) => {
    if (revealedPassphrases[ipskId]) {
      setRevealedPassphrases((prev) => {
        const next = { ...prev }
        delete next[ipskId]
        return next
      })
      return
    }

    try {
      const result = await revealIPSKPassphrase(ipskId)
      setRevealedPassphrases((prev) => ({
        ...prev,
        [ipskId]: result.passphrase,
      }))
    } catch (error) {
      console.error('Failed to reveal passphrase:', error)
    }
  }

  const filteredIPSKs = ipsks?.filter((ipsk) =>
    ipsk.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    ipsk.associated_unit?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    ipsk.associated_user?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <span className="badge badge-success">Active</span>
      case 'expired':
        return <span className="badge badge-warning">Expired</span>
      case 'revoked':
        return <span className="badge badge-error">Revoked</span>
      default:
        return <span className="badge badge-gray">{status}</span>
    }
  }

  const getAssociation = (ipsk: IPSK) => {
    if (ipsk.associated_device_name) {
      return (
        <span className="flex items-center gap-1 text-sm text-muted">
          <Tv size={14} /> {ipsk.associated_device_name}
        </span>
      )
    }
    if (ipsk.associated_area_name || ipsk.associated_unit) {
      return (
        <span className="flex items-center gap-1 text-sm text-muted">
          <Building2 size={14} /> {ipsk.associated_area_name || `Unit ${ipsk.associated_unit}`}
        </span>
      )
    }
    if (ipsk.associated_user) {
      return (
        <span className="flex items-center gap-1 text-sm text-muted">
          <User size={14} /> {ipsk.associated_user}
        </span>
      )
    }
    return <span className="text-sm text-muted">—</span>
  }

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1>IPSK Management</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          <Plus size={18} /> Create IPSK
        </button>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex gap-4 flex-wrap">
          <div className="flex items-center gap-2" style={{ flex: 1, minWidth: '200px' }}>
            <Search size={18} className="text-muted" />
            <input
              type="text"
              className="form-input"
              placeholder="Search by name, unit, or user..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ marginBottom: 0 }}
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter size={18} className="text-muted" />
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ marginBottom: 0, width: 'auto' }}
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="revoked">Revoked</option>
            </select>
          </div>
        </div>
      </div>

      {/* IPSK Table */}
      {isLoading ? (
        <div className="flex items-center justify-center p-8">
          <span className="loading-spinner" style={{ width: '32px', height: '32px' }} />
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>WPN/UPN ID</th>
                <th>Group Policy</th>
                <th>Association</th>
                <th>SSID</th>
                <th>Status</th>
                <th>Connected</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredIPSKs?.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center text-muted p-8">
                    No IPSKs found
                  </td>
                </tr>
              ) : (
                filteredIPSKs?.map((ipsk) => (
                  <tr key={ipsk.id}>
                    <td>
                      <div className="font-medium">{ipsk.name}</div>
                      {revealedPassphrases[ipsk.id] && (
                        <code className="text-sm" style={{ color: 'var(--meraki-blue)' }}>
                          {revealedPassphrases[ipsk.id]}
                        </code>
                      )}
                    </td>
                    <td>
                      {(ipsk.psk_group_id || ipsk.pskGroupId) ? (
                        <code className="text-sm" style={{ 
                          background: 'var(--bg-secondary)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontFamily: 'monospace'
                        }}>
                          {ipsk.psk_group_id || ipsk.pskGroupId}
                        </code>
                      ) : (
                        <span className="text-muted text-sm">—</span>
                      )}
                    </td>
                    <td>
                      {ipsk.group_policy_name ? (
                        <span className="flex items-center gap-1 text-sm">
                          <Shield size={14} className="text-meraki-blue" />
                          {ipsk.group_policy_name}
                        </span>
                      ) : ipsk.group_policy_id ? (
                        <span className="text-sm text-muted">ID: {ipsk.group_policy_id}</span>
                      ) : (
                        <span className="text-muted text-sm">—</span>
                      )}
                    </td>
                    <td>{getAssociation(ipsk)}</td>
                    <td className="text-sm">{ipsk.ssid_name || `SSID ${ipsk.ssid_number}`}</td>
                    <td>{getStatusBadge(ipsk.status)}</td>
                    <td>
                      {ipsk.connected_clients !== undefined && ipsk.connected_clients > 0 ? (
                        <span className="badge badge-info">{ipsk.connected_clients}</span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          className="btn btn-icon btn-ghost"
                          title="Reveal passphrase"
                          onClick={() => handleReveal(ipsk.id)}
                        >
                          <Eye size={16} />
                        </button>
                        {ipsk.status === 'active' && (
                          <button
                            className="btn btn-icon btn-ghost"
                            title="Revoke"
                            onClick={() => {
                              if (confirm(`Revoke IPSK "${ipsk.name}"?`)) {
                                revokeMutation.mutate(ipsk.id)
                              }
                            }}
                          >
                            <Ban size={16} />
                          </button>
                        )}
                        <button
                          className="btn btn-icon btn-ghost"
                          title="Delete"
                          style={{ color: 'var(--error)' }}
                          onClick={() => {
                            if (confirm(`Delete IPSK "${ipsk.name}"? This cannot be undone.`)) {
                              deleteMutation.mutate(ipsk.id)
                            }
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateIPSKModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}
    </div>
  )
}

function CreateIPSKModal({
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  onClose: () => void
  onSubmit: (data: IPSKCreate) => void
  isLoading: boolean
  error?: string
}) {
  const [formData, setFormData] = useState<IPSKCreate>({
    name: '',
    passphrase: '',
    duration_hours: 0,
    group_policy_id: '',
    associated_unit: '',
    associated_user: '',
  })

  // Fetch available group policies
  const { data: ipskOptions } = useQuery({
    queryKey: ['ipsk-options'],
    queryFn: getIPSKOptions,
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
        style={{ maxWidth: '480px', width: '100%', margin: '2rem' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4">Create New IPSK</h2>

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
            <label className="form-label">IPSK Name *</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., Unit-201-John"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Passphrase
              <span className="text-muted" style={{ fontWeight: 'normal' }}>
                {' '}(leave blank to auto-generate)
              </span>
            </label>
            <input
              type="text"
              className="form-input"
              placeholder="Auto-generated if empty"
              value={formData.passphrase}
              onChange={(e) => setFormData({ ...formData, passphrase: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <Shield size={16} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
              Group Policy
            </label>
            <select
              className="form-select"
              value={formData.group_policy_id || ''}
              onChange={(e) => setFormData({ ...formData, group_policy_id: e.target.value || undefined })}
            >
              <option value="">Use default policy</option>
              {ipskOptions?.group_policies?.map((policy) => (
                <option key={policy.id} value={policy.id}>
                  {policy.name}
                </option>
              ))}
            </select>
            <p className="text-sm text-muted mt-1">
              Group policy determines splash page bypass and network access rules
            </p>
          </div>

          <div className="form-group">
            <label className="form-label">Duration (hours)</label>
            <input
              type="number"
              className="form-input"
              placeholder="0 = permanent"
              value={formData.duration_hours || ''}
              onChange={(e) =>
                setFormData({ ...formData, duration_hours: parseInt(e.target.value) || 0 })
              }
              min={0}
            />
            <p className="text-sm text-muted mt-1">0 = permanent (no expiration)</p>
          </div>

          <div className="form-group">
            <label className="form-label">Associated Unit</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., 201"
              value={formData.associated_unit}
              onChange={(e) => setFormData({ ...formData, associated_unit: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Associated User</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., John Smith"
              value={formData.associated_user}
              onChange={(e) => setFormData({ ...formData, associated_user: e.target.value })}
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
              disabled={isLoading || !formData.name}
              style={{ flex: 1 }}
            >
              {isLoading ? (
                <>
                  <span className="loading-spinner" /> Creating...
                </>
              ) : (
                'Create IPSK'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
