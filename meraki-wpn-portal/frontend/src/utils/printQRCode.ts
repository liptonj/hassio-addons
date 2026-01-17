/**
 * QR Code Print Utility
 * 
 * Opens a print-friendly page with WiFi QR code and credentials
 */

/**
 * Opens a print-friendly window with the QR code
 * @param ssid Network SSID
 * @param passphrase WiFi password
 * @param qrDataUrl Base64 data URL of the QR code image
 */
export function printQRCode(ssid: string, passphrase: string, qrDataUrl: string): void {
  const printWindow = window.open('', '_blank')
  
  if (!printWindow) {
    console.error('Failed to open print window. Pop-ups may be blocked.')
    return
  }

  printWindow.document.write(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>WiFi QR Code - ${ssid}</title>
      <style>
        @media print {
          body { margin: 0; padding: 20px; }
          .no-print { display: none; }
        }
        * {
          box-sizing: border-box;
        }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
          text-align: center;
          max-width: 600px;
          margin: 0 auto;
          padding: 40px 20px;
          line-height: 1.5;
        }
        h1 { 
          font-size: 24px; 
          margin-bottom: 10px;
          color: #1f2937;
        }
        .qr-code { 
          margin: 30px 0;
          display: flex;
          justify-content: center;
        }
        .qr-code img { 
          width: 300px; 
          height: 300px;
          border: 8px solid #f3f4f6;
          border-radius: 12px;
        }
        .credentials {
          background: #f9fafb;
          padding: 24px;
          border-radius: 12px;
          margin: 20px 0;
          border: 1px solid #e5e7eb;
        }
        .credentials p { 
          margin: 12px 0; 
          font-size: 16px;
        }
        .credentials strong { 
          display: block; 
          color: #6b7280; 
          margin-bottom: 5px;
          font-size: 14px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .credentials .value {
          font-size: 18px;
          font-weight: 600;
          color: #1f2937;
          font-family: 'JetBrains Mono', 'Courier New', monospace;
        }
        .instructions { 
          text-align: left; 
          margin-top: 30px;
          padding: 20px;
          background: white;
          border-radius: 8px;
        }
        .instructions h3 {
          margin-top: 0;
          color: #1f2937;
        }
        .instructions ol {
          margin: 16px 0;
          padding-left: 24px;
        }
        .instructions li {
          margin: 8px 0;
          color: #4b5563;
        }
        .instructions small {
          color: #6b7280;
        }
        .print-button {
          margin-top: 30px;
          padding: 12px 24px;
          font-size: 16px;
          cursor: pointer;
          background: linear-gradient(135deg, #0066cc 0%, #004999 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          transition: transform 0.2s;
        }
        .print-button:hover {
          transform: translateY(-2px);
        }
        @media (max-width: 640px) {
          .qr-code img { 
            width: 250px; 
            height: 250px; 
          }
          body {
            padding: 20px 16px;
          }
        }
      </style>
    </head>
    <body>
      <h1>WiFi Access Credentials</h1>
      
      <div class="qr-code">
        <img src="${qrDataUrl}" alt="WiFi QR Code" />
      </div>
      
      <div class="credentials">
        <p>
          <strong>Network Name (SSID)</strong>
          <span class="value">${ssid}</span>
        </p>
        <p>
          <strong>Password</strong>
          <span class="value">${passphrase}</span>
        </p>
      </div>
      
      <div class="instructions">
        <h3>How to Connect:</h3>
        <ol>
          <li>Open your phone's camera app</li>
          <li>Point it at the QR code above</li>
          <li>Tap the notification that appears</li>
          <li>Confirm to join the network</li>
        </ol>
        <p><small>Or manually enter the SSID and password above in your WiFi settings.</small></p>
      </div>
      
      <button class="no-print print-button" onclick="window.print()">
        Print This Page
      </button>
    </body>
    </html>
  `)
  
  printWindow.document.close()
  printWindow.focus()
  
  // Auto-trigger print dialog after a short delay to ensure content is loaded
  setTimeout(() => {
    printWindow.print()
  }, 250)
}
