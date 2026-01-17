import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Shield, RefreshCw, AlertTriangle, CheckCircle, Pencil, Trash2, Beaker } from 'lucide-react'
import {
  createPolicy,
  deletePolicy,
  listPolicies,
  testPolicy,
  updatePolicy,
  type PolicyCreate,
  type PolicyResponse,
} from '../../api/radiusClient'

interface PolicyFormData {
  name: string
  group_name: string
  policy_type: 'user' | 'group' | 'device' | 'network'
  priority: number
  vlan_id: string
  bandwidth_limit_up: string
  bandwidth_limit_down: string
  is_active: boolean
}

const emptyPolicyForm: PolicyFormData = {
  name: '',
  group_name: '',
  policy_type: 'user',
  priority: 100,
  vlan_id: '',
  bandwidth_limit_up: '',
  bandwidth_limit_down: '',
  is_active: true,
}

export default function PolicyManagement() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingPolicy, setEditingPolicy] = useState<PolicyResponse | null>(null)
  const [formData, setFormData] = useState<PolicyFormData>(emptyPolicyForm)
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['radius-policies'],
    queryFn: async () => {
      const response = await listPolicies({ page: 1, page_size: 200 })
      return response.items
    },
  })

  const createMutation = useMutation({
    mutationFn: async (policy: PolicyCreate) => createPolicy(policy),
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Policy created successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['radius-policies'] })
      setShowAddModal(false)
      setFormData(emptyPolicyForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to create policy',
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ policyId, policy }: { policyId: number; policy: PolicyCreate }) =>
      updatePolicy(policyId, policy),
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Policy updated successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['radius-policies'] })
      setEditingPolicy(null)
      setFormData(emptyPolicyForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to update policy',
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (policyId: number) => deletePolicy(policyId),
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Policy deleted successfully',
      })
      queryClient.invalidateQueries({ queryKey: ['radius-policies'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message || 'Failed to delete policy',
      })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setNotification({
        type: 'error',
        message: 'Policy name is required',
      })
      return
    }

    const payload: PolicyCreate = {
      name: formData.name.trim(),
      group_name: formData.group_name.trim() || undefined,
      policy_type: formData.policy_type,
      priority: formData.priority,
      vlan_id: formData.vlan_id ? parseInt(formData.vlan_id, 10) : undefined,
      bandwidth_limit_up: formData.bandwidth_limit_up
        ? parseInt(formData.bandwidth_limit_up, 10)
        : undefined,
      bandwidth_limit_down: formData.bandwidth_limit_down
        ? parseInt(formData.bandwidth_limit_down, 10)
        : undefined,
      is_active: formData.is_active,
    }

    if (editingPolicy) {
      updateMutation.mutate({ policyId: editingPolicy.id, policy: payload })
      return
    }

    createMutation.mutate(payload)
  }

  const handleEdit = (policy: PolicyResponse) => {
    setEditingPolicy(policy)
    setFormData({
      name: policy.name,
      group_name: policy.group_name || '',
      policy_type: policy.policy_type as PolicyFormData['policy_type'],
      priority: policy.priority,
      vlan_id: policy.vlan_id?.toString() || '',
      bandwidth_limit_up: policy.bandwidth_limit_up?.toString() || '',
      bandwidth_limit_down: policy.bandwidth_limit_down?.toString() || '',
      is_active: policy.is_active,
    })
    setShowAddModal(true)
  }

  const handleDelete = (policy: PolicyResponse) => {
    if (window.confirm(`Delete policy "${policy.name}"?`)) {
      deleteMutation.mutate(policy.id)
    }
  }

  const handleTest = async (policy: PolicyResponse) => {
    const username = window.prompt('Enter a username to test this policy')
    if (!username) return
    const macAddress = window.prompt('Optional: Enter a MAC address to test (or leave blank)') || undefined

    try {
      const result = await testPolicy(policy.id, {
        username,
        mac_address: macAddress || null,
      })
      setNotification({
        type: result.matches ? 'success' : 'warning',
        message: result.matches
          ? `Policy matched. ${result.policy_name || policy.name}`
          : result.reason || 'Policy did not match.',
      })
      setTimeout(() => setNotification(null), 5000)
    } catch (error) {
      setNotification({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to test policy',
      })
      setTimeout(() => setNotification(null), 5000)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-meraki-blue" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="text-meraki-blue" />
            Policy Management
          </h1>
          <p className="text-gray-600 mt-1">
            Manage authorization policies for RADIUS access decisions
          </p>
        </div>
        <button
          onClick={() => {
            setShowAddModal(true)
            setEditingPolicy(null)
            setFormData(emptyPolicyForm)
          }}
          className="flex items-center gap-2 px-4 py-2 bg-meraki-blue text-white rounded-lg hover:bg-meraki-blue-dark transition-colors"
        >
          <Plus size={18} />
          Add Policy
        </button>
      </div>

      {notification && (
        <div
          className={`p-4 rounded-lg flex items-start gap-3 ${
            notification.type === 'success'
              ? 'bg-green-50 border border-green-200'
              : notification.type === 'error'
              ? 'bg-red-50 border border-red-200'
              : 'bg-yellow-50 border border-yellow-200'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
          ) : (
            <AlertTriangle
              className={`flex-shrink-0 ${
                notification.type === 'error' ? 'text-red-600' : 'text-yellow-600'
              }`}
              size={20}
            />
          )}
          <p
            className={`text-sm ${
              notification.type === 'success'
                ? 'text-green-900'
                : notification.type === 'error'
                ? 'text-red-900'
                : 'text-yellow-900'
            }`}
          >
            {notification.message}
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="text-red-600 flex-shrink-0" size={20} />
            <div>
              <p className="text-red-900 font-medium">Failed to load policies</p>
              <p className="text-red-700 text-sm mt-1">{(error as Error).message}</p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Group
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  VLAN
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Active
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {!data || data.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    No policies configured yet. Click "Add Policy" to create one.
                  </td>
                </tr>
              ) : (
                data.map((policy) => (
                  <tr key={policy.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <Shield className="text-meraki-blue" size={18} />
                        <span className="text-sm font-medium text-gray-900">{policy.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 capitalize">
                      {policy.policy_type}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {policy.group_name || '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {policy.priority}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {policy.vlan_id ?? '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {policy.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          <CheckCircle size={12} />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          <AlertTriangle size={12} />
                          Disabled
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleTest(policy)}
                          className="text-blue-600 hover:text-blue-800 transition-colors p-2"
                          title="Test policy"
                        >
                          <Beaker size={16} />
                        </button>
                        <button
                          onClick={() => handleEdit(policy)}
                          className="text-gray-600 hover:text-gray-800 transition-colors p-2"
                          title="Edit"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => handleDelete(policy)}
                          className="text-red-600 hover:text-red-800 transition-colors p-2"
                          title="Delete"
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
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">
                {editingPolicy ? 'Edit Policy' : 'Add Policy'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Policy Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent"
                    placeholder="e.g., Guest Access"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Group Name</label>
                  <input
                    type="text"
                    value={formData.group_name}
                    onChange={(e) => setFormData({ ...formData, group_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent"
                    placeholder="e.g., residents"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Policy Type
                    </label>
                    <select
                      value={formData.policy_type}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          policy_type: e.target.value as PolicyFormData['policy_type'],
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="user">User</option>
                      <option value="group">Group</option>
                      <option value="device">Device</option>
                      <option value="network">Network</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Priority
                    </label>
                    <input
                      type="number"
                      value={formData.priority}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          priority: parseInt(e.target.value, 10) || 0,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">VLAN ID</label>
                    <input
                      type="number"
                      value={formData.vlan_id}
                      onChange={(e) => setFormData({ ...formData, vlan_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      placeholder="e.g., 100"
                    />
                  </div>
                  <div className="flex items-center gap-2 pt-6">
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <span className="text-sm text-gray-700">Active</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Bandwidth Up (kbps)
                    </label>
                    <input
                      type="number"
                      value={formData.bandwidth_limit_up}
                      onChange={(e) =>
                        setFormData({ ...formData, bandwidth_limit_up: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Bandwidth Down (kbps)
                    </label>
                    <input
                      type="number"
                      value={formData.bandwidth_limit_down}
                      onChange={(e) =>
                        setFormData({ ...formData, bandwidth_limit_down: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddModal(false)
                      setEditingPolicy(null)
                      setFormData(emptyPolicyForm)
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="flex-1 px-4 py-2 bg-meraki-blue text-white rounded-lg hover:bg-meraki-blue-dark transition-colors disabled:opacity-50"
                  >
                    {createMutation.isPending || updateMutation.isPending
                      ? 'Saving...'
                      : editingPolicy
                      ? 'Save Changes'
                      : 'Create Policy'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
