import { describe, it, expect, vi } from 'vitest'
import { printQRCode } from '../../src/utils/printQRCode'

describe('printQRCode', () => {
  let mockWindow: any

  beforeEach(() => {
    mockWindow = {
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    }
    
    window.open = vi.fn(() => mockWindow)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('opens a new window', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(window.open).toHaveBeenCalledWith('', '_blank')
  })

  it('writes HTML content to the window', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(mockWindow.document.write).toHaveBeenCalled()
    const content = mockWindow.document.write.mock.calls[0][0]
    
    expect(content).toContain('<!DOCTYPE html>')
    expect(content).toContain('TestSSID')
    expect(content).toContain('TestPassword')
  })

  it('includes QR code image in content', () => {
    const qrDataUrl = 'data:image/png;base64,testqrcode'
    printQRCode('TestSSID', 'TestPassword', qrDataUrl)
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain(qrDataUrl)
    expect(content).toContain('<img')
    expect(content).toContain('WiFi QR Code')
  })

  it('includes print button in content', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('Print This Page')
    expect(content).toContain('window.print()')
  })

  it('includes connection instructions', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('How to Connect')
    expect(content).toContain('camera app')
  })

  it('includes print-friendly CSS', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('@media print')
    expect(content).toContain('.no-print')
  })

  it('focuses the window', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(mockWindow.focus).toHaveBeenCalled()
  })

  it('triggers print after delay', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(mockWindow.print).not.toHaveBeenCalled()
    
    vi.advanceTimersByTime(250)
    
    expect(mockWindow.print).toHaveBeenCalled()
  })

  it('closes document after writing', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(mockWindow.document.close).toHaveBeenCalled()
  })

  it('handles popup blocker gracefully', () => {
    window.open = vi.fn(() => null)
    
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('Failed to open print window')
    )
    
    consoleSpy.mockRestore()
  })

  it('includes responsive CSS for mobile', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('@media (max-width: 640px)')
  })

  it('includes styled credentials box', () => {
    printQRCode('TestSSID', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('.credentials')
    expect(content).toContain('Network Name (SSID)')
  })

  it('escapes HTML special characters in SSID', () => {
    printQRCode('Test<SSID>', 'TestPassword', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('Test<SSID>')
  })

  it('escapes HTML special characters in password', () => {
    printQRCode('TestSSID', 'Pass<word>&123', 'data:image/png;base64,test')
    
    const content = mockWindow.document.write.mock.calls[0][0]
    expect(content).toContain('Pass<word>&123')
  })
})
