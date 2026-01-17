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
  Edit,
} from 'lucide-react'
import {
  getUsers,
  createUser,
  toggleUserAdmin,
  deleteUser,
  getPendingUsers,
  approveUser,
  rejectUser,
  type AdminUserInfo,
  type UserCreateRequest,
  type PendingUser,
} from '../../api/client'
import UserEditDialog from '../../components/UserEditDialog'

type TabFilter = 'all' | 'pending' | 'approved'

export default function Users() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [editingUser, setEditingUser] = useState<AdminUserInfo | null>(null)
  const [activeTab, setActiveTab] = useState<TabFilter>('all')
  const [rejectModal, setRejectModal] = useState<PendingUser | null>(null)
  const [rejectNotes, setRejectNotes] = useState('')

  // Fetch all users
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => getUsers(),
  })

  // Fetch pending users
  const { data: pendingData, refetch: refetchPending } = useQuery({
    queryKey: ['pending-users'],
    queryFn: getPendingUsers,
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

  // Approve user mutation
  const approveMutation = useMutation({
    mutationFn: (userId: number) => approveUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['pending-users'] })
    },
  })

  // Reject user mutation
  const rejectMutation = useMutation({
    mutationFn: ({ userId, notes }: { userId: number; notes?: string }) => 
      rejectUser(userId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['pending-users'] })
      setRejectModal(null)
      setRejectNotes('')
    },
  })

  const users = data?.users || []
  const pendingUsers = pendingData?.users || []
  const pendingCount = pendingUsers.length

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-meraki-blue/10">
            <UsersIcon size={24} className="text-meraki-blue" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">User Management</h1>
            <p className="text-sm text-muted">
              {data?.total || 0} users registered
              {pendingCount > 0 && (
                <span className="ml-2 text-amber-600">
                  • {pendingCount} pending approval
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => { refetch(); refetchPending(); }}
            className="btn btn-secondary"
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

      {/* Tab Filter */}
      <div className="flex gap-1 mb-4 border-b border-border">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'all'
              ? 'border-meraki-blue text-meraki-blue'
              : 'border-transparent text-muted hover:text-primary'
          }`}
        >
          All Users
        </button>
        <button
          onClick={() => setActiveTab('pending')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px flex items-center gap-2 ${
            activeTab === 'pending'
              ? 'border-amber-500 text-amber-600'
              : 'border-transparent text-muted hover:text-primary'
          }`}
        >
          Pending Approval
          {pendingCount > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded-full">
              {pendingCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('approved')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'approved'
              ? 'border-green-500 text-green-600'
              : 'border-transparent text-muted hover:text-primary'
          }`}
        >
          Approved
        </button>
      </div>

      {/* Pending Users Table */}
      {activeTab === 'pending' && (
        <div className="card mb-4">
          {pendingUsers.length === 0 ? (
            <div className="text-center py-8 opacity-50">
              No users pending approval
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Unit</th>
                  <th>Auth Method</th>
                  <th>Submitted</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingUsers.map((user: PendingUser) => (
                  <tr key={user.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-semibold">
                          {user.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium text-primary">{user.name}</div>
                          <div className="text-sm text-muted flex items-center gap-1">
                            <Mail size={12} />
                            {user.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="text-sm">{user.unit || '—'}</td>
                    <td className="text-sm capitalize">{user.preferred_auth_method || 'ipsk'}</td>
                    <td className="text-sm text-muted">
                      <div className="flex items-center gap-1">
                        <Calendar size={12} />
                        {user.created_at
                          ? new Date(user.created_at).toLocaleDateString()
                          : '—'}
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => approveMutation.mutate(user.id)}
                          className="btn btn-sm bg-green-500 text-white hover:bg-green-600 flex items-center gap-1"
                          disabled={approveMutation.isPending}
                        >
                          <Check size={14} />
                          Approve
                        </button>
                        <button
                          onClick={() => setRejectModal(user)}
                          className="btn btn-sm bg-red-500 text-white hover:bg-red-600 flex items-center gap-1"
                        >
                          <X size={14} />
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Users Table */}
      {activeTab !== 'pending' && (
      <div className="card">
        {isLoading ? (
          <div className="text-center py-8 opacity-50">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="text-center py-8 opacity-50">
            No users registered yet
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Unit</th>
                <th>Status</th>
                <th>WiFi</th>
                <th>Created</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user: AdminUserInfo) => (
                <tr key={user.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className={user.is_admin ? 'avatar-admin' : 'avatar'}>
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-medium flex items-center gap-2 text-primary">
                          {user.name}
                          {user.is_admin && (
                            <span className="badge-admin">Admin</span>
                          )}
                        </div>
                        <div className="text-sm text-muted flex items-center gap-1">
                          <Mail size={12} />
                          {user.email}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="text-sm">{user.unit || '—'}</td>
                  <td>
                    <span className={user.is_active ? 'status-active' : 'status-inactive'}>
                      {user.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td>
                    {user.has_ipsk ? (
                      <span className="flex items-center gap-1 text-sm text-green-600">
                        <Wifi size={14} />
                        {user.ipsk_name || 'Configured'}
                      </span>
                    ) : (
                      <span className="text-sm text-muted">No iPSK</span>
                    )}
                  </td>
                  <td className="text-sm text-muted">
                    <div className="flex items-center gap-1">
                      <Calendar size={12} />
                      {user.created_at
                        ? new Date(user.created_at).toLocaleDateString()
                        : '—'}
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center justify-end gap-1">
                      {/* Edit */}
                      <button
                        onClick={() => setEditingUser(user)}
                        className="btn-icon-subtle"
                        title="Edit User"
                      >
                        <Edit size={16} />
                      </button>

                      {/* Toggle Admin */}
                      <button
                        onClick={() => toggleAdminMutation.mutate(user.id)}
                        className="btn-icon-subtle"
                        title={user.is_admin ? 'Revoke Admin' : 'Grant Admin'}
                        disabled={toggleAdminMutation.isPending}
                      >
                        {user.is_admin ? (
                          <ShieldOff size={16} className="text-amber-500" />
                        ) : (
                          <Shield size={16} />
                        )}
                      </button>

                      {/* Delete */}
                      {deleteConfirm === user.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => deleteMutation.mutate(user.id)}
                            className="btn-icon-danger bg-red-50"
                            disabled={deleteMutation.isPending}
                          >
                            <Check size={16} className="text-red-500" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="btn-icon-subtle"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirm(user.id)}
                          className="btn-icon-danger"
                          title="Delete User"
                        >
                          <Trash2 size={16} />
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
      )}

      {/* Reject User Modal */}
      {rejectModal && (
        <div className="modal-overlay" onClick={() => setRejectModal(null)}>
          <div className="modal-content max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-primary">Reject User</h2>
              <button onClick={() => setRejectModal(null)} className="btn-icon-subtle">
                <X size={20} />
              </button>
            </div>
            
            <p className="text-sm text-muted mb-4">
              Are you sure you want to reject <strong>{rejectModal.name}</strong>'s registration?
            </p>
            
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">
                Rejection Notes (optional)
              </label>
              <textarea
                value={rejectNotes}
                onChange={(e) => setRejectNotes(e.target.value)}
                className="input w-full"
                rows={3}
                placeholder="Reason for rejection..."
              />
            </div>
            
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setRejectModal(null)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={() => rejectMutation.mutate({ 
                  userId: rejectModal.id, 
                  notes: rejectNotes || undefined 
                })}
                className="btn bg-red-500 text-white hover:bg-red-600"
                disabled={rejectMutation.isPending}
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject User'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}

      {/* Edit User Dialog */}
      {editingUser && (
        <UserEditDialog
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={() => {
            setEditingUser(null)
            refetch()
          }}
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
      className="modal-overlay"
      onClick={onClose}
    >
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-primary">Create New User</h2>
          <button
            onClick={onClose}
            className="btn-icon-subtle"
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="mb-4 alert-error">
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
              className="btn btn-secondary flex-1"
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
