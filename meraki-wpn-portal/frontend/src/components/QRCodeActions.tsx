import { useState } from 'react'
import { Printer, Download, Share2, Check, QrCode as QrCodeIcon, Copy } from 'lucide-react'
import QRCode from './QRCode'
import { printQRCode } from '../utils/printQRCode'
import { createQRToken } from '../api/client'

interface QRCodeActionsProps {
  qrCodeDataUrl: string
  ssid: string
  passphrase: string
  ipskId?: string
}

export default function QRCodeActions({
  qrCodeDataUrl,
  ssid,
  passphrase,
  ipskId,
}: QRCodeActionsProps) {
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [isSharing, setIsSharing] = useState(false)
  const [shareError, setShareError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handlePrint = () => {
    printQRCode(ssid, passphrase, qrCodeDataUrl)
  }

  const handleDownload = () => {
    // Convert data URL to blob
    fetch(qrCodeDataUrl)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `wifi-${ssid.replace(/\s+/g, '-')}.png`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      })
      .catch(err => {
        console.error('Download failed:', err)
      })
  }

  const handleShare = async () => {
    if (!ipskId) {
      setShareError('Cannot generate share link without iPSK ID')
      return
    }

    setIsSharing(true)
    setShareError(null)

    try {
      const result = await createQRToken(ipskId)
      setShareUrl(result.public_url)
    } catch (err) {
      setShareError(err instanceof Error ? err.message : 'Failed to create share link')
    } finally {
      setIsSharing(false)
    }
  }

  const handleCopyShareUrl = async () => {
    if (shareUrl) {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-4">
      {/* QR Code Display */}
      <div className="flex justify-center">
        <QRCode
          dataUrl={qrCodeDataUrl}
          size={200}
          hint="Scan with your phone's camera to connect"
        />
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button
          type="button"
          onClick={handlePrint}
          className="btn btn-secondary"
        >
          <Printer size={18} /> Print
        </button>

        <button
          type="button"
          onClick={handleDownload}
          className="btn btn-secondary"
        >
          <Download size={18} /> Download
        </button>

        {ipskId && (
          <button
            type="button"
            onClick={handleShare}
            disabled={isSharing}
            className="btn btn-secondary"
          >
            {isSharing ? (
              <>
                <span className="loading-spinner" /> Generating...
              </>
            ) : (
              <>
                <Share2 size={18} /> Share Link
              </>
            )}
          </button>
        )}
      </div>

      {/* Share URL Display */}
      {shareUrl && (
        <div className="p-4 bg-success-light rounded-lg border border-success">
          <div className="flex items-start gap-2 mb-2">
            <Check size={20} className="text-success flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-success mb-1">Share link created!</p>
              <p className="text-sm text-gray-700 mb-3">
                Anyone with this link can view and download your WiFi QR code. The link expires in 30 days.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="form-input text-sm flex-1"
                  onClick={(e) => e.currentTarget.select()}
                />
                <button
                  type="button"
                  onClick={handleCopyShareUrl}
                  className="btn btn-secondary btn-sm flex-shrink-0"
                >
                  {copied ? (
                    <>
                      <Check size={16} /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={16} /> Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Share Error */}
      {shareError && (
        <div className="p-4 bg-error-light rounded-lg border border-error text-error text-sm">
          {shareError}
        </div>
      )}

      {/* Instructions */}
      <div className="text-center text-sm text-muted">
        <p className="flex items-center justify-center gap-2">
          <QrCodeIcon size={16} />
          <span>Point your camera at the QR code to connect instantly</span>
        </p>
      </div>
    </div>
  )
}
