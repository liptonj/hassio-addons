import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  FileCheck,
  Download,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Lock,
} from 'lucide-react'
import {
  getUserCertificates,
  downloadCertificate,
  revokeCertificate,
  renewCertificate,
  type UserCertificate,
} from '../../api/client'

export default function UserCertificates() {
  const queryClient = useQueryClient()
  const [selectedFormat, setSelectedFormat] = useState<'pkcs12' | 'pem'>('pkcs12')
  const [revokeConfirm, setRevokeConfirm] = useState<number | null>(null)
  const [renewId, setRenewId] = useState<number | null>(null)
  const [renewPassword, setRenewPassword] = useState('')

  // Fetch certificates
  const { data, isLoading, error } = useQuery({
    queryKey: ['userCertificates'],
    queryFn: getUserCertificates,
  })

  // Download certificate
  const handleDownload = async (id: number, format: 'pkcs12' | 'pem') => {
    try {
      const blob = await downloadCertificate(id, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = format === 'pkcs12' ? `certificate_${id}.p12` : `certificate_${id}.pem`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      queryClient.invalidateQueries({ queryKey: ['userCertificates'] })
    } catch (error) {
      alert(`Failed to download certificate: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  // Revoke certificate
  const revokeMutation = useMutation({
    mutationFn: (id: number) => revokeCertificate(id, 'user_requested'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userCertificates'] })
      setRevokeConfirm(null)
      alert('Certificate revoked successfully')
    },
    onError: (error: Error) => {
      alert(`Failed to revoke certificate: ${error.message}`)
    },
  })

  // Renew certificate
  const renewMutation = useMutation({
    mutationFn: ({ id, passphrase }: { id: number; passphrase: string }) => 
      renewCertificate(id, passphrase),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userCertificates'] })
      setRenewId(null)
      setRenewPassword('')
      alert('Certificate renewed successfully. Download the new certificate below.')
    },
    onError: (error: Error) => {
      alert(`Failed to renew certificate: ${error.message}`)
    },
  })

  const handleRenew = (id: number) => {
    if (renewPassword.length < 8) {
      alert('Password must be at least 8 characters')
      return
    }
    renewMutation.mutate({ id, passphrase: renewPassword })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-600 bg-green-50'
      case 'revoked':
        return 'text-red-600 bg-red-50'
      case 'expired':
        return 'text-gray-600 bg-gray-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle size={16} />
      case 'revoked':
        return <XCircle size={16} />
      case 'expired':
        return <AlertTriangle size={16} />
      default:
        return null
    }
  }

  const isExpiringSoon = (cert: UserCertificate) => {
    const daysUntilExpiry = Math.floor(
      (new Date(cert.valid_until).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    )
    return daysUntilExpiry <= 30 && cert.status === 'active'
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <span className="loading-spinner w-10 h-10" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="text-red-500 mt-0.5" size={20} />
          <div>
            <h3 className="font-medium text-red-900">Error Loading Certificates</h3>
            <p className="text-sm text-red-700 mt-1">{error.message}</p>
          </div>
        </div>
      </div>
    )
  }

  const certificates = data?.certificates || []

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">My Certificates</h1>
        <p className="text-gray-600 mt-2">
          Manage your WiFi authentication certificates for EAP-TLS (WPA2-Enterprise)
        </p>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <p className="font-medium mb-1">About WiFi Certificates</p>
            <p>
              Certificates provide enterprise-grade security for WiFi access. Install the certificate on your device to connect to the Enterprise-WiFi network.
              Each certificate is password-protected for security.
            </p>
          </div>
        </div>
      </div>

      {/* No Certificates */}
      {certificates.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
          <FileCheck className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="font-medium text-gray-900 mb-2">No Certificates</h3>
          <p className="text-gray-600 mb-4">
            You don't have any certificates yet. Register for WiFi with EAP-TLS authentication to get one.
          </p>
        </div>
      )}

      {/* Certificates List */}
      {certificates.length > 0 && (
        <div className="space-y-4">
          {certificates.map((cert) => (
            <div
              key={cert.id}
              className="bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3">
                  <FileCheck className="text-blue-600 mt-1" size={24} />
                  <div>
                    <h3 className="font-medium text-gray-900">{cert.common_name}</h3>
                    <p className="text-sm text-gray-600">{cert.user_email}</p>
                  </div>
                </div>
                <span className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(cert.status)}`}>
                  {getStatusIcon(cert.status)}
                  {cert.status.charAt(0).toUpperCase() + cert.status.slice(1)}
                </span>
              </div>

              {/* Certificate Details */}
              <div className="grid md:grid-cols-3 gap-4 mb-4 text-sm">
                <div>
                  <p className="text-gray-600">Serial Number</p>
                  <p className="font-mono text-gray-900">{cert.serial_number.slice(0, 16)}...</p>
                </div>
                <div>
                  <p className="text-gray-600">Issued</p>
                  <p className="text-gray-900">{new Date(cert.issued_at).toLocaleDateString()}</p>
                </div>
                <div>
                  <p className="text-gray-600">Expires</p>
                  <p className="text-gray-900">{new Date(cert.valid_until).toLocaleDateString()}</p>
                </div>
              </div>

              {/* Expiring Soon Warning */}
              {isExpiringSoon(cert) && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="text-amber-600 mt-0.5 flex-shrink-0" size={18} />
                    <div className="text-sm text-amber-900">
                      <p className="font-medium">Expiring Soon</p>
                      <p>
                        This certificate will expire in{' '}
                        {Math.floor((new Date(cert.valid_until).getTime() - Date.now()) / (1000 * 60 * 60 * 24))} days.
                        {cert.auto_renew ? ' It will be automatically renewed.' : ' Consider renewing it manually.'}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              {cert.status === 'active' && (
                <div className="flex flex-wrap gap-3">
                  {/* Download Format Selector */}
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-gray-700">Format:</label>
                    <select
                      value={selectedFormat}
                      onChange={(e) => setSelectedFormat(e.target.value as 'pkcs12' | 'pem')}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="pkcs12">PKCS#12 (.p12) - iOS/macOS</option>
                      <option value="pem">PEM (.pem) - Android/Linux</option>
                    </select>
                  </div>

                  <button
                    onClick={() => handleDownload(cert.id, selectedFormat)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <Download size={18} />
                    Download
                  </button>

                  <button
                    onClick={() => setRenewId(cert.id)}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <RefreshCw size={18} />
                    Renew
                  </button>

                  <button
                    onClick={() => setRevokeConfirm(cert.id)}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={18} />
                    Revoke
                  </button>
                </div>
              )}

              {/* Download Info */}
              {cert.download_count > 0 && (
                <p className="text-sm text-gray-500 mt-3">
                  Downloaded {cert.download_count} time{cert.download_count !== 1 ? 's' : ''}
                  {cert.last_downloaded_at && ` (last: ${new Date(cert.last_downloaded_at).toLocaleDateString()})`}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Revoke Confirmation Modal */}
      {revokeConfirm !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-start gap-3 mb-4">
              <AlertTriangle className="text-red-500 mt-0.5 flex-shrink-0" size={24} />
              <div>
                <h3 className="font-bold text-gray-900 text-lg">Revoke Certificate?</h3>
                <p className="text-sm text-gray-600 mt-2">
                  This certificate will no longer be valid for WiFi authentication. You will need to download a new certificate to reconnect.
                </p>
                <p className="text-sm text-red-600 mt-2 font-medium">
                  This action cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setRevokeConfirm(null)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => revokeMutation.mutate(revokeConfirm)}
                disabled={revokeMutation.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {revokeMutation.isPending ? 'Revoking...' : 'Revoke Certificate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Renew Modal */}
      {renewId !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="font-bold text-gray-900 text-lg mb-4">Renew Certificate</h3>
            <p className="text-sm text-gray-600 mb-4">
              Enter a password to protect your new certificate. You'll need this password when installing the certificate on your device.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Lock size={16} className="inline mr-1" />
                Certificate Password
              </label>
              <input
                type="password"
                value={renewPassword}
                onChange={(e) => setRenewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                minLength={8}
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setRenewId(null)
                  setRenewPassword('')
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleRenew(renewId)}
                disabled={renewMutation.isPending || renewPassword.length < 8}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {renewMutation.isPending ? 'Renewing...' : 'Renew Certificate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
