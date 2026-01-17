import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Wifi, User, Mail, Ticket, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { validateInviteCode, register, getPortalOptions } from '../../api/client'
import type { RegistrationRequest } from '../../types/user'
import { getUserAgent } from '../../utils/deviceDetection'

type Step = 'code' | 'form' | 'success' | 'pending'

export default function InviteCode() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  
  // Get invite code from URL if provided
  const codeFromQuery = searchParams.get('code') || ''
  const clientMac = searchParams.get('mac') || ''
  
  // State
  const [step, setStep] = useState<Step>('code')
  const [inviteCode, setInviteCode] = useState(codeFromQuery.toUpperCase())
  const [codeError, setCodeError] = useState('')
  const [codeInfo, setCodeInfo] = useState<{
    max_uses: number
    uses: number
    remaining_uses: number
    expires_at?: string
    note?: string
  } | null>(null)
  
  // Form data for minimal registration
  const [formData, setFormData] = useState<RegistrationRequest>({
    name: '',
    email: '',
    invite_code: inviteCode,
    mac_address: clientMac || undefined,
    user_agent: getUserAgent(),
    auth_method: 'ipsk',
  })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  
  // Registration result
  const [credentials, setCredentials] = useState<{
    ssid_name: string
    passphrase?: string
    qr_code?: string
    pending_approval?: boolean
    pending_message?: string
  } | null>(null)

  const { data: options } = useQuery({
    queryKey: ['portal-options'],
    queryFn: getPortalOptions,
  })

  // Validate code mutation
  const validateMutation = useMutation({
    mutationFn: (code: string) => validateInviteCode(code),
    onSuccess: (data) => {
      if (data.valid) {
        setCodeError('')
        setCodeInfo(data.code_info || null)
        setFormData(prev => ({ ...prev, invite_code: inviteCode }))
        setStep('form')
      } else {
        setCodeError(data.error || 'Invalid invite code')
        setCodeInfo(null)
      }
    },
    onError: (error: Error) => {
      setCodeError(error.message || 'Failed to validate code')
    },
  })

  // Registration mutation
  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: (data) => {
      if (data.pending_approval) {
        setCredentials({
          ssid_name: data.ssid_name,
          pending_approval: true,
          pending_message: data.pending_message,
        })
        setStep('pending')
      } else {
        setCredentials({
          ssid_name: data.ssid_name,
          passphrase: data.passphrase || undefined,
          qr_code: data.qr_code || undefined,
        })
        setStep('success')
      }
    },
    onError: (error: Error) => {
      setFormErrors({ submit: error.message || 'Registration failed' })
    },
  })

  const handleValidateCode = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteCode.trim()) {
      setCodeError('Please enter an invite code')
      return
    }
    validateMutation.mutate(inviteCode.trim())
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    
    if (!formData.name?.trim()) {
      errors.name = 'Name is required'
    }
    if (!formData.email?.trim()) {
      errors.email = 'Email is required'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Please enter a valid email'
    }
    
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }
    
    setFormErrors({})
    registerMutation.mutate(formData)
  }

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
    setInviteCode(value)
    setCodeError('')
  }

  // Step 1: Enter invite code
  if (step === 'code') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 mb-4">
              <Ticket className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">
              {options?.property_name || 'WiFi Access'}
            </h1>
            <p className="text-slate-400">
              Enter your invite code to get WiFi access
            </p>
          </div>

          {/* Code Entry Form */}
          <form onSubmit={handleValidateCode} className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Invite Code
              </label>
              <div className="relative">
                <Ticket className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="text"
                  value={inviteCode}
                  onChange={handleCodeChange}
                  placeholder="XXXXXX"
                  autoFocus
                  className={`
                    w-full pl-11 pr-4 py-3 rounded-xl text-center text-2xl font-mono tracking-widest
                    bg-slate-900/50 border transition-colors
                    ${codeError ? 'border-red-500' : 'border-slate-600 focus:border-emerald-500'}
                    text-white placeholder-slate-500
                    focus:outline-none focus:ring-2 focus:ring-emerald-500/20
                  `}
                  maxLength={20}
                />
              </div>
              {codeError && (
                <div className="flex items-center gap-2 mt-2 text-red-400 text-sm">
                  <XCircle className="w-4 h-4" />
                  <span>{codeError}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={validateMutation.isPending || !inviteCode.trim()}
              className={`
                w-full py-3 rounded-xl font-semibold text-white
                transition-all duration-200
                ${validateMutation.isPending || !inviteCode.trim()
                  ? 'bg-slate-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 shadow-lg shadow-emerald-500/25'
                }
              `}
            >
              {validateMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Validating...
                </span>
              ) : (
                'Continue'
              )}
            </button>
          </form>

          {/* Link to regular registration */}
          <div className="mt-6 text-center">
            <button
              onClick={() => navigate('/register')}
              className="text-slate-400 hover:text-white transition-colors text-sm"
            >
              Don't have a code? Register here →
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Step 2: Minimal registration form
  if (step === 'form') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 mb-4">
              <Wifi className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">
              Almost There!
            </h1>
            <p className="text-slate-400">
              Just a few details to get you connected
            </p>
            {codeInfo && (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full text-sm">
                <CheckCircle className="w-4 h-4" />
                Code: {inviteCode}
              </div>
            )}
          </div>

          {/* Registration Form */}
          <form onSubmit={handleSubmit} className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
            {formErrors.submit && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-xl text-red-400 text-sm">
                {formErrors.submit}
              </div>
            )}

            {/* Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="John Smith"
                  className={`
                    w-full pl-11 pr-4 py-3 rounded-xl
                    bg-slate-900/50 border transition-colors
                    ${formErrors.name ? 'border-red-500' : 'border-slate-600 focus:border-emerald-500'}
                    text-white placeholder-slate-500
                    focus:outline-none focus:ring-2 focus:ring-emerald-500/20
                  `}
                />
              </div>
              {formErrors.name && (
                <p className="mt-1 text-red-400 text-sm">{formErrors.name}</p>
              )}
            </div>

            {/* Email */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="john@example.com"
                  className={`
                    w-full pl-11 pr-4 py-3 rounded-xl
                    bg-slate-900/50 border transition-colors
                    ${formErrors.email ? 'border-red-500' : 'border-slate-600 focus:border-emerald-500'}
                    text-white placeholder-slate-500
                    focus:outline-none focus:ring-2 focus:ring-emerald-500/20
                  `}
                />
              </div>
              {formErrors.email && (
                <p className="mt-1 text-red-400 text-sm">{formErrors.email}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={registerMutation.isPending}
              className={`
                w-full py-3 rounded-xl font-semibold text-white
                transition-all duration-200
                ${registerMutation.isPending
                  ? 'bg-slate-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 shadow-lg shadow-emerald-500/25'
                }
              `}
            >
              {registerMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Getting your WiFi access...
                </span>
              ) : (
                'Get WiFi Access'
              )}
            </button>

            {/* Back link */}
            <button
              type="button"
              onClick={() => setStep('code')}
              className="w-full mt-4 text-slate-400 hover:text-white transition-colors text-sm"
            >
              ← Use a different code
            </button>
          </form>
        </div>
      </div>
    )
  }

  // Step 3: Success - show credentials
  if (step === 'success' && credentials) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 mb-4">
              <CheckCircle className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">
              You're Connected!
            </h1>
            <p className="text-slate-400">
              Here are your WiFi credentials
            </p>
          </div>

          {/* Credentials Card */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
            {/* QR Code */}
            {credentials.qr_code && (
              <div className="flex justify-center mb-6">
                <div className="bg-white p-4 rounded-xl">
                  <img 
                    src={credentials.qr_code} 
                    alt="WiFi QR Code" 
                    className="w-48 h-48"
                  />
                </div>
              </div>
            )}

            {/* Network Name */}
            <div className="mb-4 p-4 bg-slate-900/50 rounded-xl">
              <p className="text-sm text-slate-400 mb-1">Network Name</p>
              <p className="text-xl font-semibold text-white font-mono">{credentials.ssid_name}</p>
            </div>

            {/* Password */}
            {credentials.passphrase && (
              <div className="mb-6 p-4 bg-slate-900/50 rounded-xl">
                <p className="text-sm text-slate-400 mb-1">Password</p>
                <p className="text-xl font-semibold text-emerald-400 font-mono break-all">
                  {credentials.passphrase}
                </p>
              </div>
            )}

            <p className="text-center text-slate-400 text-sm">
              Scan the QR code with your camera app or enter the credentials manually
            </p>
          </div>

          {/* Done button */}
          <button
            onClick={() => navigate('/')}
            className="w-full mt-6 py-3 rounded-xl font-semibold text-white bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    )
  }

  // Step 4: Pending approval
  if (step === 'pending') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 mb-4">
              <Loader2 className="w-8 h-8 text-white animate-spin" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">
              Pending Approval
            </h1>
            <p className="text-slate-400">
              Your registration is being reviewed
            </p>
          </div>

          {/* Message Card */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
            <div className="text-center">
              <p className="text-slate-300 mb-4">
                {credentials?.pending_message || 
                  'Your registration is pending admin approval. You will receive your WiFi credentials once approved.'}
              </p>
              <p className="text-slate-400 text-sm">
                We'll notify you at your email address when your access is approved.
              </p>
            </div>
          </div>

          {/* Done button */}
          <button
            onClick={() => navigate('/')}
            className="w-full mt-6 py-3 rounded-xl font-semibold text-white bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            Got it
          </button>
        </div>
      </div>
    )
  }

  return null
}
