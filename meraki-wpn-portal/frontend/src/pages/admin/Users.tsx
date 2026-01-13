import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users as UsersIcon,
  UserPlus,
  Shield,
  ShieldOff,
  Trash2,
  Wifi,
  Mail,
  Calendar,
  X,
  Check,
  RefreshCw,
} from 'lucide-react'
import {
  getUsers,
  createUser,
  toggleUserAdmin,
  deleteUser,
  type AdminUserInfo,
  type UserCreateRequest,
} from '../../api/client'

export default function Users() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  // Fetch users
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => getUsers(),
  })

  // Create user mutation
  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setShowCreateModal(false)
    },
  })

  // Toggle admin mutation
  const toggleAdminMutation = useMutation({
    mutationFn: toggleUserAdmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
  })

  // Delete user mutation
  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setDeleteConfirm(null)
    },
  })

  const users = data?.users || []

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div
            className="p-2 rounded-lg"
            style={{ background: 'rgba(0, 164, 228, 0.1)' }}
          >
            <UsersIcon size={24} style={{ color: 'var(--meraki-blue)' }} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">User Management</h1>
            <p className="text-sm opacity-70">
              {data?.total || 0} users registered
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="btn"
            style={{ background: 'var(--gray-100)' }}
          >
            <RefreshCw size={18} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <UserPlus size={18} />
            Add User
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="card">
        {isLoading ? (
          <div className="text-center py-8 opacity-50">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="text-center py-8 opacity-50">
            No users registered yet
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr
                className="text-left text-sm"
                style={{ borderBottom: '1px solid var(--gray-200)' }}
              >
                <th className="pb-3 font-medium">User</th>
                <th className="pb-3 font-medium">Unit</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">WiFi</th>
                <th className="pb-3 font-medium">Created</th>
                <th className="pb-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user: AdminUserInfo) => (
                <tr
                  key={user.id}
                  style={{ borderBottom: '1px solid var(--gray-100)' }}
                >
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium"
                        style={{
                          background: user.is_admin
                            ? 'rgba(0, 164, 228, 0.1)'
                            : 'var(--gray-100)',
                          color: user.is_admin
                            ? 'var(--meraki-blue)'
                            : 'var(--gray-600)',
                        }}
                      >
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-medium flex items-center gap-2">
                          {user.name}
                          {user.is_admin && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                background: 'rgba(0, 164, 228, 0.1)',
                                color: 'var(--meraki-blue)',
                              }}
                            >
                              Admin
                            </span>
                          )}
                        </div>
                        <div className="text-sm opacity-60 flex items-center gap-1">
                          <Mail size={12} />
                          {user.email}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 text-sm">{user.unit || '—'}</td>
                  <td className="py-3">
                    <span
                      className="text-xs px-2 py-1 rounded-full"
                      style={{
                        background: user.is_active
                          ? 'rgba(34, 197, 94, 0.1)'
                          : 'rgba(239, 68, 68, 0.1)',
                        color: user.is_active ? '#22c55e' : '#ef4444',
                      }}
                    >
                      {user.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="py-3">
                    {user.has_ipsk ? (
                      <span className="flex items-center gap-1 text-sm text-green-600">
                        <Wifi size={14} />
                        {user.ipsk_name || 'Configured'}
                      </span>
                    ) : (
                      <span className="text-sm opacity-50">No iPSK</span>
                    )}
                  </td>
                  <td className="py-3 text-sm opacity-60">
                    <div className="flex items-center gap-1">
                      <Calendar size={12} />
                      {user.created_at
                        ? new Date(user.created_at).toLocaleDateString()
                        : '—'}
                    </div>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center justify-end gap-1">
                      {/* Toggle Admin */}
                      <button
                        onClick={() => toggleAdminMutation.mutate(user.id)}
                        className="p-2 rounded-lg hover:bg-gray-100"
                        title={user.is_admin ? 'Revoke Admin' : 'Grant Admin'}
                        disabled={toggleAdminMutation.isPending}
                      >
                        {user.is_admin ? (
                          <ShieldOff size={16} style={{ color: '#f59e0b' }} />
                        ) : (
                          <Shield size={16} style={{ color: 'var(--gray-400)' }} />
                        )}
                      </button>

                      {/* Delete */}
                      {deleteConfirm === user.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => deleteMutation.mutate(user.id)}
                            className="p-2 rounded-lg"
                            style={{ background: '#fef2f2' }}
                            disabled={deleteMutation.isPending}
                          >
                            <Check size={16} style={{ color: '#ef4444' }} />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="p-2 rounded-lg hover:bg-gray-100"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirm(user.id)}
                          className="p-2 rounded-lg hover:bg-gray-100"
                          title="Delete User"
                        >
                          <Trash2 size={16} style={{ color: 'var(--gray-400)' }} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}
    </div>
  )
}

// Create User Modal Component
function CreateUserModal({
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  onClose: () => void
  onSubmit: (data: UserCreateRequest) => void
  isLoading: boolean
  error?: string
}) {
  const [formData, setFormData] = useState<UserCreateRequest>({
    email: '',
    name: '',
    password: '',
    unit: '',
    is_admin: false,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0, 0, 0, 0.5)' }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ maxWidth: '400px', width: '100%' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Create New User</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100"
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div
            className="mb-4 p-3 text-sm rounded"
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="John Doe"
              required
              minLength={2}
              className="w-full"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="john@example.com"
              required
              className="w-full"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              placeholder="Minimum 8 characters"
              required
              minLength={8}
              className="w-full"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">Unit (Optional)</label>
            <input
              type="text"
              value={formData.unit}
              onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
              placeholder="e.g., Apt 101"
              className="w-full"
            />
          </div>

          <div className="mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_admin}
                onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
              />
              <span className="text-sm">Grant admin privileges</span>
            </label>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn flex-1"
              style={{ background: 'var(--gray-100)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary flex-1"
              disabled={isLoading}
            >
              {isLoading ? 'Creating...' : 'Create User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
