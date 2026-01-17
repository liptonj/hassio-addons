import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Trash2,
  RefreshCw,
  Network,
  Server,
  Key,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Upload,
} from 'lucide-react'
import api, { getAllSettings } from '../../api/client'
import type { NadCreate, NadResponse } from '../../api/radiusClient'
import BulkNadImportModal from '../../components/BulkNadImportModal'

interface NewClient extends NadCreate {
  network_id: string
  radsec_enabled: boolean
  radsec_port: number
  require_tls_cert: boolean
  require_message_authenticator: boolean
}

export default function RADIUSClients() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [newClient, setNewClient] = useState<NewClient>({
    name: '',
    ipaddr: '',
    secret: '',
    nas_type: 'other',
    network_id: '',
    require_message_authenticator: true,
    radsec_enabled: false,
    radsec_port: 2083,
    require_tls_cert: true,
  })
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: clients, isLoading } = useQuery({
    queryKey: ['radius-clients'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/clients')
      // API returns array directly or { clients: [...] }
      return Array.isArray(data) ? data : (data.clients || [])
    },
  })

  const syncMerakiRadsec = async (networkId: string, radsecPort: number) => {
    const settings = await getAllSettings()
    const ssidNumber =
      typeof settings.default_ssid_number === 'number' ? settings.default_ssid_number : null
    const radiusHost = settings.radius_server_host as string | undefined
    const organizationId = settings.meraki_org_id as string | undefined

    if (!ssidNumber && ssidNumber !== 0) {
      throw new Error('Default SSID number is missing. Set it in portal settings.')
    }

    if (!radiusHost) {
      throw new Error('RADIUS server host is missing. Set radius_server_host in portal settings.')
    }

    if (!organizationId) {
      throw new Error('Meraki organization is not selected. Choose it in the Meraki settings tab.')
    }

    await api.post('/admin/radius/meraki/setup-radsec', {
      organization_id: organizationId,
      network_id: networkId,
      ssid_number: ssidNumber,
      radius_server_host: radiusHost,
      radius_server_port: radsecPort,
      generate_shared_secret: true,
    })
  }

  const addMutation = useMutation({
    mutationFn: async (client: NewClient) => {
      const payload = {
        name: client.name,
        ipaddr: client.ipaddr,
        secret: client.secret,
        nas_type: client.nas_type,
        network_id: client.network_id || undefined,
        require_message_authenticator: client.require_message_authenticator,
      }
      const { data } = await api.post('/admin/radius/clients', payload)
      return data
    },
    onSuccess: async (_created, variables) => {
      setNotification({
        type: 'success',
        message: 'RADIUS client added successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['radius-clients'] })

      if (variables.radsec_enabled && variables.network_id) {
        try {
          await syncMerakiRadsec(variables.network_id, variables.radsec_port)
        } catch (error) {
          setNotification({
            type: 'warning',
            message: error instanceof Error ? error.message : 'Failed to configure Meraki RadSec',
          })
        }
      }

      setShowAddModal(false)
      setNewClient({
        name: '',
        ipaddr: '',
        secret: '',
        nas_type: 'other',
        network_id: '',
        require_message_authenticator: true,
        radsec_enabled: false,
        radsec_port: 2083,
        require_tls_cert: true,
      })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message,
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/admin/radius/clients/${id}`)
    },
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'RADIUS client deleted successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['radius-clients'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message,
      })
    },
  })

  const handleAdd = () => {
    if (!newClient.name || !newClient.ipaddr || !newClient.secret) {
      setNotification({
        type: 'error',
        message: 'Please fill in all required fields',
      })
      return
    }
    addMutation.mutate(newClient)
  }

  const handleDelete = (id: number, name: string) => {
    if (window.confirm(`Delete RADIUS client "${name}"?`)) {
      deleteMutation.mutate(id)
    }
  }

  const generateSecret = () => {
    const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let secret = ''
    for (let i = 0; i < 32; i++) {
      secret += charset.charAt(Math.floor(Math.random() * charset.length))
    }
    setNewClient((prev) => ({ ...prev, secret: secret }))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">RADIUS Clients</h1>
          <p className="text-sm text-gray-600 mt-1">
            Manage network access points and devices that can use RADIUS authentication
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn btn-secondary flex items-center gap-2"
            onClick={() => setShowBulkImport(true)}
          >
            <Upload size={16} />
            Bulk Import from Meraki
          </button>
          <button
            className="btn btn-primary flex items-center gap-2"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={16} />
            Add Client
          </button>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 text-green-800 border border-green-200'
              : notification.type === 'warning'
              ? 'bg-yellow-100 text-yellow-800 border border-yellow-200'
              : 'bg-red-100 text-red-800 border border-red-200'
          }`}
        >
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <XCircle size={20} />}
          {notification.message}
        </div>
      )}

      {/* Info Card */}
      <div className="card bg-blue-50 border border-blue-200">
        <div className="flex items-start gap-3">
          <Network size={20} className="text-meraki-blue mt-0.5" />
          <div>
            <h3 className="font-semibold text-blue-900 mb-1">About RADIUS Clients</h3>
            <p className="text-sm text-blue-800">
              RADIUS clients are network devices (like Meraki access points) that send authentication
              requests to the RADIUS server. Each client needs a unique IP address and shared secret.
            </p>
          </div>
        </div>
      </div>

      {/* Clients List */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Active NADs</h3>
          <span className="text-sm text-gray-600">
            {clients?.length || 0} NAD{clients?.length !== 1 ? 's' : ''}
          </span>
        </div>

        {!clients || clients.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Network size={48} className="mx-auto mb-3 opacity-30" />
            <p>No NADs configured</p>
            <p className="text-sm mt-1">Add your first NAD to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    IP Address
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    NAS Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    RadSec
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-600 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {clients.map((client) => (
                  <tr key={client.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Server size={16} className="text-gray-400" />
                        <span className="font-medium">{client.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                        {client.ipaddr}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 capitalize">
                      {client.nas_type}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {client.radsec_enabled ? `Enabled (${client.radsec_port || 2083})` : 'Disabled'}
                    </td>
                    <td className="px-4 py-3">
                      {client.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          <CheckCircle size={12} />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          <XCircle size={12} />
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(client.id, client.name)}
                        className="text-red-600 hover:text-red-800 transition-colors p-2"
                        title="Delete"
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
      </div>

      {/* Add Client Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Add Network Access Device</h3>

            <div className="space-y-4">
              <FormRow label="Client Name" required>
                <input
                  type="text"
                  value={newClient.name}
                  onChange={(e) => setNewClient((prev) => ({ ...prev, name: e.target.value }))}
                  className="input"
                  placeholder="e.g., Main Campus APs"
                />
              </FormRow>

              <FormRow label="IP Address / CIDR" required>
                <input
                  type="text"
                  value={newClient.ipaddr}
                  onChange={(e) => setNewClient((prev) => ({ ...prev, ipaddr: e.target.value }))}
                  className="input"
                  placeholder="e.g., 192.168.1.0/24 or 10.0.0.1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  IP address or CIDR range of the network access points
                </p>
              </FormRow>

              <FormRow label="Shared Secret" required>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newClient.secret}
                    onChange={(e) =>
                      setNewClient((prev) => ({ ...prev, secret: e.target.value }))
                    }
                    className="input flex-1 font-mono"
                    placeholder="Enter or generate a strong secret"
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={generateSecret}
                  >
                    <Key size={16} />
                    Generate
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Must match the secret configured on the network device
                </p>
              </FormRow>

              <FormRow label="NAS Type">
                <select
                  value={newClient.nas_type}
                  onChange={(e) => setNewClient((prev) => ({ ...prev, nas_type: e.target.value }))}
                  className="input"
                >
                  <option value="other">Other</option>
                  <option value="cisco">Cisco</option>
                  <option value="meraki">Meraki</option>
                  <option value="aruba">Aruba</option>
                  <option value="ruckus">Ruckus</option>
                  <option value="ubiquiti">Ubiquiti</option>
                </select>
              </FormRow>

              <FormRow label="Meraki Network ID">
                <input
                  type="text"
                  value={newClient.network_id}
                  onChange={(e) => setNewClient((prev) => ({ ...prev, network_id: e.target.value }))}
                  className="input"
                  placeholder="e.g., L_123456789"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Optional. Used to auto-configure Meraki RadSec when enabled.
                </p>
              </FormRow>

              <FormRow label="Enable RadSec">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={newClient.radsec_enabled}
                    onChange={(e) =>
                      setNewClient((prev) => ({ ...prev, radsec_enabled: e.target.checked }))
                    }
                    className="w-5 h-5"
                  />
                  <span className="text-sm text-gray-600">
                    Use RADIUS over TLS (RadSec) for this NAD
                  </span>
                </div>
              </FormRow>

              {newClient.radsec_enabled && (
                <>
                  <FormRow label="RadSec Port">
                    <input
                      type="number"
                      value={newClient.radsec_port}
                      onChange={(e) =>
                        setNewClient((prev) => ({
                          ...prev,
                          radsec_port: parseInt(e.target.value) || 2083,
                        }))
                      }
                      className="input"
                    />
                  </FormRow>
                  <FormRow label="Require TLS Client Certificate">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={newClient.require_tls_cert}
                        onChange={(e) =>
                          setNewClient((prev) => ({
                            ...prev,
                            require_tls_cert: e.target.checked,
                          }))
                        }
                        className="w-5 h-5"
                      />
                      <span className="text-sm text-gray-600">
                        Require client certificates for RadSec connections
                      </span>
                    </div>
                  </FormRow>
                </>
              )}

              <FormRow label="Require Message Authenticator">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={newClient.require_message_authenticator}
                    onChange={(e) =>
                      setNewClient((prev) => ({
                        ...prev,
                        require_message_authenticator: e.target.checked,
                      }))
                    }
                    className="w-5 h-5"
                  />
                  <span className="text-sm text-gray-600">
                    Require message authenticator attribute (recommended for security)
                  </span>
                </div>
              </FormRow>
            </div>

            <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowAddModal(false)
                  setNewClient({
                    name: '',
                    ipaddr: '',
                    secret: '',
                    nas_type: 'other',
                    network_id: '',
                    require_message_authenticator: true,
                    radsec_enabled: false,
                    radsec_port: 2083,
                    require_tls_cert: true,
                  })
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAdd}
                disabled={addMutation.isPending}
              >
                {addMutation.isPending ? 'Adding...' : 'Add Client'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Import Modal */}
      {showBulkImport && (
        <BulkNadImportModal
          onClose={() => setShowBulkImport(false)}
          onImport={() => {
            setShowBulkImport(false)
            setNotification({
              type: 'success',
              message: 'NADs imported successfully from Meraki devices',
            })
            queryClient.invalidateQueries({ queryKey: ['radius-nads'] })
          }}
        />
      )}
    </div>
  )
}

function FormRow({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium mb-2">
        {label}
        {required && <span className="text-danger"> *</span>}
      </label>
      {children}
    </div>
  )
}
