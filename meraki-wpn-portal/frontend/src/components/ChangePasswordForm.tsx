import { useState } from 'react'
import { Lock, Eye, EyeOff } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { changeUserPassword } from '../api/client'

export default function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [success, setSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: () => changeUserPassword(currentPassword, newPassword),
    onSuccess: () => {
      setSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => setSuccess(false), 5000)
    },
    onError: (err: Error) => {
      setErrors({ form: err.message })
    },
  })

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!currentPassword) {
      newErrors.currentPassword = 'Current password is required'
    }

    if (!newPassword) {
      newErrors.newPassword = 'New password is required'
    } else if (newPassword.length < 8) {
      newErrors.newPassword = 'Password must be at least 8 characters'
    }

    if (newPassword !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})
    setSuccess(false)

    if (validate()) {
      mutation.mutate()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {success && (
        <div className="p-4 bg-success-light rounded-lg text-success border border-success">
          Password changed successfully!
        </div>
      )}

      {errors.form && (
        <div className="p-4 bg-error-light rounded-lg text-error border border-error">
          {errors.form}
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Current Password</label>
        <div className="relative">
          <input
            type={showCurrent ? 'text' : 'password'}
            className={`form-input pr-10 ${errors.currentPassword ? 'error' : ''}`}
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={() => setShowCurrent(!showCurrent)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-500"
          >
            {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
        {errors.currentPassword && <p className="form-error">{errors.currentPassword}</p>}
      </div>

      <div className="form-group">
        <label className="form-label">New Password</label>
        <div className="relative">
          <input
            type={showNew ? 'text' : 'password'}
            className={`form-input pr-10 ${errors.newPassword ? 'error' : ''}`}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={() => setShowNew(!showNew)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-500"
          >
            {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
        {errors.newPassword && <p className="form-error">{errors.newPassword}</p>}
      </div>

      <div className="form-group">
        <label className="form-label">Confirm New Password</label>
        <input
          type="password"
          className={`form-input ${errors.confirmPassword ? 'error' : ''}`}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />
        {errors.confirmPassword && <p className="form-error">{errors.confirmPassword}</p>}
      </div>

      <button
        type="submit"
        className="btn btn-primary w-full"
        disabled={mutation.isPending}
      >
        {mutation.isPending ? (
          <>
            <span className="loading-spinner" /> Changing...
          </>
        ) : (
          <>
            <Lock size={18} /> Change Password
          </>
        )}
      </button>
    </form>
  )
}
