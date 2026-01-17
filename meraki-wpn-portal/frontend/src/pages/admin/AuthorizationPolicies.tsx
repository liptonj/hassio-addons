import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Shield, RefreshCw, AlertTriangle, CheckCircle, Pencil, Trash2, Link2, Code } from 'lucide-react'
import {
  createUnlangPolicy,
  deleteUnlangPolicy,
  listUnlangPolicies,
  updateUnlangPolicy,
  listPolicies,
  type UnlangPolicyCreate,
  type UnlangPolicyResponse,
  type PolicyResponse,
} from '../../api/radiusClient'

interface PolicyFormData {
  name: string
  description: string
  priority: number
  policy_type: string
  section: string
  condition_type: string
  condition_attribute: string
  condition_operator: string
  condition_value: string
  action_type: string
  authorization_profile_id: number | null
  is_active: boolean
}

const emptyPolicyForm: PolicyFormData = {
  name: '',
  description: '',
  priority: 100,
  policy_type: 'authorization',
  section: 'authorize',
  condition_type: 'attribute',
  condition_attribute: '',
  condition_operator: 'exists',
  condition_value: '',
  action_type: 'apply_profile',
  authorization_profile_id: null,
  is_active: true,
}

export default function AuthorizationPolicies() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingPolicy, setEditingPolicy] = useState<UnlangPolicyResponse | null>(null)
  const [formData, setFormData] = useState<PolicyFormData>(emptyPolicyForm)
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  // Fetch authorization policies (unlang policies)
  const { data: policies, isLoading, error, refetch } = useQuery({
    queryKey: ['unlang-policies'],
    queryFn: async () => {
      const response = await listUnlangPolicies({ page: 1, page_size: 200 })
      return response.items
    },
  })

  // Fetch profiles for dropdown
  const { data: profiles } = useQuery({
    queryKey: ['radius-profiles'],
    queryFn: async () => {
      const response = await listPolicies({ page: 1, page_size: 200 })
      return response.items
    },
  })

  const createMutation = useMutation({
    mutationFn: async (policy: UnlangPolicyCreate) => createUnlangPolicy(policy),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Authorization policy created successfully' })
      queryClient.invalidateQueries({ queryKey: ['unlang-policies'] })
      setShowAddModal(false)
      setFormData(emptyPolicyForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to create policy' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ policyId, policy }: { policyId: number; policy: UnlangPolicyCreate }) =>
      updateUnlangPolicy(policyId, policy),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Authorization policy updated successfully' })
      queryClient.invalidateQueries({ queryKey: ['unlang-policies'] })
      setEditingPolicy(null)
      setFormData(emptyPolicyForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to update policy' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (policyId: number) => deleteUnlangPolicy(policyId),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Authorization policy deleted successfully' })
      queryClient.invalidateQueries({ queryKey: ['unlang-policies'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to delete policy' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setNotification({ type: 'error', message: 'Policy name is required' })
      return
    }

    const payload: UnlangPolicyCreate = {
      name: formData.name.trim(),
      description: formData.description.trim() || undefined,
      priority: formData.priority,
      policy_type: formData.policy_type,
      section: formData.section,
      condition_type: formData.condition_type,
      condition_attribute: formData.condition_attribute.trim() || undefined,
      condition_operator: formData.condition_operator,
      condition_value: formData.condition_value.trim() || undefined,
      action_type: formData.action_type,
      authorization_profile_id: formData.authorization_profile_id || undefined,
      is_active: formData.is_active,
    }

    if (editingPolicy) {
      updateMutation.mutate({ policyId: editingPolicy.id, policy: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleEdit = (policy: UnlangPolicyResponse) => {
    setEditingPolicy(policy)
    setFormData({
      name: policy.name,
      description: policy.description || '',
      priority: policy.priority,
      policy_type: policy.policy_type,
      section: policy.section,
      condition_type: policy.condition_type,
      condition_attribute: policy.condition_attribute || '',
      condition_operator: policy.condition_operator,
      condition_value: policy.condition_value || '',
      action_type: policy.action_type,
      authorization_profile_id: policy.authorization_profile_id || null,
      is_active: policy.is_active,
    })
    setShowAddModal(true)
  }

  const handleDelete = (policy: UnlangPolicyResponse) => {
    if (policy.used_by_mac_bypass?.length || policy.used_by_eap_methods?.length) {
      setNotification({
        type: 'error',
        message: 'Cannot delete policy that is in use by authentication methods',
      })
      return
    }
    if (confirm(`Are you sure you want to delete policy "${policy.name}"?`)) {
      deleteMutation.mutate(policy.id)
    }
  }

  const handleCloseModal = () => {
    setShowAddModal(false)
    setEditingPolicy(null)
    setFormData(emptyPolicyForm)
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="text-red-700">Error loading policies: {String(error)}</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="h-7 w-7 text-indigo-600" />
            Authorization Policies
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Define conditions and link profiles to authentication methods. Policies determine when and which profile to apply.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            Add Policy
          </button>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`flex items-center gap-2 rounded-lg border p-4 ${
            notification.type === 'success'
              ? 'border-green-200 bg-green-50 text-green-700'
              : notification.type === 'error'
                ? 'border-red-200 bg-red-50 text-red-700'
                : 'border-yellow-200 bg-yellow-50 text-yellow-700'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <AlertTriangle className="h-5 w-5" />
          )}
          {notification.message}
        </div>
      )}

      {/* Policies Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Policy
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Condition
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Profile
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Used By
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                  <RefreshCw className="mx-auto h-8 w-8 animate-spin text-indigo-500" />
                  <p className="mt-2">Loading policies...</p>
                </td>
              </tr>
            ) : policies && policies.length > 0 ? (
              policies.map((policy) => (
                <tr key={policy.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-indigo-100 p-2">
                        <Shield className="h-5 w-5 text-indigo-600" />
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{policy.name}</div>
                        {policy.description && (
                          <div className="text-sm text-gray-500 truncate max-w-xs">{policy.description}</div>
                        )}
                        <div className="text-xs text-gray-400">Priority: {policy.priority}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <div className="flex items-center gap-1">
                      <Code className="h-4 w-4 text-gray-400" />
                      <span className="font-mono text-xs">
                        {policy.condition_type === 'attribute'
                          ? `${policy.condition_attribute || 'any'} ${policy.condition_operator} ${policy.condition_value || ''}`
                          : policy.condition_type}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      Action: {policy.action_type}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm">
                    {policy.authorization_profile_name ? (
                      <div className="flex items-center gap-1">
                        <Link2 className="h-4 w-4 text-teal-500" />
                        <span className="text-teal-700">{policy.authorization_profile_name}</span>
                      </div>
                    ) : (
                      <span className="text-gray-400">No profile</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <div className="space-y-1">
                      {policy.used_by_mac_bypass && policy.used_by_mac_bypass.length > 0 && (
                        <div className="text-xs text-blue-600">
                          MAC Bypass: {policy.used_by_mac_bypass.join(', ')}
                        </div>
                      )}
                      {policy.used_by_eap_methods && policy.used_by_eap_methods.length > 0 && (
                        <div className="text-xs text-purple-600">
                          EAP: {policy.used_by_eap_methods.join(', ')}
                        </div>
                      )}
                      {!policy.used_by_mac_bypass?.length && !policy.used_by_eap_methods?.length && (
                        <span className="text-gray-400">Not in use</span>
                      )}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                        policy.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {policy.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEdit(policy)}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-blue-600"
                        title="Edit policy"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(policy)}
                        className="rounded p-1.5 text-gray-400 hover:bg-red-100 hover:text-red-600"
                        title="Delete policy"
                        disabled={!!(policy.used_by_mac_bypass?.length || policy.used_by_eap_methods?.length)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center">
                  <Shield className="mx-auto h-12 w-12 text-gray-300" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No authorization policies yet</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Create policies to define conditions and link them to profiles.
                  </p>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                  >
                    <Plus className="h-4 w-4" />
                    Add Policy
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add/Edit Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-2xl">
            <div className="border-b border-gray-200 px-6 py-4">
              <h2 className="text-xl font-semibold text-gray-900">
                {editingPolicy ? 'Edit Authorization Policy' : 'Add New Authorization Policy'}
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Define when this policy applies and which profile to use.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {/* Basic Info */}
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900">Basic Information</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Name *</label>
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Priority</label>
                    <input
                      type="number"
                      name="priority"
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value, 10) || 100 })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      min="0"
                      max="1000"
                    />
                    <p className="mt-1 text-xs text-gray-500">Lower = higher priority (0-1000)</p>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    name="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    rows={2}
                  />
                </div>
              </div>

              {/* Condition */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  <Code className="h-5 w-5 text-purple-600" />
                  Condition
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Condition Type</label>
                    <select
                      name="condition_type"
                      value={formData.condition_type}
                      onChange={(e) => setFormData({ ...formData, condition_type: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="attribute">Attribute Check</option>
                      <option value="sql_lookup">SQL Lookup</option>
                      <option value="module_call">Module Call</option>
                      <option value="custom">Custom Unlang</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Attribute</label>
                    <input
                      type="text"
                      name="condition_attribute"
                      value={formData.condition_attribute}
                      onChange={(e) => setFormData({ ...formData, condition_attribute: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="e.g., User-Name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Operator</label>
                    <select
                      name="condition_operator"
                      value={formData.condition_operator}
                      onChange={(e) => setFormData({ ...formData, condition_operator: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="exists">Exists</option>
                      <option value="notexists">Not Exists</option>
                      <option value="==">Equals (==)</option>
                      <option value="!=">Not Equals (!=)</option>
                      <option value="=~">Matches Regex (=~)</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Value</label>
                  <input
                    type="text"
                    name="condition_value"
                    value={formData.condition_value}
                    onChange={(e) => setFormData({ ...formData, condition_value: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Value to compare (optional for exists/notexists)"
                  />
                </div>
              </div>

              {/* Action */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  <Link2 className="h-5 w-5 text-teal-600" />
                  Action & Profile
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Action Type</label>
                    <select
                      name="action_type"
                      value={formData.action_type}
                      onChange={(e) => setFormData({ ...formData, action_type: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="apply_profile">Apply Profile</option>
                      <option value="accept">Accept</option>
                      <option value="reject">Reject</option>
                      <option value="continue">Continue</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Profile to Apply</label>
                    <select
                      name="authorization_profile_id"
                      value={formData.authorization_profile_id || ''}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          authorization_profile_id: e.target.value ? parseInt(e.target.value, 10) : null,
                        })
                      }
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="">-- Select Profile --</option>
                      {profiles?.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                          {profile.vlan_id ? ` (VLAN ${profile.vlan_id})` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      Profile defines RADIUS attributes (VLAN, bandwidth, etc.)
                    </p>
                  </div>
                </div>
              </div>

              {/* Status */}
              <div className="border-t pt-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm font-medium text-gray-700">Active</span>
                </label>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 border-t pt-4">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingPolicy
                      ? 'Update Policy'
                      : 'Create Policy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
