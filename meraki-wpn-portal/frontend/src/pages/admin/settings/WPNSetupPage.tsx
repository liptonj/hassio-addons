import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { 
  Wifi, 
  CheckCircle, 
  AlertTriangle, 
  Users, 
  Eye, 
  EyeOff,
  RefreshCw,
  Zap,
  X,
  Settings,
  ExternalLink,
} from 'lucide-react'
import { getAllSettings, getIPSKOptions, getWPNSSIDStatus, type WPNSSIDStatus } from '../../../api/client'
import WPNSetup from '../../../components/WPNSetup'

export default function WPNSetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [showWizardDialog, setShowWizardDialog] = useState(false)
  const [ssidStatus, setSsidStatus] = useState<WPNSSIDStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(false)
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'warning'
    message: string
  } | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings-all'],
    queryFn: getAllSettings,
  })

  const { data: ipskOptions } = useQuery({
    queryKey: ['ipsk-options'],
    queryFn: getIPSKOptions,
  })

  const merakiOptions = ipskOptions || { networks: [], ssids: [], group_policies: [] }
  const formData = settings || {}

  // Check prerequisites
  const hasPrerequisites =
    formData.default_network_id &&
    formData.default_ssid_number !== undefined &&
    formData.default_group_policy_id

  // Load SSID status
  const loadSSIDStatus = async () => {
    if (!formData.default_network_id || formData.default_ssid_number === undefined) return
    
    setStatusLoading(true)
    try {
      const status = await getWPNSSIDStatus(formData.default_network_id, formData.default_ssid_number)
      setSsidStatus(status)
    } catch (err) {
      console.error('Failed to load SSID status:', err)
    } finally {
      setStatusLoading(false)
    }
  }

  useEffect(() => {
    if (hasPrerequisites) {
      loadSSIDStatus()
    }
  }, [formData.default_network_id, formData.default_ssid_number])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  // Get status display values
  const getStatusBadge = (status: string | undefined, isGood: boolean) => {
    if (!status) return null
    return (
      <span className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
        isGood 
          ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' 
          : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
      }`}>
        {status}
      </span>
    )
  }

  const getOverallStatusColor = () => {
    if (!ssidStatus) return 'bg-gray-100 dark:bg-gray-800'
    if (ssidStatus.overall_status === 'ready') return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    if (ssidStatus.overall_status === 'config_complete') return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    if (ssidStatus.overall_status === 'needs_wpn') return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
    return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
  }

  const getOverallStatusMessage = () => {
    if (!ssidStatus) return 'Loading...'
    if (ssidStatus.overall_status === 'ready') return 'WPN is fully configured and ready'
    if (ssidStatus.overall_status === 'config_complete') return 'Configuration Complete - All API settings applied successfully'
    if (ssidStatus.overall_status === 'needs_wpn') return 'WPN must be enabled manually in Meraki Dashboard'
    return 'Configuration needed'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">WPN Configuration</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Wi-Fi Personal Network status and configuration
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadSSIDStatus}
            disabled={statusLoading || !hasPrerequisites}
            className="btn btn-secondary"
          >
            <RefreshCw size={16} className={statusLoading ? 'animate-spin' : ''} />
            Refresh Status
          </button>
          {hasPrerequisites && (
            <button
              onClick={() => setShowWizardDialog(true)}
              className="btn btn-primary"
            >
              <Zap size={16} />
              Configure WPN
            </button>
          )}
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            notification.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
              : notification.type === 'warning'
              ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
          }`}
        >
          {notification.type === 'success' && <CheckCircle size={20} />}
          {notification.type === 'warning' && <AlertTriangle size={20} />}
          {notification.type === 'error' && <AlertTriangle size={20} />}
          {notification.message}
        </div>
      )}

      {/* Prerequisites Check */}
      {!hasPrerequisites && (
        <div className="card bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="text-yellow-600 flex-shrink-0 mt-1" />
            <div>
              <h3 className="font-semibold text-yellow-900 dark:text-yellow-100 mb-2">Prerequisites Required</h3>
              <p className="text-sm text-yellow-800 dark:text-yellow-200 mb-3">
                Please complete the following steps before configuring WPN:
              </p>
              <ul className="text-sm text-yellow-800 dark:text-yellow-200 space-y-1 list-disc list-inside">
                {!formData.default_network_id && <li>Select a network</li>}
                {formData.default_ssid_number === undefined && <li>Select an SSID</li>}
                {!formData.default_group_policy_id && <li>Configure group policies</li>}
              </ul>
              <button
                onClick={() => navigate('/admin/settings/network/selection')}
                className="btn btn-secondary mt-3"
              >
                Go to Network Selection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Current SSID Status Card */}
      {hasPrerequisites && (
        <div className={`card border ${getOverallStatusColor()}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
              <Wifi size={20} className="text-meraki-blue" />
              Current SSID Status
            </h3>
            <button
              onClick={loadSSIDStatus}
              disabled={statusLoading}
              className="btn btn-sm btn-secondary"
            >
              <RefreshCw size={14} className={statusLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {/* Overall Status Banner */}
          <div className={`p-3 rounded-lg mb-4 flex items-center gap-2 ${
            ssidStatus?.overall_status === 'ready' || ssidStatus?.overall_status === 'config_complete'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200'
              : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200'
          }`}>
            {ssidStatus?.overall_status === 'ready' || ssidStatus?.overall_status === 'config_complete' ? (
              <CheckCircle size={18} />
            ) : (
              <AlertTriangle size={18} />
            )}
            <span className="font-medium">
              {ssidStatus?.overall_status === 'config_complete' && '✓ '}
              {getOverallStatusMessage()}
            </span>
          </div>

          {/* Status Grid */}
          {ssidStatus && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">SSID Name</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">
                  {ssidStatus.ssid_name || formData.standalone_ssid_name || 'N/A'}
                </div>
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">SSID Enabled</div>
                {getStatusBadge(ssidStatus.enabled ? 'Yes' : 'No', ssidStatus.enabled)}
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Auth Mode</div>
                {getStatusBadge(
                  ssidStatus.auth_mode || 'Unknown',
                  ssidStatus.auth_mode === 'ipsk-without-radius'
                )}
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Identity PSK</div>
                {getStatusBadge(
                  ssidStatus.ipsk_configured ? 'Configured' : 'Not Configured',
                  ssidStatus.ipsk_configured
                )}
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">WPN Status</div>
                {getStatusBadge(
                  ssidStatus.wpn_enabled ? 'Enabled' : 'Manual Enable Required',
                  ssidStatus.wpn_enabled
                )}
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Overall Status</div>
                {getStatusBadge(
                  ssidStatus.overall_status === 'ready' ? 'Ready' :
                  ssidStatus.overall_status === 'config_complete' ? 'Config Complete' :
                  ssidStatus.overall_status === 'needs_wpn' ? 'Needs WPN' : 'Needs Config',
                  ssidStatus.overall_status === 'ready' || ssidStatus.overall_status === 'config_complete'
                )}
              </div>
            </div>
          )}

          {/* Manual Steps Warning */}
          {ssidStatus?.overall_status === 'needs_wpn' || ssidStatus?.overall_status === 'config_complete' ? (
            <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800 dark:text-amber-200">
                  <strong>Manual Steps Required</strong>
                  <p className="mt-1">→ WPN must be enabled manually in Meraki Dashboard (API limitation)</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* WPN Access Configuration Display */}
      {hasPrerequisites &&
        formData.default_group_policy_name &&
        formData.default_ssid_number !== undefined && (
          <div className="card">
            <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
              <Users size={20} className="text-meraki-blue" />
              WPN Access Configuration
            </h3>

            <div className="space-y-4">
              {/* Two-Tier Model */}
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                  Two-Tier Access Model
                </h4>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                      <Users size={14} className="text-green-600 dark:text-green-400" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 dark:text-gray-100">
                        Registered Users
                      </div>
                      <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
                        Use personal iPSK → Assigned to group policy "
                        <strong>{formData.default_group_policy_name}</strong>" → Splash page
                        bypassed → Direct internet access
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-100 dark:bg-yellow-900/50 flex items-center justify-center">
                      <Users size={14} className="text-yellow-600 dark:text-yellow-400" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 dark:text-gray-100">New Guests</div>
                      <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
                        Use default PSK →
                        {formData.default_guest_group_policy_name ? (
                          <>
                            {' '}
                            Assigned to group policy "
                            <strong>{formData.default_guest_group_policy_name}</strong>" →
                          </>
                        ) : (
                          ' No group policy → '
                        )}
                        {' '}
                        See splash page → Register → Receive personal iPSK
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Guest Access Details */}
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                  Guest Access Credentials
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-600 dark:text-gray-400">SSID Name:</span>
                      <span className="font-mono text-gray-900 dark:text-gray-100 font-medium">
                        {formData.standalone_ssid_name ||
                          merakiOptions.ssids.find(
                            (s) => s.number === formData.default_ssid_number
                          )?.name ||
                          'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-600 dark:text-gray-400">
                        Default iPSK Name:
                      </span>
                      <span className="font-mono text-gray-900 dark:text-gray-100 font-medium">
                        Guest-Default-Access
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-600 dark:text-gray-400">Default PSK:</span>
                      <div className="flex items-center gap-2">
                        {formData.default_ssid_psk ? (
                          <>
                            <span className="font-mono text-gray-900 dark:text-gray-100 font-medium">
                              {showSecrets.default_psk
                                ? formData.default_ssid_psk
                                : '••••••••••••'}
                            </span>
                            <button
                              onClick={() =>
                                setShowSecrets((prev) => ({
                                  ...prev,
                                  default_psk: !prev.default_psk,
                                }))
                              }
                              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                            >
                              {showSecrets.default_psk ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          </>
                        ) : (
                          <span className="text-gray-400 italic">Run WPN wizard to generate</span>
                        )}
                      </div>
                    </div>
                    <div className="flex justify-between items-center py-2">
                      <span className="text-gray-600 dark:text-gray-400">Group Policy:</span>
                      <span className="font-medium text-gray-900 dark:text-gray-100">
                        {formData.default_guest_group_policy_name || 'None (uses splash page)'}
                      </span>
                    </div>
                  </div>

                  {/* QR Code */}
                  {formData.default_ssid_psk &&
                    (formData.standalone_ssid_name ||
                      merakiOptions.ssids.find((s) => s.number === formData.default_ssid_number)) && (
                      <div className="flex flex-col items-center justify-center bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="bg-white p-3 rounded-lg shadow-sm">
                          <QRCodeSVG
                            value={`WIFI:T:WPA;S:${
                              formData.standalone_ssid_name ||
                              merakiOptions.ssids.find((s) => s.number === formData.default_ssid_number)
                                ?.name ||
                              ''
                            };P:${formData.default_ssid_psk};;`}
                            size={140}
                            level="M"
                            includeMargin={false}
                          />
                        </div>
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 text-center">
                          Scan to connect to guest WiFi
                        </p>
                      </div>
                    )}
                </div>
              </div>

              {/* Splash Page Info */}
              {formData.splash_page_url && (
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                    Splash Page URL
                  </h4>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-white dark:bg-gray-900 px-3 py-2 rounded border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300">
                      {formData.splash_page_url}
                    </code>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(formData.splash_page_url || '')
                        setNotification({
                          type: 'success',
                          message: 'Splash URL copied to clipboard',
                        })
                        setTimeout(() => setNotification(null), 2000)
                      }}
                      className="btn btn-sm btn-secondary"
                    >
                      Copy
                    </button>
                    <a
                      href={formData.splash_page_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-sm btn-secondary"
                    >
                      <ExternalLink size={14} />
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

      {/* Quick Actions */}
      {hasPrerequisites && (
        <div className="card bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
          <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-3 flex items-center gap-2">
            <Settings size={16} />
            Quick Actions
          </h4>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setShowWizardDialog(true)}
              className="btn btn-primary"
            >
              <Zap size={16} />
              Run WPN Setup Wizard
            </button>
            <button
              onClick={() => navigate('/admin/settings/network/selection')}
              className="btn btn-secondary"
            >
              Change Network/SSID
            </button>
            <button
              onClick={() => navigate('/admin/settings/ssid')}
              className="btn btn-secondary"
            >
              SSID Configuration
            </button>
          </div>
        </div>
      )}

      {/* WPN Wizard Dialog */}
      {showWizardDialog && hasPrerequisites && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Dialog Header */}
            <div className="bg-gradient-to-r from-meraki-blue to-blue-600 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3 text-white">
                <div className="p-2 bg-white/20 rounded-lg">
                  <Zap size={24} />
                </div>
                <div>
                  <h2 className="text-xl font-bold">WPN Quick Setup Wizard</h2>
                  <p className="text-sm text-blue-100">
                    Configure {formData.standalone_ssid_name || 'SSID'} for Wi-Fi Personal Network
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowWizardDialog(false)}
                className="p-2 hover:bg-white/20 rounded-lg transition-colors text-white"
              >
                <X size={24} />
              </button>
            </div>

            {/* Dialog Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6">
              <WPNSetup
                networkId={formData.default_network_id}
                ssidNumber={formData.default_ssid_number}
                ssidName={formData.standalone_ssid_name}
                currentGroupPolicyId={formData.default_group_policy_id}
                cloudflareHostname={formData.cloudflare_hostname}
                cloudflareEnabled={formData.cloudflare_enabled ?? false}
                onConfigured={(result) => {
                  setNotification({
                    type: 'success',
                    message: `SSID configured successfully! ${result.message}`,
                  })
                  queryClient.invalidateQueries({ queryKey: ['settings-all'] })
                  queryClient.invalidateQueries({ queryKey: ['dashboard'] })
                  loadSSIDStatus()
                  setTimeout(() => {
                    setNotification(null)
                  }, 10000)
                }}
                onSettingsChange={() => {
                  queryClient.invalidateQueries({ queryKey: ['settings-all'] })
                }}
              />
            </div>

            {/* Dialog Footer */}
            <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 bg-gray-50 dark:bg-gray-800/50 flex justify-end gap-3">
              <button
                onClick={() => setShowWizardDialog(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
