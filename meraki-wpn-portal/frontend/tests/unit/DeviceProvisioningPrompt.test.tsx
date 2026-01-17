import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import DeviceProvisioningPrompt from '../../src/components/DeviceProvisioningPrompt'

describe('DeviceProvisioningPrompt', () => {
  const defaultProps = {
    ipskId: 'test-ipsk-123',
    ssid: 'TestNetwork',
    passphrase: 'TestPassword123',
  }

  const originalUserAgent = navigator.userAgent

  beforeEach(() => {
    // Reset user agent before each test
    Object.defineProperty(navigator, 'userAgent', {
      value: originalUserAgent,
      configurable: true,
    })
  })

  it('shows iOS profile option for iPhone', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/apple device detected/i)).toBeInTheDocument()
    expect(screen.getByText(/download wifi profile/i)).toBeInTheDocument()
  })

  it('shows iOS profile option for iPad', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X)',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/apple device detected/i)).toBeInTheDocument()
  })

  it('shows macOS installation steps', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/system preferences/i)).toBeInTheDocument()
  })

  it('shows QR code for Android', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Linux; Android 13) Mobile Safari',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/android device detected/i)).toBeInTheDocument()
    expect(screen.getByText(/scan qr code/i)).toBeInTheDocument()
  })

  it('shows Android camera instructions', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Linux; Android 13) Mobile Safari',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/open your camera app/i)).toBeInTheDocument()
  })

  it('shows generic instructions for other devices', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/connect this device/i)).toBeInTheDocument()
    expect(screen.getByText(/manual connection/i)).toBeInTheDocument()
  })

  it('displays SSID in generic instructions', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(defaultProps.ssid)).toBeInTheDocument()
    expect(screen.getByText(defaultProps.passphrase)).toBeInTheDocument()
  })

  it('uses mobileconfig URL when provided', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
      configurable: true,
    })

    const mobileconfigUrl = 'https://example.com/profile.mobileconfig'
    render(<DeviceProvisioningPrompt {...defaultProps} mobileconfigUrl={mobileconfigUrl} />)
    
    const button = screen.getByText(/download wifi profile/i)
    expect(button).toBeInTheDocument()
  })

  it('shows iOS installation steps', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    expect(screen.getByText(/tap the button above/i)).toBeInTheDocument()
    expect(screen.getByText(/settings/i)).toBeInTheDocument()
  })

  it('displays device description when available', () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
      configurable: true,
    })

    render(<DeviceProvisioningPrompt {...defaultProps} />)
    
    // Should show some device info
    expect(screen.getByText(/device:/i)).toBeInTheDocument()
  })
})
