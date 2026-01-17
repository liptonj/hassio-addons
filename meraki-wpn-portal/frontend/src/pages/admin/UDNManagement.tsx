import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Trash2,
  RefreshCw,
  Users,
  Hash,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Search,
} from 'lucide-react'
import { type UdnAssignmentResponse } from '../../api/radiusClient'
import api from '../../api/client'

interface NewAssignment {
  mac_address: string
  user_email: string
  unit: string
}

export default function UDNManagement() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [newAssignment, setNewAssignment] = useState<NewAssignment>({
    mac_address: '',
    user_email: '',
    unit: '',
  })
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: assignments, isLoading } = useQuery({
    queryKey: ['udn-assignments'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/udn/assignments', {
        params: { active_only: true }
      })
      return data as UdnAssignmentResponse[]
    },
  })

  const { data: poolStatus } = useQuery({
    queryKey: ['udn-pool-status'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/udn/pool')
      return data
    },
  })

  const assignMutation = useMutation({
    mutationFn: async (assignment: NewAssignment) => {
      const { data } = await api.post('/admin/radius/udn/assignments', {
        mac_address: assignment.mac_address,
        user_email: assignment.user_email || undefined,
        unit: assignment.unit || undefined,
      })
      return data
    },
    onSuccess: (data: { udn_id: number }) => {
      setNotification({
        type: 'success',
        message: `UDN ID ${data.udn_id} assigned to ${newAssignment.mac_address}`,
      })
      queryClient.invalidateQueries({ queryKey: ['udn-assignments'] })
      queryClient.invalidateQueries({ queryKey: ['udn-pool-status'] })
      setShowAddModal(false)
      setNewAssignment({ mac_address: '', user_email: '', unit: '' })
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

  const revokeMutation = useMutation({
    mutationFn: async (macAddress: string) => {
      await api.delete(`/admin/radius/udn/assignments/${encodeURIComponent(macAddress)}`)
    },
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'UDN assignment revoked successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['udn-assignments'] })
      queryClient.invalidateQueries({ queryKey: ['udn-pool-status'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message,
      })
    },
  })

  const handleAssign = () => {
    if (!newAssignment.mac_address) {
      setNotification({
        type: 'error',
        message: 'MAC address is required',
      })
      return
    }
    assignMutation.mutate(newAssignment)
  }

  const handleRevoke = (mac: string, udn_id: number) => {
    if (window.confirm(`Revoke UDN ID ${udn_id} from ${mac}?`)) {
      revokeMutation.mutate(mac)
    }
  }

  const filteredAssignments = assignments?.filter((assignment: UdnAssignmentResponse) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      assignment.mac_address.toLowerCase().includes(query) ||
      assignment.udn_id.toString().includes(query) ||
      assignment.user_name?.toLowerCase().includes(query) ||
      assignment.user_email?.toLowerCase().includes(query) ||
      assignment.unit?.toLowerCase().includes(query)
    )
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin" size={32} />
      </div>
    )
  }

  const totalPool = poolStatus ? poolStatus.total_assigned + poolStatus.total_available : 0
  const utilizationPercent = totalPool > 0 ? (poolStatus!.total_assigned / totalPool) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">UDN Assignments</h1>
          <p className="text-sm text-gray-600 mt-1">
            Manage Unique Device Network IDs for WPN segmentation
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <Plus size={16} />
          Assign UDN
        </button>
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

      {/* Pool Status */}
      {poolStatus && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-meraki-blue/10 rounded-lg">
                <Hash size={24} className="text-meraki-blue" />
              </div>
              <div>
            <div className="text-2xl font-bold">{poolStatus.total_assigned}</div>
                <div className="text-sm text-gray-600">Assigned</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircle size={24} className="text-green-600" />
              </div>
              <div>
            <div className="text-2xl font-bold">{poolStatus.total_available}</div>
                <div className="text-sm text-gray-600">Available</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-100 rounded-lg">
                <Users size={24} className="text-blue-600" />
              </div>
              <div>
            <div className="text-2xl font-bold">{totalPool}</div>
                <div className="text-sm text-gray-600">Total Pool</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="text-sm text-gray-600 mb-2">Utilization</div>
            <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                  utilizationPercent > 90
                    ? 'bg-red-500'
                    : utilizationPercent > 75
                    ? 'bg-yellow-500'
                    : 'bg-green-500'
                }`}
                style={{ width: `${utilizationPercent}%` }}
              />
            </div>
            <div className="text-xl font-bold mt-2">{utilizationPercent.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Info Card */}
      <div className="card bg-blue-50 border border-blue-200">
        <div className="flex items-start gap-3">
          <Hash size={20} className="text-meraki-blue mt-0.5" />
          <div>
            <h3 className="font-semibold text-blue-900 mb-1">About UDN IDs</h3>
            <p className="text-sm text-blue-800">
              UDN (Unique Device Network) IDs are used for WPN segmentation in Meraki networks. Each
              device gets a unique ID (2-16777200) which isolates it from other devices on the network.
              IDs are automatically assigned during registration and returned via RADIUS.
            </p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 relative">
            <Search size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
              placeholder="Search by MAC, UDN ID, email, or unit..."
            />
          </div>
          <span className="text-sm text-gray-600">
            {filteredAssignments?.length || 0} of {assignments?.length || 0}
          </span>
        </div>

        {/* Assignments Table */}
        {!filteredAssignments || filteredAssignments.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Hash size={48} className="mx-auto mb-3 opacity-30" />
            <p>{searchQuery ? 'No assignments match your search' : 'No UDN assignments yet'}</p>
            <p className="text-sm mt-1">
              {searchQuery ? 'Try a different search term' : 'Assign your first UDN to get started'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    MAC Address
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    UDN ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    User
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    Unit
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                    User
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
                {filteredAssignments.map((assignment: UdnAssignmentResponse) => (
                  <tr key={assignment.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                        {assignment.mac_address}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 px-2 py-1 bg-meraki-blue/10 text-meraki-blue text-sm font-medium rounded">
                        <Hash size={14} />
                        {assignment.udn_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {assignment.user_email || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {assignment.unit || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {assignment.user_name || assignment.user_email || '-'}
                    </td>
                    <td className="px-4 py-3">
                      {assignment.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          <CheckCircle size={12} />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          <XCircle size={12} />
                          Revoked
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {assignment.is_active && (
                        <button
                          onClick={() => handleRevoke(assignment.mac_address, assignment.udn_id)}
                          className="text-red-600 hover:text-red-800 transition-colors p-2"
                          title="Revoke"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Assignment Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h3 className="text-lg font-semibold mb-4">Assign UDN ID</h3>

            <div className="space-y-4">
              <FormRow label="MAC Address" required>
                <input
                  type="text"
                  value={newAssignment.mac_address}
                  onChange={(e) =>
                    setNewAssignment((prev) => ({ ...prev, mac_address: e.target.value }))
                  }
                  className="input font-mono"
                  placeholder="AA:BB:CC:DD:EE:FF"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Device MAC address (any format accepted)
                </p>
              </FormRow>

              <FormRow label="User Email">
                <input
                  type="email"
                  value={newAssignment.user_email}
                  onChange={(e) =>
                    setNewAssignment((prev) => ({ ...prev, user_email: e.target.value }))
                  }
                  className="input"
                  placeholder="user@example.com"
                />
              </FormRow>

              <FormRow label="Unit Number">
                <input
                  type="text"
                  value={newAssignment.unit}
                  onChange={(e) =>
                    setNewAssignment((prev) => ({ ...prev, unit: e.target.value }))
                  }
                  className="input"
                  placeholder="101"
                />
              </FormRow>

              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                <strong>Note:</strong> A unique UDN ID will be automatically assigned from the available
                pool (2-16777200).
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowAddModal(false)
                  setNewAssignment({ mac_address: '', user_email: '', unit: '' })
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAssign}
                disabled={assignMutation.isPending}
              >
                {assignMutation.isPending ? 'Assigning...' : 'Assign UDN'}
              </button>
            </div>
          </div>
        </div>
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
