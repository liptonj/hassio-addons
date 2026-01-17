import { useState, useEffect } from 'react'
import {
  Wifi,
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  ChevronRight,
  ExternalLink,
  Copy,
  RefreshCw,
  Zap,
  Users,
  Globe,
  Key,
} from 'lucide-react'
import {
  getWPNSSIDStatus,
  configureSSIDForWPN,
  validateWPNSetup,
  type WPNSSIDStatus,
  type WPNConfigureResult,
  type WPNValidationResult,
} from '../api/client'

interface WPNSetupProps {
  networkId: string | undefined
  ssidNumber: number | undefined
  ssidName: string | undefined
  currentGroupPolicyId?: string | undefined  // eslint-disable-line @typescript-eslint/no-unused-vars
  cloudflareHostname: string | undefined
  cloudflareEnabled: boolean
  onConfigured?: (result: WPNConfigureResult) => void
  onSettingsChange?: (settings: { group_policy_id?: string; guest_group_policy_id?: string; splash_url?: string }) => void
}

type SetupStep = 'check' | 'configure' | 'apply' | 'complete'

interface StepStatus {
  check: 'pending' | 'loading' | 'success' | 'warning' | 'error'
  configure: 'pending' | 'loading' | 'success' | 'error'
  apply: 'pending' | 'loading' | 'success' | 'error'
  complete: 'pending' | 'success'
}

