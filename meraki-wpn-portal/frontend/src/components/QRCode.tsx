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
        className="qr-code block mx-auto"
        width={size}
        height={size}
      />
      {hint && <p className="qr-hint">{hint}</p>}
    </div>
  )
}
