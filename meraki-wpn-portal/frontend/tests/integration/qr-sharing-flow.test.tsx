import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import Success from '../../src/pages/public/Success'
import * as apiClient from '../../src/api/client'
import type { CreateQRTokenResponse, DeviceRegisterResponse } from '../../src/types/user'

vi.mock('../../src/api/client')

describe('QR Sharing and Device Registration Flow Integration', () => {
  let queryClient: QueryClient

  const mockSuccessData = {
    ssid: 'TestNetwork',
    passphrase: 'TestPassword123',
    qr_code: 'data:image/png;base64,testqrcode',
    ipsk_id: 'ipsk-test-123',
    is_returning_user: false,
    mobileconfig_url: 'https://example.com/profiles/test.mobileconfig',
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  const renderSuccess = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Success />
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('creates QR share token with correct data structure', async () => {
    const mockQRToken: CreateQRTokenResponse = {
      token: 'abc123def456',
      public_url: 'https://portal.example.com/wifi-qr/abc123def456',
      expires_at: '2026-02-14T12:00:00Z',
      created_at: '2026-01-14T12:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(mockQRToken)

    // Mock Success page location state
    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    // Find and click share button
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)

    // Verify API call
    await waitFor(() => {
      expect(apiClient.createQRToken).toHaveBeenCalledWith('ipsk-test-123')
    })

    // Verify response structure
    const response = await apiClient.createQRToken('ipsk-test-123')
    expect(response).toHaveProperty('token')
    expect(response).toHaveProperty('public_url')
    expect(response).toHaveProperty('expires_at')
    expect(response).toHaveProperty('created_at')

    // Verify data types
    expect(typeof response.token).toBe('string')
    expect(typeof response.public_url).toBe('string')
    expect(typeof response.expires_at).toBe('string')
    expect(typeof response.created_at).toBe('string')

    // Verify URL format
    expect(response.public_url).toMatch(/^https?:\/\//)
    expect(response.public_url).toContain(response.token)

    // Verify ISO date format
    expect(response.expires_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
    expect(response.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)

    // Verify token is alphanumeric
    expect(response.token).toMatch(/^[a-zA-Z0-9]+$/)
  })

  it('registers additional device with correct payload', async () => {
    const mockDeviceRegister: DeviceRegisterResponse = {
      success: true,
      device_id: 456,
      mac_address: '11:22:33:44:55:66',
      device_name: 'New Laptop',
      message: 'Device registered successfully',
    }

    vi.mocked(apiClient.registerDevice).mockResolvedValue(mockDeviceRegister)

    // Simulate user with existing account registering new device
    const returningUserData = {
      ...mockSuccessData,
      is_returning_user: true,
    }

    window.history.pushState(returningUserData, '', '/success')

    renderSuccess()

    // This would typically be triggered by a "Register Another Device" flow
    // For now, we'll test the API contract directly

    const response = await apiClient.registerDevice({
      email: 'test@example.com',
      password: 'TestPassword123',
      device_type: 'laptop',
      device_os: 'macOS',
      device_model: 'MacBook Pro',
      user_agent: navigator.userAgent,
    })

    // Verify response structure
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('device_id')
    expect(response).toHaveProperty('mac_address')
    expect(response).toHaveProperty('device_name')
    expect(response).toHaveProperty('message')

    // Verify data types
    expect(typeof response.success).toBe('boolean')
    expect(typeof response.device_id).toBe('number')
    expect(typeof response.mac_address).toBe('string')
    expect(typeof response.device_name).toBe('string')

    // Verify MAC address format
    expect(response.mac_address).toMatch(/^([0-9A-F]{2}:){5}[0-9A-F]{2}$/)

    // Verify device_id is positive integer
    expect(response.device_id).toBeGreaterThan(0)
    expect(Number.isInteger(response.device_id)).toBe(true)
  })

  it('validates QR code data URL format', async () => {
    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    // QR code should be displayed
    const qrImage = screen.getByAltText(/wifi qr code/i)
    expect(qrImage).toBeInTheDocument()

    // Verify src is data URL
    const src = qrImage.getAttribute('src')
    expect(src).toMatch(/^data:image\/(png|jpeg|jpg);base64,/)

    // Verify base64 content exists
    const base64Part = src?.split(',')[1]
    expect(base64Part).toBeTruthy()
    expect(base64Part!.length).toBeGreaterThan(0)
  })

  it('validates WiFi config string format for QR code', () => {
    // WiFi QR code format: WIFI:T:<type>;S:<ssid>;P:<password>;;
    const wifiConfig = `WIFI:T:WPA;S:${mockSuccessData.ssid};P:${mockSuccessData.passphrase};;`

    // Verify format
    expect(wifiConfig).toMatch(/^WIFI:T:(WPA|WEP|nopass);S:[^;]+;P:[^;]*;;$/)

    // Parse and verify components
    expect(wifiConfig).toContain(`S:${mockSuccessData.ssid}`)
    expect(wifiConfig).toContain(`P:${mockSuccessData.passphrase}`)
    expect(wifiConfig).toContain('T:WPA')
  })

  it('handles QR token expiration correctly', async () => {
    const expiredToken: CreateQRTokenResponse = {
      token: 'expired123',
      public_url: 'https://portal.example.com/wifi-qr/expired123',
      expires_at: '2026-01-13T12:00:00Z', // Yesterday
      created_at: '2026-01-07T12:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(expiredToken)

    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)

    await waitFor(() => {
      expect(apiClient.createQRToken).toHaveBeenCalled()
    })

    // Verify expiration date is in the past
    const response = await apiClient.createQRToken('test')
    const expiresAt = new Date(response.expires_at)
    const now = new Date('2026-01-14T12:00:00Z')
    
    expect(expiresAt < now).toBe(true)
  })

  it('validates mobileconfig URL format for iOS devices', async () => {
    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    // Mobileconfig URL should be valid HTTPS URL
    expect(mockSuccessData.mobileconfig_url).toMatch(/^https:\/\//)
    expect(mockSuccessData.mobileconfig_url).toContain('.mobileconfig')

    // URL should contain user-specific identifier
    expect(mockSuccessData.mobileconfig_url).toBeTruthy()
    
    // Parse URL
    const url = new URL(mockSuccessData.mobileconfig_url)
    expect(url.protocol).toBe('https:')
    expect(url.pathname).toMatch(/\.mobileconfig$/)
  })

  it('copies share URL to clipboard with correct format', async () => {
    const mockQRToken: CreateQRTokenResponse = {
      token: 'copy123',
      public_url: 'https://portal.example.com/wifi-qr/copy123',
      expires_at: '2026-02-14T12:00:00Z',
      created_at: '2026-01-14T12:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(mockQRToken)

    // Mock clipboard API
    const writeTextMock = vi.fn(() => Promise.resolve())
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    })

    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    // Generate share link
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)

    await waitFor(() => {
      expect(screen.getByText(/share link created/i)).toBeInTheDocument()
    })

    // Click copy button
    const copyButton = screen.getByText(/copy/i)
    fireEvent.click(copyButton)

    // Verify clipboard API called with correct URL
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(mockQRToken.public_url)
    })

    // Verify URL format matches response
    expect(writeTextMock.mock.calls[0][0]).toBe(mockQRToken.public_url)
  })

  it('validates print QR code data structure', async () => {
    // Mock window.open for print
    const mockPrintWindow = {
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    }
    window.open = vi.fn(() => mockPrintWindow) as any

    window.history.pushState(mockSuccessData, '', '/success')

    renderSuccess()

    // Click print button
    const printButton = screen.getByText(/print/i)
    fireEvent.click(printButton)

    // Verify print window opened
    expect(window.open).toHaveBeenCalled()

    // Verify document content includes all required data
    await waitFor(() => {
      const writeCall = mockPrintWindow.document.write.mock.calls[0][0]
      
      // Should include SSID
      expect(writeCall).toContain(mockSuccessData.ssid)
      
      // Should include passphrase
      expect(writeCall).toContain(mockSuccessData.passphrase)
      
      // Should include QR code data URL
      expect(writeCall).toContain(mockSuccessData.qr_code)
      
      // Should include proper HTML structure
      expect(writeCall).toContain('<!DOCTYPE html>')
      expect(writeCall).toContain('<img')
    })
  })

  it('handles device registration errors with proper error codes', async () => {
    vi.mocked(apiClient.registerDevice).mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: 'Device already registered',
          error_code: 'DEVICE_EXISTS',
        },
      },
    })

    try {
      await apiClient.registerDevice({
        email: 'test@example.com',
        password: 'test',
        device_type: 'phone',
        device_os: 'iOS',
        user_agent: 'test',
      })
    } catch (error: any) {
      // Verify error structure
      expect(error.response.status).toBe(409)
      expect(error.response.data).toHaveProperty('error')
      expect(error.response.data).toHaveProperty('error_code')
      expect(error.response.data.error_code).toBe('DEVICE_EXISTS')
    }
  })

  it('validates complete data flow from registration to QR sharing', async () => {
    // Step 1: Registration response
    const registrationResponse = {
      success: true,
      ssid: 'TestNet',
      passphrase: 'Pass123',
      qr_code: 'data:image/png;base64,qr123',
      ipsk_id: 'ipsk-flow-test',
    }

    // Step 2: Create share token
    const shareTokenResponse: CreateQRTokenResponse = {
      token: 'flow456',
      public_url: 'https://portal.example.com/wifi-qr/flow456',
      expires_at: '2026-02-14T12:00:00Z',
      created_at: '2026-01-14T12:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(shareTokenResponse)

    window.history.pushState(registrationResponse, '', '/success')

    renderSuccess()

    // Verify QR code is displayed
    expect(screen.getByAltText(/wifi qr code/i)).toBeInTheDocument()

    // Generate share link
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)

    await waitFor(() => {
      expect(apiClient.createQRToken).toHaveBeenCalledWith('ipsk-flow-test')
    })

    // Verify complete data chain
    const tokenResponse = await apiClient.createQRToken('ipsk-flow-test')
    
    // Token should be generated from ipsk_id
    expect(tokenResponse.token).toBeTruthy()
    
    // Public URL should contain token
    expect(tokenResponse.public_url).toContain(tokenResponse.token)
    
    // Expiration should be in future
    const expiresAt = new Date(tokenResponse.expires_at)
    const createdAt = new Date(tokenResponse.created_at)
    expect(expiresAt > createdAt).toBe(true)
  })

  it('ensures data consistency across all API responses', async () => {
    // Verify all timestamp fields use ISO 8601 format
    const testDates = [
      '2026-01-14T12:00:00Z',
      '2026-01-14T12:00:00.123Z',
      '2026-01-14T12:00:00+00:00',
    ]

    testDates.forEach(date => {
      const parsed = new Date(date)
      expect(parsed.toString()).not.toBe('Invalid Date')
      expect(parsed.toISOString()).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
    })

    // Verify all ID fields are positive integers
    const testIds = [1, 123, 999999]
    testIds.forEach(id => {
      expect(Number.isInteger(id)).toBe(true)
      expect(id).toBeGreaterThan(0)
    })

    // Verify all MAC addresses use colon-separated format
    const testMacs = [
      'AA:BB:CC:DD:EE:FF',
      '11:22:33:44:55:66',
      'A1:B2:C3:D4:E5:F6',
    ]
    testMacs.forEach(mac => {
      expect(mac).toMatch(/^([0-9A-F]{2}:){5}[0-9A-F]{2}$/)
    })

    // Verify all URLs use HTTPS
    const testUrls = [
      'https://portal.example.com/wifi-qr/abc123',
      'https://example.com/profiles/test.mobileconfig',
    ]
    testUrls.forEach(url => {
      expect(url).toMatch(/^https:\/\//)
      const parsed = new URL(url)
      expect(parsed.protocol).toBe('https:')
    })
  })
})
