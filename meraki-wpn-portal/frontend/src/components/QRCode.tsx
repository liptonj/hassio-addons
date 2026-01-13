interface QRCodeProps {
  dataUrl: string
  size?: number
  hint?: string
}

export default function QRCode({ dataUrl, size = 200, hint }: QRCodeProps) {
  return (
    <div className="qr-container">
      <img
        src={dataUrl}
        alt="WiFi QR Code"
        className="qr-code"
        width={size}
        height={size}
        style={{ display: 'block', margin: '0 auto' }}
      />
      {hint && <p className="qr-hint">{hint}</p>}
    </div>
  )
}
