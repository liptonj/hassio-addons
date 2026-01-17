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
  Eye,
  EyeOff,
  QrCode,
} from 'lucide-react'
import { getDashboardData, getAllSettings } from '../../api/client'
import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'

interface Settings {
  standalone_ssid_name?: string
  default_ssid_psk?: string
  default_guest_group_policy_name?: string
}

export default function Dashboard() {
  const [showPsk, setShowPsk] = useState(false)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardData,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const { data: settingsData } = useQuery({
    queryKey: ['settings'],
    queryFn: getAllSettings,
  })
  
  const settings = settingsData as Settings | undefined

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <span className="loading-spinner w-10 h-10" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center max-w-lg mx-auto my-8">
        <AlertCircle size={48} className="text-error mx-auto mb-4" />
        <h3>Failed to Load Dashboard</h3>
        <p className="text-muted">{(error as Error).message}</p>
      </div>
    )
  }

  const stats = data?.stats
  const recentActivity = data?.recent_activity || []
  const merakiStatus = data?.meraki_status

  const getActivityIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-success" />
      case 'failed':
        return <XCircle size={16} className="text-error" />
      case 'pending':
        return <Clock size={16} className="text-warning" />
      default:
        return <Activity size={16} className="text-info" />
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

      {merakiStatus && (
        <div
          className={`card mb-6 ${
            merakiStatus.status === 'online'
              ? 'border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30'
              : merakiStatus.status === 'offline'
              ? 'border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30'
              : 'border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950/30'
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-2">
              {merakiStatus.status === 'online' ? (
                <CheckCircle size={20} className="text-success" />
              ) : (
                <AlertCircle size={20} className="text-error" />
              )}
              <div>
                <div className="text-sm font-semibold">
                  Meraki API: {merakiStatus.status === 'online' ? 'Connected' : 'Offline'}
                </div>
                <div className="text-xs text-muted">
                  Check your API key and network selection in Settings.
                </div>
              </div>
            </div>
            {merakiStatus.error && (
              <div className="text-xs text-muted max-w-[420px] text-right">
                {merakiStatus.error}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="stats-grid mb-8">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_ipsks || 0}</div>
          <div className="stat-label">Total IPSKs</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-success">
            {stats?.active_ipsks || 0}
          </div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-warning">
            {stats?.expired_ipsks || 0}
          </div>
          <div className="stat-label">Expired</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-error">
            {stats?.revoked_ipsks || 0}
          </div>
          <div className="stat-label">Revoked</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-info">
            {stats?.online_now || 0}
          </div>
          <div className="stat-label">Online Now</div>
        </div>
      </div>

      {/* Guest WiFi Access Card */}
      {settings?.standalone_ssid_name && (
        <div className="card mb-8 bg-gradient-to-r from-meraki-blue-light to-white dark:from-sky-950/40 dark:to-slate-800">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="flex items-center gap-2 mb-4 text-meraki-blue">
                <QrCode size={20} />
                Guest WiFi Access
              </h3>
              
              <div className="space-y-3">
                <div>
                  <div className="text-sm text-muted">Network Name</div>
                  <div className="text-lg font-semibold text-primary">
                    {settings.standalone_ssid_name}
                  </div>
                </div>
                
                <div>
                  <div className="text-sm text-muted">Password</div>
                  {settings.default_ssid_psk ? (
                    <div className="flex items-center gap-2">
                      <div className="text-lg font-mono font-semibold text-primary">
                        {showPsk ? settings.default_ssid_psk : '••••••••••••'}
                      </div>
                      <button
                        onClick={() => setShowPsk(!showPsk)}
                        className="btn-icon-subtle"
                      >
                        {showPsk ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  ) : (
                    <div className="text-sm italic text-muted">
                      <Link to="/admin/settings" className="text-meraki-blue hover:underline">
                        Run WPN wizard
                      </Link> to generate default PSK
                    </div>
                  )}
                </div>

                {settings.default_guest_group_policy_name && (
                  <div>
                    <div className="text-sm text-muted">Guest Policy</div>
                    <div className="text-sm font-medium text-secondary">
                      {settings.default_guest_group_policy_name}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* QR Code */}
            <div className="flex flex-col items-center">
              {settings.default_ssid_psk ? (
                <>
                  <div className="bg-white p-4 rounded-lg shadow-md">
                    <QRCodeSVG
                      value={`WIFI:T:WPA;S:${settings.standalone_ssid_name};P:${settings.default_ssid_psk};;`}
                      size={160}
                      level="M"
                      includeMargin={false}
                    />
                  </div>
                  <div className="text-xs text-center text-muted mt-2 max-w-[160px]">
                    Scan to connect to guest WiFi
                  </div>
                </>
              ) : (
                <div className="bg-surface-tertiary p-4 rounded-lg border-2 border-dashed border-default flex items-center justify-center w-40 h-40">
                  <div className="text-center text-muted">
                    <QrCode size={48} className="mx-auto mb-2 opacity-30" />
                    <div className="text-xs">QR code available<br/>after wizard</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-6 flex-wrap">
        {/* Recent Activity */}
        <div className="card flex-[2] min-w-[300px]">
          <h3 className="flex items-center gap-2 mb-4">
            <Activity size={20} className="text-meraki-blue" />
            Recent Activity
          </h3>
          
          {recentActivity.length === 0 ? (
            <p className="text-muted text-center p-4">No recent activity</p>
          ) : (
            <div className="flex flex-col gap-2">
              {recentActivity.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-center gap-4 p-3 bg-surface-secondary rounded-lg"
                >
                  {getActivityIcon(activity.status)}
                  <div className="flex-1">
                    <div className="font-medium text-primary">{activity.name}</div>
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
        <div className="card flex-1 min-w-[250px]">
          <h3 className="flex items-center gap-2 mb-4">
            <Key size={20} className="text-meraki-blue" />
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

          <div className="mt-6 p-4 text-center bg-accent rounded-lg">
            <div className="text-sm text-muted mb-1">Today's Registrations</div>
            <div className="text-2xl font-bold text-accent">
              {stats?.registrations_today || 0}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
