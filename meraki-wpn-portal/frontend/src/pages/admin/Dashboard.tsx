import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Key,
  Plus,
  Ticket,
  Users,
  Wifi,
  Clock,
  Activity,
  CheckCircle,
  AlertCircle,
  XCircle,
} from 'lucide-react'
import { getDashboardData } from '../../api/client'

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardData,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '400px' }}>
        <span className="loading-spinner" style={{ width: '40px', height: '40px' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center" style={{ maxWidth: '500px', margin: '2rem auto' }}>
        <AlertCircle size={48} color="var(--error)" style={{ margin: '0 auto 1rem' }} />
        <h3>Failed to Load Dashboard</h3>
        <p className="text-muted">{(error as Error).message}</p>
      </div>
    )
  }

  const stats = data?.stats
  const recentActivity = data?.recent_activity || []

  const getActivityIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} color="var(--success)" />
      case 'failed':
        return <XCircle size={16} color="var(--error)" />
      case 'pending':
        return <Clock size={16} color="var(--warning)" />
      default:
        return <Activity size={16} color="var(--info)" />
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1>Dashboard</h1>
        <div className="flex gap-2">
          <Link to="/admin/ipsks" className="btn btn-primary">
            <Plus size={18} /> Create IPSK
          </Link>
          <Link to="/admin/invite-codes" className="btn btn-secondary">
            <Ticket size={18} /> Generate Codes
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid mb-8">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_ipsks || 0}</div>
          <div className="stat-label">Total IPSKs</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--success)' }}>
            {stats?.active_ipsks || 0}
          </div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--warning)' }}>
            {stats?.expired_ipsks || 0}
          </div>
          <div className="stat-label">Expired</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--error)' }}>
            {stats?.revoked_ipsks || 0}
          </div>
          <div className="stat-label">Revoked</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--meraki-teal)' }}>
            {stats?.online_now || 0}
          </div>
          <div className="stat-label">Online Now</div>
        </div>
      </div>

      <div className="flex gap-6" style={{ flexWrap: 'wrap' }}>
        {/* Recent Activity */}
        <div className="card" style={{ flex: '2', minWidth: '300px' }}>
          <h3 className="flex items-center gap-2 mb-4">
            <Activity size={20} style={{ color: 'var(--meraki-blue)' }} />
            Recent Activity
          </h3>
          
          {recentActivity.length === 0 ? (
            <p className="text-muted text-center p-4">No recent activity</p>
          ) : (
            <div className="flex flex-col gap-2">
              {recentActivity.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-center gap-4 p-3"
                  style={{
                    background: 'var(--gray-50)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  {getActivityIcon(activity.status)}
                  <div style={{ flex: 1 }}>
                    <div className="font-medium">{activity.name}</div>
                    <div className="text-sm text-muted">
                      {activity.unit && `Unit ${activity.unit} • `}
                      {activity.type}
                    </div>
                  </div>
                  <span
                    className={`badge badge-${
                      activity.status === 'completed' ? 'success' :
                      activity.status === 'failed' ? 'error' : 'gray'
                    }`}
                  >
                    {activity.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card" style={{ flex: '1', minWidth: '250px' }}>
          <h3 className="flex items-center gap-2 mb-4">
            <Key size={20} style={{ color: 'var(--meraki-blue)' }} />
            Quick Actions
          </h3>
          
          <div className="flex flex-col gap-3">
            <Link to="/admin/ipsks" className="btn btn-secondary btn-full">
              <Wifi size={18} /> Manage IPSKs
            </Link>
            <Link to="/admin/invite-codes" className="btn btn-secondary btn-full">
              <Ticket size={18} /> Invite Codes
            </Link>
            <Link to="/admin/settings" className="btn btn-ghost btn-full">
              <Users size={18} /> View Settings
            </Link>
          </div>

          <div
            className="mt-6 p-4 text-center"
            style={{
              background: 'var(--meraki-blue-light)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div className="text-sm text-muted mb-1">Today's Registrations</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--meraki-blue)' }}>
              {stats?.registrations_today || 0}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
