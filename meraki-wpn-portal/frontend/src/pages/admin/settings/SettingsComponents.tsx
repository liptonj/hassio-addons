import { Eye, EyeOff, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'

/* Form Row Component */
export function FormRow({ label, children, required = false }: { 
  label: string
  children: React.ReactNode
  required?: boolean
}) {
  return (
    <div className="form-group">
      <label className="form-label">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  )
}

/* Secret Input Component */
export function SecretInput({
  value,
  onChange,
  show,
  onToggle,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  show: boolean
  onToggle: () => void
  placeholder: string
}) {
  const isMasked = value === '***' || value?.startsWith('***')
  
  return (
    <div className="flex gap-2">
      <div className="flex-1 relative">
        <input
          type={show ? 'text' : 'password'}
          value={isMasked ? '' : (value || '')}
          onChange={(e) => onChange(e.target.value)}
          className={`input ${isMasked ? 'bg-green-50 dark:bg-green-900/20 border-green-500 dark:border-green-700' : ''}`}
          placeholder={isMasked ? '••••••••••••  (saved)' : placeholder}
        />
        {isMasked && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-green-600 dark:text-green-400 font-medium">
            ✓ Saved
          </span>
        )}
      </div>
      <button
        type="button"
        className="btn btn-secondary px-3"
        onClick={onToggle}
      >
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  )
}

/* Notification Component */
export function Notification({
  type,
  message,
}: {
  type: 'success' | 'error' | 'warning'
  message: string
}) {
  return (
    <div className={`p-4 rounded-lg flex items-center gap-3 ${
        type === 'success'
          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
          : type === 'warning'
          ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
          : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
      }`}>
      {type === 'success' && <CheckCircle size={20} />}
      {type === 'warning' && <AlertTriangle size={20} />}
      {type === 'error' && <XCircle size={20} />}
      {message}
    </div>
  )
}
