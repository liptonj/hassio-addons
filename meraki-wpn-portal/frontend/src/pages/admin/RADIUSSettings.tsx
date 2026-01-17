import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { 
  RefreshCw,
  Shield,
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Download,
  Cpu
} from 'lucide-react'
import api from '../../api/client'

export default function RADIUSSettings() {
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: configStatus, isLoading } = useQuery({
    queryKey: ['radius-config'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/config')
      return data
    },
  })

  const { data: stats } = useQuery({
    queryKey: ['radius-stats'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/freeradius/stats')
      return data
    },
  })

  const { data: health } = useQuery({
    queryKey: ['radius-health'],
    queryFn: async () => {
      const { data } = await api.get('/admin/radius/freeradius/health')
      return data
    },
    refetchInterval: 30000, // Refresh every 30s
    retry: false,
  })

  const generateCertsMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/admin/radius/certificates/generate', {
        hostname: 'FreeRADIUS Server',
      })
      return data
    },
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'RadSec certificates generated successfully',
      })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message,
      })
    },
  })

  const syncMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/admin/radius/reload', { force: true })
      return data
    },
    onSuccess: (data) => {
      setNotification({
        type: 'success',
        message: data.message || 'Configuration reloaded successfully',
      })
      setTimeout(() => setNotification(null), 5000)
    },
    onError: (error: Error) => {
      setNotification({
        type: 'error',
        message: error.message,
      })
    },
  })

  const handleGenerateCerts = () => {
    if (window.confirm('Generate new RadSec certificates? This will replace existing certificates.')) {
      generateCertsMutation.mutate()
    }
  }

  const handleSync = () => {
    syncMutation.mutate()
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
          <h1 className="text-2xl font-bold">RADIUS Configuration</h1>
          <p className="text-sm text-gray-600 mt-1">
            Configure FreeRADIUS server for MAC-based authentication and WPN
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn btn-secondary"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            <RefreshCw size={16} className={syncMutation.isPending ? 'animate-spin' : ''} />
            {syncMutation.isPending ? 'Reloading...' : 'Reload Config'}
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
          <span className="whitespace-pre-wrap">{notification.message}</span>
        </div>
      )}

      {/* FreeRADIUS Status */}
      {health && (
        <div className="card">
          <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
            <Activity size={20} className="text-meraki-blue" />
            FreeRADIUS Status
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatusIndicator
              label="RADIUS Server"
              status={health.radius_running ? 'healthy' : 'error'}
              value={health.radius_running ? 'Running' : 'Stopped'}
            />
            <StatusIndicator
              label="Portal DB"
              status={health.portal_db_connected ? 'healthy' : 'warning'}
              value={health.portal_db_connected ? 'Connected' : 'Disconnected'}
            />
            <StatusIndicator
              label="Config Files"
              status={health.config_files_exist ? 'healthy' : 'warning'}
              value={health.config_files_exist ? 'Present' : 'Missing'}
            />
            <StatusIndicator
              label="Overall"
              status={health.status as 'healthy' | 'warning' | 'error'}
              value={health.status.charAt(0).toUpperCase() + health.status.slice(1)}
            />
          </div>
        </div>
      )}

      {/* RADIUS Server Statistics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <div className="text-sm text-gray-600 dark:text-slate-400">Total Clients</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-sky-300">{stats.total_clients}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-600 dark:text-slate-400">Active Clients</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-sky-300">{stats.active_clients}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-600 dark:text-slate-400">UDN Utilization</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-sky-300">{stats.udn_utilization_percent.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* RADIUS Server Configuration Status */}
      <div className="card">
        <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
          <Shield size={20} className="text-meraki-blue dark:text-sky-400" />
          Configuration Status
        </h3>
        <p className="text-sm text-gray-600 dark:text-slate-400 mb-3">
          Configuration values are managed by the FreeRADIUS service. Use the Settings page for portal-side defaults.
        </p>
        <pre className="text-xs bg-gray-50 dark:bg-slate-900/50 dark:text-slate-300 dark:border dark:border-slate-700/50 p-4 rounded-lg overflow-auto">
          {JSON.stringify(configStatus ?? {}, null, 2)}
        </pre>
      </div>

      {/* RadSec Configuration */}
      <div className="card">
        <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold">
          <Shield size={20} className="text-meraki-blue" />
          RadSec (RADIUS over TLS)
        </h3>

        <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/40 rounded-lg">
          <p className="text-sm text-blue-900 dark:text-blue-300 mb-3">
            <strong>Certificate Management:</strong> RadSec requires CA and server certificates for secure communication.
          </p>
          <div className="flex gap-2 flex-wrap">
            <button
              className="btn btn-secondary text-sm"
              onClick={handleGenerateCerts}
              disabled={generateCertsMutation.isPending}
            >
              <Cpu size={16} />
              {generateCertsMutation.isPending ? 'Generating...' : 'Generate Certificates'}
            </button>
            <button
              className="btn btn-secondary text-sm"
              disabled
            >
              <Download size={16} />
              Download CA Certificate
            </button>
          </div>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/40">
          <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2 flex items-center gap-2">
            <Shield size={18} />
            About RADIUS Integration
          </h4>
          <p className="text-sm text-blue-800 dark:text-blue-300">
            RADIUS enables MAC-based authentication for devices. When enabled, devices are authenticated
            using their MAC address and assigned a UDN ID for WPN segmentation.
          </p>
        </div>

        <div className="card bg-green-50 dark:bg-emerald-950/30 border border-green-200 dark:border-emerald-800/40">
          <h4 className="font-semibold text-green-900 dark:text-emerald-300 mb-2 flex items-center gap-2">
            <CheckCircle size={18} />
            Setup Checklist
          </h4>
          <ul className="text-sm text-green-800 dark:text-emerald-300 space-y-1">
            <li className="flex items-center gap-2">
              <span className={health?.radius_running ? 'text-green-600' : 'text-gray-400'}>✓</span>
              FreeRADIUS Running
            </li>
            <li className="flex items-center gap-2">
              Generate Certificates
            </li>
            <li className="flex items-center gap-2">
              <span className={health?.radius_running ? 'text-green-600' : 'text-gray-400'}>✓</span>
              Check Health
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function StatusIndicator({
  label,
  status,
  value,
}: {
  label: string
  status: 'healthy' | 'warning' | 'error'
  value: string
}) {
  const colors = {
    healthy: 'bg-green-100 text-green-800 border-green-200',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    error: 'bg-red-100 text-red-800 border-red-200',
  }

  const icons = {
    healthy: <CheckCircle size={16} />,
    warning: <AlertTriangle size={16} />,
    error: <XCircle size={16} />,
  }

  return (
    <div className={`p-3 rounded-lg border ${colors[status]}`}>
      <div className="flex items-center gap-2 mb-1">
        {icons[status]}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-sm font-semibold">{value}</div>
    </div>
  )
}
