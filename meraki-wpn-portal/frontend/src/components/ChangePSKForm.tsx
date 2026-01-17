import { useState } from 'react'
import { RefreshCw, Check } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { changeUserPSK } from '../api/client'
import PSKCustomizer from './PSKCustomizer'
import QRCodeActions from './QRCodeActions'

interface ChangePSKFormProps {
  currentSSID: string
  onSuccess?: () => void
}

export default function ChangePSKForm({ currentSSID, onSuccess }: ChangePSKFormProps) {
  const [customPassphrase, setCustomPassphrase] = useState('')
  const [newCredentials, setNewCredentials] = useState<{
    passphrase: string
    qr_code: string
  } | null>(null)

  const mutation = useMutation({
    mutationFn: () => changeUserPSK(customPassphrase || undefined),
    onSuccess: (data) => {
      setNewCredentials({
        passphrase: data.new_passphrase,
        qr_code: data.qr_code,
      })
      setCustomPassphrase('')
      if (onSuccess) {
        onSuccess()
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate()
  }

  if (newCredentials) {
    return (
      <div className="space-y-4">
        <div className="p-4 bg-success-light rounded-lg border border-success">
          <div className="flex items-center gap-2 mb-2">
            <Check size={20} className="text-success" />
            <span className="font-semibold text-success">WiFi Password Updated!</span>
          </div>
          <p className="text-sm text-gray-700">
            Your new password has been set. Update all your devices with the new credentials.
          </p>
        </div>

        <div className="card">
          <h4 className="font-semibold mb-4">New WiFi Password</h4>
          <QRCodeActions
            qrCodeDataUrl={newCredentials.qr_code}
            ssid={currentSSID}
            passphrase={newCredentials.passphrase}
          />
        </div>

        <button
          onClick={() => setNewCredentials(null)}
          className="btn btn-secondary w-full"
        >
          Change Password Again
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {mutation.isError && (
        <div className="p-4 bg-error-light rounded-lg text-error border border-error">
          {mutation.error instanceof Error ? mutation.error.message : 'Failed to change password'}
        </div>
      )}

      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value={customPassphrase}
        onChange={setCustomPassphrase}
      />

      <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
        <p className="text-sm text-yellow-800">
          <strong>Important:</strong> Changing your WiFi password will disconnect all your devices. 
          You'll need to reconnect them with the new password.
        </p>
      </div>

      <button
        type="submit"
        className="btn btn-primary w-full"
        disabled={mutation.isPending}
      >
        {mutation.isPending ? (
          <>
            <span className="loading-spinner" /> Updating...
          </>
        ) : (
          <>
            <RefreshCw size={18} /> Change WiFi Password
          </>
        )}
      </button>
    </form>
  )
}