export default function WPNSetup({
  networkId,
  ssidNumber,
  ssidName,
  currentGroupPolicyId: _currentGroupPolicyId,
  cloudflareHostname,
  cloudflareEnabled,
  onConfigured,
  onSettingsChange,
}: WPNSetupProps) {
  // Note: _currentGroupPolicyId is passed for future use when displaying current selection
  void _currentGroupPolicyId
  const [currentStep, setCurrentStep] = useState<SetupStep>('check')
  const [stepStatus, setStepStatus] = useState<StepStatus>({
    check: 'pending',
    configure: 'pending',
    apply: 'pending',
    complete: 'pending',
  })
  
  // SSID Status
  const [ssidStatus, setSsidStatus] = useState<WPNSSIDStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  
  // Configuration
  const [groupPolicyName, setGroupPolicyName] = useState('WPN-Users')
  const [guestGroupPolicyName, setGuestGroupPolicyName] = useState('WPN-Guests')
  const [splashUrl, setSplashUrl] = useState('')
  const [useCloudflare, setUseCloudflare] = useState(cloudflareEnabled && !!cloudflareHostname)
  
  // Result
  const [configResult, setConfigResult] = useState<WPNConfigureResult | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  
  // Validation
  const [validationResult, setValidationResult] = useState<WPNValidationResult | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  
  // Derived splash URL
  const computedSplashUrl = useCloudflare && cloudflareHostname
    ? `https://${cloudflareHostname}/api/splash`
    : splashUrl || `${window.location.origin}/api/splash`

  // Check if prerequisites are met
  const hasPrerequisites = networkId && ssidNumber !== undefined

  // Load SSID status on mount
  useEffect(() => {
    if (hasPrerequisites && currentStep === 'check') {
      checkSSIDStatus()
    }
  }, [hasPrerequisites])

  // Update splash URL when cloudflare changes
  useEffect(() => {
    if (cloudflareEnabled && cloudflareHostname) {
      setSplashUrl(`https://${cloudflareHostname}/api/splash`)
      setUseCloudflare(true)
    }
  }, [cloudflareEnabled, cloudflareHostname])

  const checkSSIDStatus = async () => {
    setStepStatus(prev => ({ ...prev, check: 'loading' }))
    setStatusError(null)
    
    try {
      const status = await getWPNSSIDStatus()
      setSsidStatus(status)
      
      if (status.wpn_ready) {
        setStepStatus(prev => ({ ...prev, check: 'success' }))
      } else if (status.ipsk_configured) {
        setStepStatus(prev => ({ ...prev, check: 'warning' }))
      } else {
        setStepStatus(prev => ({ ...prev, check: 'warning' }))
      }
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : 'Failed to check SSID status')
      setStepStatus(prev => ({ ...prev, check: 'error' }))
    }
  }

  const runValidation = async () => {
    setIsValidating(true)
    setValidationResult(null)
    
    try {
      const result = await validateWPNSetup()
      setValidationResult(result)
    } catch (error) {
      setValidationResult({
        valid: false,
        checks: [],
        issues: [error instanceof Error ? error.message : 'Validation failed'],
        summary: 'Validation error',
      })
    } finally {
      setIsValidating(false)
    }
  }

  const handleConfigure = async () => {
    setCurrentStep('apply')
    setStepStatus(prev => ({ ...prev, configure: 'success', apply: 'loading' }))
    setConfigError(null)
    
    try {
      const result = await configureSSIDForWPN({
        groupPolicyName,
        guestGroupPolicyName: guestGroupPolicyName || undefined,  // Only include if not empty
        splashUrl: computedSplashUrl,
      })
      setConfigResult(result)
      
      if (result.success) {
        setStepStatus(prev => ({ ...prev, apply: 'success', complete: 'success' }))
        setCurrentStep('complete')
        
        // Notify parent of changes
        if (onConfigured) {
          onConfigured(result)
        }
        if (onSettingsChange) {
          onSettingsChange({
            group_policy_id: result.result?.group_policy_id || undefined,
            guest_group_policy_id: result.guest_group_policy_id || undefined,
            splash_url: result.splash_url,
          })
        }
      } else {
        setStepStatus(prev => ({ ...prev, apply: 'error' }))
        setConfigError('Configuration failed')
      }
    } catch (error) {
      setConfigError(error instanceof Error ? error.message : 'Failed to configure SSID')
      setStepStatus(prev => ({ ...prev, apply: 'error' }))
    }
  }


  const getStepIcon = (step: keyof StepStatus, size = 20) => {
    const status = stepStatus[step]
    switch (status) {
      case 'loading':
        return <Loader2 size={size} className="animate-spin text-meraki-blue" />
      case 'success':
        return <CheckCircle size={size} className="text-green-500" />
      case 'warning':
        return <AlertTriangle size={size} className="text-yellow-500" />
      case 'error':
        return <XCircle size={size} className="text-red-500" />
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
    }
  }

  // Render step indicator
  const StepIndicator = () => (
    <div className="flex items-center justify-between mb-8 px-4">
      {(['check', 'configure', 'apply', 'complete'] as SetupStep[]).map((step, index) => (
        <div key={step} className="flex items-center">
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all ${
              currentStep === step
                ? 'border-meraki-blue bg-meraki-blue/10'
                : stepStatus[step] === 'success'
                ? 'border-green-500 bg-green-50'
                : stepStatus[step] === 'error'
                ? 'border-red-500 bg-red-50'
                : 'border-gray-300 bg-white'
            }`}
          >
            {stepStatus[step] !== 'pending' ? (
              getStepIcon(step, 18)
            ) : (
              <span className="text-sm font-semibold text-gray-500">{index + 1}</span>
            )}
          </div>
          {index < 3 && (
            <ChevronRight size={20} className="mx-2 text-gray-300" />
          )}
        </div>
      ))}
    </div>
  )

  // Render no prerequisites message
  if (!hasPrerequisites) {
    return (
      <div className="bg-gradient-to-br from-yellow-50 to-orange-50 border border-yellow-200 rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-yellow-100 rounded-lg">
            <AlertTriangle size={24} className="text-yellow-600" />
          </div>
          <div>
            <h3 className="font-semibold text-yellow-900 mb-2">Prerequisites Required</h3>
            <p className="text-yellow-800 text-sm mb-4">
              Before setting up WPN, please configure the following:
            </p>
            <ul className="space-y-2 text-sm text-yellow-800">
              <li className="flex items-center gap-2">
                {networkId ? (
                  <CheckCircle size={16} className="text-green-500" />
                ) : (
                  <XCircle size={16} className="text-red-500" />
                )}
                Select a <strong>Network</strong> above
              </li>
              <li className="flex items-center gap-2">
                {ssidNumber !== undefined ? (
                  <CheckCircle size={16} className="text-green-500" />
                ) : (
                  <XCircle size={16} className="text-red-500" />
                )}
                Select an <strong>SSID</strong> to configure
              </li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-br from-slate-50 to-blue-50 border border-slate-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-meraki-blue to-blue-600 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/20 rounded-lg">
            <Zap size={24} className="text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">WPN Quick Setup Wizard</h3>
            <p className="text-blue-100 text-sm">
              Configure {ssidName || `SSID ${ssidNumber}`} for Wi-Fi Personal Network
            </p>
          </div>
        </div>
      </div>

      <div className="p-6">
        <StepIndicator />

        {/* Step 1: Check Status */}
        {currentStep === 'check' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-semibold text-slate-800 flex items-center gap-2">
                  <Wifi size={20} className="text-meraki-blue" />
                  Current SSID Status
                </h4>
                <button
                  onClick={checkSSIDStatus}
                  disabled={stepStatus.check === 'loading'}
                  className="btn btn-secondary btn-sm"
                >
                  <RefreshCw size={16} className={stepStatus.check === 'loading' ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>

              {statusError ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-red-700">{statusError}</p>
                </div>
              ) : ssidStatus ? (
                <div className="space-y-3">
                  {/* Overall Status Banner */}
                  {ssidStatus.configuration_complete && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <div className="flex items-center gap-2">
                        <CheckCircle size={18} className="text-green-600" />
                        <span className="text-sm font-medium text-green-800">
                          ✓ Configuration Complete - All API settings applied successfully
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <StatusItem
                      label="SSID Name"
                      value={ssidStatus.ssid_name}
                      status="neutral"
                    />
                    <StatusItem
                      label="SSID Enabled"
                      value={ssidStatus.enabled ? 'Yes' : 'No'}
                      status={ssidStatus.enabled ? 'success' : 'error'}
                    />
                    <StatusItem
                      label="Auth Mode"
                      value={ssidStatus.auth_mode || 'Not Set'}
                      status={ssidStatus.ipsk_configured ? 'success' : 'warning'}
                    />
                    <StatusItem
                      label="Identity PSK"
                      value={ssidStatus.ipsk_configured ? 'Configured' : 'Not Configured'}
                      status={ssidStatus.ipsk_configured ? 'success' : 'warning'}
                    />
                    <StatusItem
                      label="WPN Status"
                      value={ssidStatus.wpn_enabled ? 'Enabled' : 'Manual Enable Required'}
                      status={ssidStatus.wpn_enabled ? 'success' : 'neutral'}
                    />
                    <StatusItem
                      label="Overall Status"
                      value={
                        ssidStatus.wpn_ready ? 'Fully Ready' : 
                        ssidStatus.configuration_complete ? 'Config Complete' : 
                        'Needs Configuration'
                      }
                      status={
                        ssidStatus.wpn_ready ? 'success' : 
                        ssidStatus.configuration_complete ? 'success' : 
                        'warning'
                      }
                    />
                  </div>

                  {ssidStatus.issues && ssidStatus.issues.length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
                      <h5 className="font-medium text-red-800 mb-2 flex items-center gap-2">
                        <XCircle size={16} />
                        Critical Issues
                      </h5>
                      <ul className="space-y-1 text-sm text-red-700">
                        {ssidStatus.issues.map((issue, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span>•</span>
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {ssidStatus.warnings && ssidStatus.warnings.length > 0 && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
                      <h5 className="font-medium text-blue-800 mb-2 flex items-center gap-2">
                        <AlertTriangle size={16} />
                        Manual Steps Required
                      </h5>
                      <ul className="space-y-1 text-sm text-blue-700">
                        {ssidStatus.warnings.map((warning, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span>→</span>
                            <span>{warning}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={32} className="animate-spin text-meraki-blue" />
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setCurrentStep('configure')}
                disabled={stepStatus.check === 'loading'}
                className="btn btn-primary"
              >
                Continue to Configure
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Configure */}
        {currentStep === 'configure' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <h4 className="font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <Shield size={20} className="text-meraki-blue" />
                WPN Configuration Options
              </h4>

              <div className="space-y-5">
                {/* Group Policy for Registered Users */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    <Users size={16} className="inline mr-2" />
                    Registered Users Group Policy
                  </label>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={groupPolicyName}
                      onChange={(e) => setGroupPolicyName(e.target.value)}
                      className="input flex-1"
                      placeholder="e.g., WPN-Users"
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    <strong>Splash bypass enabled</strong> - Users with iPSKs will bypass the splash page and get direct internet access.
                  </p>
                </div>

                {/* Group Policy for Guest/Default Users */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    <Users size={16} className="inline mr-2" />
                    Guest/Default Users Group Policy (Optional)
                  </label>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={guestGroupPolicyName}
                      onChange={(e) => setGuestGroupPolicyName(e.target.value)}
                      className="input flex-1"
                      placeholder="e.g., WPN-Guests (leave empty for splash page only)"
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    <strong>Optional:</strong> Group policy for users connecting with the default PSK. 
                    Leave empty to only use splash page. If set, splash page will still be shown but users get this group policy.
                  </p>
                </div>

                {/* Info about Guest Users */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h5 className="font-medium text-blue-800 mb-2 flex items-center gap-2">
                    <Users size={16} />
                    Guest/Default User Behavior
                  </h5>
                  <p className="text-sm text-blue-700">
                    Users <strong>without</strong> an iPSK will use the default PSK and see the splash page.
                    After registration, they'll receive their own personal iPSK and automatically join the registered users group policy.
                  </p>
                </div>

                {/* Splash URL */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    <Globe size={16} className="inline mr-2" />
                    Splash Page URL
                  </label>
                  
                  {cloudflareEnabled && cloudflareHostname && (
                    <div className="mb-3">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={useCloudflare}
                          onChange={(e) => setUseCloudflare(e.target.checked)}
                          className="w-4 h-4 rounded border-slate-300 text-meraki-blue focus:ring-meraki-blue"
                        />
                        <span className="text-sm text-slate-700">
                          Use Cloudflare Tunnel URL (recommended)
                        </span>
                      </label>
                    </div>
                  )}
                  
                  <input
                    type="text"
                    value={useCloudflare ? `https://${cloudflareHostname}/api/splash` : splashUrl}
                    onChange={(e) => {
                      if (!useCloudflare) setSplashUrl(e.target.value)
                    }}
                    disabled={useCloudflare}
                    className={`input w-full ${useCloudflare ? 'bg-slate-50' : ''}`}
                    placeholder="https://your-portal.com/api/splash"
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    {useCloudflare
                      ? '✓ Using your configured Cloudflare hostname for reliable external access.'
                      : 'URL where unregistered users will be redirected for registration.'}
                  </p>
                </div>

                {/* What Will Be Configured */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h5 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                    <Zap size={16} />
                    What Will Be Configured
                  </h5>
                  <ul className="space-y-2 text-sm text-blue-700">
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Enable SSID with <strong>Identity PSK without RADIUS</strong>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Set encryption to <strong>WPA2 only</strong>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Enable <strong>Bridge mode</strong> (required for WPN)
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Enable <strong>Click-through splash page</strong> for guest access
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Configure splash URL: <code className="bg-blue-100 px-1 rounded text-xs">{computedSplashUrl}</code>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      {_currentGroupPolicyId ? (
                        <>
                          <strong>Update</strong> group policy "<strong>{groupPolicyName}</strong>" with splash bypass
                        </>
                      ) : (
                        <>
                          <strong>Create</strong> group policy "<strong>{groupPolicyName}</strong>" with splash bypass
                        </>
                      )}
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-blue-500" />
                      Generate <strong>simple, easy-to-type default PSK</strong> for initial guest access
                    </li>
                  </ul>
                  
                  <div className="mt-4 pt-4 border-t border-blue-200">
                    <h6 className="font-medium text-blue-800 mb-2">Two-Tier Access Model:</h6>
                    <div className="space-y-2 text-xs">
                      <div className="flex items-start gap-2">
                        <Users size={14} className="text-blue-600 mt-0.5" />
                        <div>
                          <strong>Registered Users</strong>: Personal iPSK → Group policy with splash bypass → Direct internet
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <Users size={14} className="text-blue-600 mt-0.5" />
                        <div>
                          <strong>New Guests</strong>: Default PSK → Splash page → Registration → Personal iPSK
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Manual Step Warning */}
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <h5 className="font-medium text-amber-800 mb-2 flex items-center gap-2">
                    <AlertTriangle size={16} />
                    Manual Step Required
                  </h5>
                  <p className="text-sm text-amber-700">
                    After configuration, you must <strong>manually enable WPN</strong> in the Meraki Dashboard.
                    The API does not support enabling WPN directly.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex justify-between">
              <button
                onClick={() => setCurrentStep('check')}
                className="btn btn-secondary"
              >
                Back
              </button>
              <button
                onClick={handleConfigure}
                className="btn btn-primary"
              >
                Apply Configuration
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Apply */}
        {currentStep === 'apply' && stepStatus.apply === 'loading' && (
          <div className="bg-white rounded-lg border border-slate-200 p-8">
            <div className="flex flex-col items-center justify-center py-8">
              <Loader2 size={48} className="animate-spin text-meraki-blue mb-4" />
              <h4 className="text-lg font-semibold text-slate-800 mb-2">
                Configuring SSID...
              </h4>
              <p className="text-slate-600 text-center max-w-md">
                Setting up Identity PSK, splash page, and group policy.
                This may take a few seconds.
              </p>
            </div>
          </div>
        )}

        {/* Error State */}
        {currentStep === 'apply' && stepStatus.apply === 'error' && (
          <div className="space-y-6">
            <div className="bg-red-50 border border-red-200 rounded-lg p-5">
              <div className="flex items-start gap-4">
                <XCircle size={24} className="text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-red-800 mb-2">Configuration Failed</h4>
                  <p className="text-red-700">{configError}</p>
                </div>
              </div>
            </div>
            <div className="flex justify-between">
              <button
                onClick={() => setCurrentStep('configure')}
                className="btn btn-secondary"
              >
                Back to Configure
              </button>
              <button
                onClick={handleConfigure}
                className="btn btn-primary"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Complete */}
        {currentStep === 'complete' && configResult && (
          <div className="space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-5">
              <div className="flex items-start gap-4">
                <CheckCircle size={24} className="text-green-500 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-green-800 mb-2">
                    SSID Configured Successfully!
                  </h4>
                  <p className="text-green-700">
                    {configResult.result?.ssid?.name || ssidName} is now configured for WPN.
                  </p>
                </div>
              </div>
            </div>

            {/* Configuration Summary */}
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <h4 className="font-semibold text-slate-800 mb-4">Configuration Summary</h4>
              <div className="space-y-4">
                {/* Success Banner */}
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <CheckCircle size={20} className="text-green-600 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-green-800">
                        {configResult.message || 'Configuration completed successfully!'}
                      </p>
                      {configResult.group_policy_action && (
                        <p className="text-sm text-green-700 mt-1">
                          Group policy <strong>{configResult.group_policy_name}</strong> was{' '}
                          <strong>{configResult.group_policy_action}</strong>
                          {configResult.splash_bypass_enabled && ' with splash bypass enabled for registered users.'}
                        </p>
                      )}
                      {configResult.default_ipsk_created && (
                        <p className="text-sm text-green-700 mt-1">
                          ✓ Default guest iPSK created in Meraki Dashboard as <strong>"Guest-Default-Access"</strong>
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <SummaryItem label="SSID" value={configResult.result?.ssid?.name || 'N/A'} />
                  <SummaryItem label="Auth Mode" value={configResult.result?.ssid?.authMode || 'N/A'} />
                  <SummaryItem label="Encryption" value={configResult.result?.ssid?.wpaEncryptionMode || 'N/A'} />
                  <SummaryItem label="Group Policy" value={configResult.group_policy_name || 'N/A'} />
                  <SummaryItem 
                    label="Group Policy ID" 
                    value={configResult.result?.group_policy_id || 'N/A'} 
                    copyable 
                  />
                  <SummaryItem 
                    label="Splash URL" 
                    value={configResult.splash_url || 'N/A'} 
                    copyable 
                  />
                  <SummaryItem 
                    label="Default PSK" 
                    value={configResult.default_psk || 'N/A'} 
                    copyable 
                    sensitive 
                  />
                  {configResult.group_policy_action && (
                    <SummaryItem 
                      label="Policy Action" 
                      value={configResult.group_policy_action === 'updated' ? '✓ Updated Existing' : '✓ Created New'} 
                    />
                  )}
                  {configResult.default_ipsk_created !== undefined && (
                    <SummaryItem 
                      label="Guest iPSK" 
                      value={configResult.default_ipsk_created ? '✓ Created in Meraki' : '✓ Already Exists'} 
                    />
                  )}
                </div>
              </div>
            </div>

            {/* Validation Section */}
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-semibold text-slate-800 flex items-center gap-2">
                  <Shield size={20} className="text-meraki-blue" />
                  Setup Validation
                </h4>
                <button
                  onClick={runValidation}
                  disabled={isValidating}
                  className="btn btn-secondary btn-sm"
                >
                  {isValidating ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Validating...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={16} />
                      Run Validation
                    </>
                  )}
                </button>
              </div>
              
              {validationResult ? (
                <div className="space-y-3">
                  <div className={`p-3 rounded-lg ${
                    validationResult.valid 
                      ? 'bg-green-50 border border-green-200' 
                      : 'bg-yellow-50 border border-yellow-200'
                  }`}>
                    <p className={`font-medium ${
                      validationResult.valid ? 'text-green-800' : 'text-yellow-800'
                    }`}>
                      {validationResult.summary}
                    </p>
                  </div>
                  
                  {validationResult.checks.length > 0 && (
                    <div className="space-y-2">
                      {validationResult.checks.map((check, i) => (
                        <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
                          <span className="text-sm text-slate-700">{check.name}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-slate-600">{check.value}</span>
                            {check.passed ? (
                              <CheckCircle size={16} className="text-green-500" />
                            ) : (
                              <XCircle size={16} className="text-yellow-500" />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {validationResult.issues.length > 0 && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mt-3">
                      <p className="font-medium text-yellow-800 mb-2">Issues to Address:</p>
                      <ul className="text-sm text-yellow-700 space-y-1">
                        {validationResult.issues.map((issue, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span>•</span>
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  Click "Run Validation" to verify your WPN setup is complete and working correctly.
                </p>
              )}
            </div>

            {/* Manual Step */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-5">
              <h4 className="font-semibold text-amber-800 mb-3 flex items-center gap-2">
                <AlertTriangle size={20} />
                Final Step: Enable WPN in Meraki Dashboard
              </h4>
              <ol className="space-y-2 text-sm text-amber-800 list-decimal ml-5">
                <li>Go to <strong>Meraki Dashboard</strong></li>
                <li>Navigate to <strong>Wireless → Access Control</strong></li>
                <li>Select your SSID: <strong>{configResult.result?.ssid?.name || ssidName}</strong></li>
                <li>Find <strong>Wi-Fi Personal Network (WPN)</strong> section</li>
                <li>Toggle <strong>Enable</strong></li>
              </ol>
              <a
                href="https://dashboard.meraki.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 mt-4 text-amber-700 hover:text-amber-900 font-medium"
              >
                Open Meraki Dashboard
                <ExternalLink size={16} />
              </a>
            </div>

            <div className="flex justify-between">
              <button
                onClick={() => {
                  setCurrentStep('check')
                  setStepStatus({
                    check: 'pending',
                    configure: 'pending',
                    apply: 'pending',
                    complete: 'pending',
                  })
                  setConfigResult(null)
                }}
                className="btn btn-secondary"
              >
                Start Over
              </button>
              <button
                onClick={() => window.location.reload()}
                className="btn btn-primary"
              >
                Refresh Settings
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Helper Components
function StatusItem({
  label,
  value,
  status,
}: {
  label: string
  value: string
  status: 'success' | 'warning' | 'error' | 'neutral'
}) {
  const statusColors = {
    success: 'text-green-700 bg-green-50 border-green-200',
    warning: 'text-yellow-700 bg-yellow-50 border-yellow-200',
    error: 'text-red-700 bg-red-50 border-red-200',
    neutral: 'text-slate-700 bg-slate-50 border-slate-200',
  }

  return (
    <div className={`rounded-lg border p-3 ${statusColors[status]}`}>
      <div className="text-xs font-medium opacity-70">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}

function SummaryItem({
  label,
  value,
  copyable = false,
  sensitive = false,
}: {
  label: string
  value: string
  copyable?: boolean
  sensitive?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const [revealed, setRevealed] = useState(!sensitive)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100">
      <span className="text-slate-600">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-medium text-slate-800">
          {sensitive && !revealed ? '••••••••' : value}
        </span>
        {sensitive && (
          <button
            onClick={() => setRevealed(!revealed)}
            className="text-slate-400 hover:text-slate-600"
          >
            <Key size={14} />
          </button>
        )}
        {copyable && value !== 'N/A' && (
          <button
            onClick={handleCopy}
            className="text-slate-400 hover:text-slate-600"
          >
            {copied ? <CheckCircle size={14} className="text-green-500" /> : <Copy size={14} />}
          </button>
        )}
      </div>
    </div>
  )
}
