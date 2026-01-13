import { useState } from 'react'
import { Eye, EyeOff, Trash2, Ban, Copy, Check, Building2, Tv, User } from 'lucide-react'
import type { IPSK } from '../types/ipsk'

interface IPSKCardProps {
  ipsk: IPSK
  onReveal?: (id: string) => Promise<{ passphrase: string; qr_code?: string }>
  onRevoke?: (id: string) => void
  onDelete?: (id: string) => void
}

export default function IPSKCard({ ipsk, onReveal, onRevoke, onDelete }: IPSKCardProps) {
  const [showPassphrase, setShowPassphrase] = useState(false)
  const [passphrase, setPassphrase] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleReveal = async () => {
    if (showPassphrase) {
      setShowPassphrase(false)
      return
    }

    if (passphrase) {
      setShowPassphrase(true)
      return
    }

    if (!onReveal) return

    setLoading(true)
    try {
      const result = await onReveal(ipsk.id)
      setPassphrase(result.passphrase)
      setShowPassphrase(true)
    } catch (error) {
      console.error('Failed to reveal passphrase:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!passphrase) return
    await navigator.clipboard.writeText(passphrase)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const getStatusBadge = () => {
    switch (ipsk.status) {
      case 'active':
        return <span className="badge badge-success">Active</span>
      case 'expired':
        return <span className="badge badge-warning">Expired</span>
      case 'revoked':
        return <span className="badge badge-error">Revoked</span>
      default:
        return <span className="badge badge-gray">{ipsk.status}</span>
    }
  }

  const getAssociationIcon = () => {
    if (ipsk.associated_device_id) {
      return <Tv size={16} className="text-muted" />
    }
    if (ipsk.associated_area_id || ipsk.associated_unit) {
      return <Building2 size={16} className="text-muted" />
    }
    if (ipsk.associated_user) {
      return <User size={16} className="text-muted" />
    }
    return null
  }

  const getAssociationText = () => {
    if (ipsk.associated_device_name) return ipsk.associated_device_name
    if (ipsk.associated_area_name) return ipsk.associated_area_name
    if (ipsk.associated_unit) return `Unit ${ipsk.associated_unit}`
    if (ipsk.associated_user) return ipsk.associated_user
    return 'Unassigned'
  }

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <h4 style={{ margin: 0 }}>{ipsk.name}</h4>
          {getStatusBadge()}
        </div>
        
        <div className="flex gap-2">
          {ipsk.status === 'active' && onRevoke && (
            <button
              onClick={() => onRevoke(ipsk.id)}
              className="btn btn-icon btn-ghost"
              title="Revoke IPSK"
            >
              <Ban size={18} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(ipsk.id)}
              className="btn btn-icon btn-ghost"
              title="Delete IPSK"
              style={{ color: 'var(--error)' }}
            >
              <Trash2 size={18} />
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4 text-sm text-muted mb-4">
        <div className="flex items-center gap-2">
          {getAssociationIcon()}
          <span>{getAssociationText()}</span>
        </div>
        {ipsk.ssid_name && (
          <span>SSID: {ipsk.ssid_name}</span>
        )}
        {ipsk.connected_clients !== undefined && ipsk.connected_clients > 0 && (
          <span className="badge badge-info">{ipsk.connected_clients} connected</span>
        )}
      </div>

      {onReveal && (
        <div className="flex gap-2">
          <button
            onClick={handleReveal}
            className="btn btn-secondary btn-sm"
            disabled={loading}
          >
            {loading ? (
              <span className="loading-spinner" />
            ) : showPassphrase ? (
              <>
                <EyeOff size={16} /> Hide
              </>
            ) : (
              <>
                <Eye size={16} /> Reveal Passphrase
              </>
            )}
          </button>
          
          {showPassphrase && passphrase && (
            <div className="credential-box" style={{ flex: 1 }}>
              <span className="credential-value">{passphrase}</span>
              <button onClick={handleCopy} className="credential-copy" title="Copy">
                {copied ? <Check size={16} color="var(--success)" /> : <Copy size={16} />}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
