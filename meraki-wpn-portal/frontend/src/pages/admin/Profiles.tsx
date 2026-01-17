import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, SlidersHorizontal, RefreshCw, AlertTriangle, CheckCircle, Pencil, Trash2, Network, Gauge, Shield } from 'lucide-react'
import {
  createPolicy,
  deletePolicy,
  listPolicies,
  updatePolicy,
  type PolicyCreate,
  type PolicyResponse,
} from '../../api/radiusClient'

interface ProfileFormData {
  name: string
  description: string
  priority: number
  vlan_id: string
  vlan_name: string
  bandwidth_limit_up: string
  bandwidth_limit_down: string
  filter_id: string
  sgt_value: string
  sgt_name: string
  session_timeout: string
  idle_timeout: string
  splash_url: string
  url_redirect_acl: string
  is_active: boolean
}

const emptyProfileForm: ProfileFormData = {
  name: '',
  description: '',
  priority: 100,
  vlan_id: '',
  vlan_name: '',
  bandwidth_limit_up: '',
  bandwidth_limit_down: '',
  filter_id: '',
  sgt_value: '',
  sgt_name: '',
  session_timeout: '',
  idle_timeout: '',
  splash_url: '',
  url_redirect_acl: '',
  is_active: true,
}

export default function Profiles() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingProfile, setEditingProfile] = useState<PolicyResponse | null>(null)
  const [formData, setFormData] = useState<ProfileFormData>(emptyProfileForm)
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: profiles, isLoading, error, refetch } = useQuery({
    queryKey: ['radius-profiles'],
    queryFn: async () => {
      const response = await listPolicies({ page: 1, page_size: 200 })
      return response.items
    },
  })

  const createMutation = useMutation({
    mutationFn: async (profile: PolicyCreate) => createPolicy(profile),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Profile created successfully' })
      queryClient.invalidateQueries({ queryKey: ['radius-profiles'] })
      setShowAddModal(false)
      setFormData(emptyProfileForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to create profile' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ profileId, profile }: { profileId: number; profile: PolicyCreate }) =>
      updatePolicy(profileId, profile),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Profile updated successfully' })
      queryClient.invalidateQueries({ queryKey: ['radius-profiles'] })
      setEditingProfile(null)
      setFormData(emptyProfileForm)
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to update profile' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (profileId: number) => deletePolicy(profileId),
    onSuccess: () => {
      setNotification({ type: 'success', message: 'Profile deleted successfully' })
      queryClient.invalidateQueries({ queryKey: ['radius-profiles'] })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message || 'Failed to delete profile' })
      setTimeout(() => setNotification(null), 5000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setNotification({ type: 'error', message: 'Profile name is required' })
      return
    }

    const payload: PolicyCreate = {
      name: formData.name.trim(),
      description: formData.description.trim() || undefined,
      priority: formData.priority,
      policy_type: 'user', // Profiles are user-type by default
      vlan_id: formData.vlan_id ? parseInt(formData.vlan_id, 10) : undefined,
      vlan_name: formData.vlan_name.trim() || undefined,
      bandwidth_limit_up: formData.bandwidth_limit_up ? parseInt(formData.bandwidth_limit_up, 10) : undefined,
      bandwidth_limit_down: formData.bandwidth_limit_down ? parseInt(formData.bandwidth_limit_down, 10) : undefined,
      session_timeout: formData.session_timeout ? parseInt(formData.session_timeout, 10) : undefined,
      idle_timeout: formData.idle_timeout ? parseInt(formData.idle_timeout, 10) : undefined,
      is_active: formData.is_active,
    }

    if (editingProfile) {
      updateMutation.mutate({ profileId: editingProfile.id, profile: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleEdit = (profile: PolicyResponse) => {
    setEditingProfile(profile)
    setFormData({
      name: profile.name,
      description: profile.description || '',
      priority: profile.priority,
      vlan_id: profile.vlan_id?.toString() || '',
      vlan_name: profile.vlan_name || '',
      bandwidth_limit_up: profile.bandwidth_limit_up?.toString() || '',
      bandwidth_limit_down: profile.bandwidth_limit_down?.toString() || '',
      filter_id: '',
      sgt_value: '',
      sgt_name: '',
      session_timeout: profile.session_timeout?.toString() || '',
      idle_timeout: profile.idle_timeout?.toString() || '',
      splash_url: '',
      url_redirect_acl: '',
      is_active: profile.is_active,
    })
    setShowAddModal(true)
  }

  const handleDelete = (profile: PolicyResponse) => {
    if (confirm(`Are you sure you want to delete profile "${profile.name}"?`)) {
      deleteMutation.mutate(profile.id)
    }
  }

  const handleCloseModal = () => {
    setShowAddModal(false)
    setEditingProfile(null)
    setFormData(emptyProfileForm)
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="text-red-700">Error loading profiles: {String(error)}</span>
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
            <SlidersHorizontal className="h-7 w-7 text-teal-600" />
            RADIUS Profiles
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage RADIUS attribute profiles (VLAN, bandwidth, SGT, etc.) that can be applied by authorization policies.
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
            className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            <Plus className="h-4 w-4" />
            Add Profile
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

      {/* Profiles Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Profile
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                VLAN
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Bandwidth
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Timeouts
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
                  <RefreshCw className="mx-auto h-8 w-8 animate-spin text-teal-500" />
                  <p className="mt-2">Loading profiles...</p>
                </td>
              </tr>
            ) : profiles && profiles.length > 0 ? (
              profiles.map((profile) => (
                <tr key={profile.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-teal-100 p-2">
                        <SlidersHorizontal className="h-5 w-5 text-teal-600" />
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{profile.name}</div>
                        {profile.description && (
                          <div className="text-sm text-gray-500 truncate max-w-xs">{profile.description}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm">
                    {profile.vlan_id ? (
                      <div className="flex items-center gap-1">
                        <Network className="h-4 w-4 text-blue-500" />
                        <span className="font-mono">{profile.vlan_id}</span>
                        {profile.vlan_name && (
                          <span className="text-gray-500">({profile.vlan_name})</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm">
                    {profile.bandwidth_limit_up || profile.bandwidth_limit_down ? (
                      <div className="flex items-center gap-1">
                        <Gauge className="h-4 w-4 text-purple-500" />
                        <span>
                          ↑{profile.bandwidth_limit_up || '—'} / ↓{profile.bandwidth_limit_down || '—'} Kbps
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {profile.session_timeout || profile.idle_timeout ? (
                      <div>
                        {profile.session_timeout && <div>Session: {profile.session_timeout}s</div>}
                        {profile.idle_timeout && <div>Idle: {profile.idle_timeout}s</div>}
                      </div>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                        profile.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {profile.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEdit(profile)}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-blue-600"
                        title="Edit profile"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(profile)}
                        className="rounded p-1.5 text-gray-400 hover:bg-red-100 hover:text-red-600"
                        title="Delete profile"
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
                  <SlidersHorizontal className="mx-auto h-12 w-12 text-gray-300" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No profiles yet</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Create a profile to define RADIUS attributes that can be applied to users.
                  </p>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="mt-4 inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
                  >
                    <Plus className="h-4 w-4" />
                    Add Profile
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
                {editingProfile ? 'Edit Profile' : 'Add New Profile'}
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Define the RADIUS attributes that will be returned when this profile is applied.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {/* Basic Info */}
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  <Shield className="h-5 w-5 text-teal-600" />
                  Basic Information
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Name *</label>
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Priority</label>
                    <input
                      type="number"
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value, 10) || 100 })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="0"
                      max="1000"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    name="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                    rows={2}
                  />
                </div>
              </div>

              {/* Network Settings */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  <Network className="h-5 w-5 text-blue-600" />
                  Network Settings
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">VLAN ID</label>
                    <input
                      type="number"
                      name="vlan_id"
                      value={formData.vlan_id}
                      onChange={(e) => setFormData({ ...formData, vlan_id: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="1"
                      max="4094"
                      placeholder="1-4094"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">VLAN Name</label>
                    <input
                      type="text"
                      name="vlan_name"
                      value={formData.vlan_name}
                      onChange={(e) => setFormData({ ...formData, vlan_name: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      placeholder="e.g., Guest, Corporate"
                    />
                  </div>
                </div>
              </div>

              {/* Bandwidth Settings */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  <Gauge className="h-5 w-5 text-purple-600" />
                  Bandwidth Limits
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Upload Limit (Kbps)</label>
                    <input
                      type="number"
                      name="bandwidth_limit_up"
                      value={formData.bandwidth_limit_up}
                      onChange={(e) => setFormData({ ...formData, bandwidth_limit_up: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="0"
                      placeholder="e.g., 10000"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Download Limit (Kbps)</label>
                    <input
                      type="number"
                      name="bandwidth_limit_down"
                      value={formData.bandwidth_limit_down}
                      onChange={(e) => setFormData({ ...formData, bandwidth_limit_down: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="0"
                      placeholder="e.g., 50000"
                    />
                  </div>
                </div>
              </div>

              {/* Session Settings */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="font-medium text-gray-900">Session Settings</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Session Timeout (seconds)</label>
                    <input
                      type="number"
                      name="session_timeout"
                      value={formData.session_timeout}
                      onChange={(e) => setFormData({ ...formData, session_timeout: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="0"
                      placeholder="e.g., 3600"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Idle Timeout (seconds)</label>
                    <input
                      type="number"
                      name="idle_timeout"
                      value={formData.idle_timeout}
                      onChange={(e) => setFormData({ ...formData, idle_timeout: e.target.value })}
                      className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                      min="0"
                      placeholder="e.g., 600"
                    />
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
                    className="h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500"
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
                  className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingProfile
                      ? 'Update Profile'
                      : 'Create Profile'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
