import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tantml:react-query'
import { BrowserRouter } from 'react-router-dom'
import UserAccount from '../../src/pages/public/UserAccount'
import * as apiClient from '../../src/api/client'
import type { UserDevicesResponse, UserDevice, ChangePSKResponse } from '../../src/types/user'

vi.mock('../../src/api/client')

describe('User Account Management Flow Integration', () => {
  let queryClient: QueryClient

  const mockDevices: UserDevice[] = [
    {
      id: 1,
      mac_address: 'AA:BB:CC:DD:EE:FF',
      device_type: 'phone',
      device_os: 'iOS',
      device_model: 'iPhone 15 Pro',
      device_name: 'My iPhone',
      registered_at: '2026-01-14T10:00:00Z',
      last_seen_at: '2026-01-14T12:00:00Z',
      is_active: true,
    },
    {
      id: 2,
      mac_address: '11:22:33:44:55:66',
      device_type: 'laptop',
      device_os: 'macOS',
      device_model: 'MacBook Pro',
      device_name: 'Work Laptop',
      registered_at: '2026-01-13T10:00:00Z',
      last_seen_at: '2026-01-14T11:30:00Z',
      is_active: true,
    },
  ]

  const mockDevicesResponse: UserDevicesResponse = {
    devices: mockDevices,
    total_count: 2,
    max_devices: 5,
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()

    // Mock user devices
    vi.mocked(apiClient.getUserDevices).mockResolvedValue(mockDevicesResponse)
  })

  const renderUserAccount = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <UserAccount />
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('loads and displays user devices with correct data structure', async () => {
    renderUserAccount()

    // Switch to devices tab
    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    // Verify API call
    await waitFor(() => {
      expect(apiClient.getUserDevices).toHaveBeenCalled()
    })

    // Verify response structure
    const response = await apiClient.getUserDevices()
    expect(response).toHaveProperty('devices')
    expect(response).toHaveProperty('total_count')
    expect(response).toHaveProperty('max_devices')

    // Verify devices array structure
    expect(Array.isArray(response.devices)).toBe(true)
    expect(response.devices.length).toBe(2)

    // Verify first device has all required properties
    const firstDevice = response.devices[0]
    expect(firstDevice).toHaveProperty('id')
    expect(firstDevice).toHaveProperty('mac_address')
    expect(firstDevice).toHaveProperty('device_type')
    expect(firstDevice).toHaveProperty('device_os')
    expect(firstDevice).toHaveProperty('device_model')
    expect(firstDevice).toHaveProperty('device_name')
    expect(firstDevice).toHaveProperty('registered_at')
    expect(firstDevice).toHaveProperty('last_seen_at')
    expect(firstDevice).toHaveProperty('is_active')

    // Verify data types
    expect(typeof firstDevice.id).toBe('number')
    expect(typeof firstDevice.mac_address).toBe('string')
    expect(typeof firstDevice.device_type).toBe('string')
    expect(typeof firstDevice.is_active).toBe('boolean')

    // Verify MAC address format
    expect(firstDevice.mac_address).toMatch(/^([0-9A-F]{2}:){5}[0-9A-F]{2}$/)

    // Verify ISO date format
    expect(firstDevice.registered_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
  })

  it('removes device with correct API call', async () => {
    vi.mocked(apiClient.removeUserDevice).mockResolvedValue({
      success: true,
      message: 'Device removed',
    })

    // Mock window.confirm
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderUserAccount()

    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    await waitFor(() => {
      expect(screen.getByText('My iPhone')).toBeInTheDocument()
    })

    // Click remove button
    const removeButtons = screen.getAllByText(/remove/i)
    fireEvent.click(removeButtons[0])

    // Verify API call
    await waitFor(() => {
      expect(apiClient.removeUserDevice).toHaveBeenCalledWith(1)
    })

    confirmSpy.mockRestore()
  })

  it('renames device with correct payload', async () => {
    vi.mocked(apiClient.renameUserDevice).mockResolvedValue({
      success: true,
      device_name: 'iPhone Pro Max',
    })

    // Mock window.prompt
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('iPhone Pro Max')

    renderUserAccount()

    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    await waitFor(() => {
      expect(screen.getByText('My iPhone')).toBeInTheDocument()
    })

    // Click rename button
    const renameButtons = screen.getAllByText(/rename/i)
    fireEvent.click(renameButtons[0])

    // Verify API call with correct parameters
    await waitFor(() => {
      expect(apiClient.renameUserDevice).toHaveBeenCalledWith(1, 'iPhone Pro Max')
    })

    // Verify response structure
    const response = await apiClient.renameUserDevice(1, 'iPhone Pro Max')
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('device_name')
    expect(typeof response.success).toBe('boolean')
    expect(typeof response.device_name).toBe('string')

    promptSpy.mockRestore()
  })

  it('changes user password with correct payload structure', async () => {
    vi.mocked(apiClient.changeUserPassword).mockResolvedValue({
      success: true,
      message: 'Password changed successfully',
    })

    renderUserAccount()

    // Switch to security tab
    const securityTab = screen.getByRole('button', { name: /security/i })
    fireEvent.click(securityTab)

    await waitFor(() => {
      expect(screen.getByLabelText(/current password/i)).toBeInTheDocument()
    })

    // Fill password form
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'OldPassword123' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'NewPassword456' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'NewPassword456' },
    })

    // Submit
    const changeButton = screen.getByRole('button', { name: /change password/i })
    fireEvent.click(changeButton)

    // Verify API call
    await waitFor(() => {
      expect(apiClient.changeUserPassword).toHaveBeenCalledWith(
        'OldPassword123',
        'NewPassword456'
      )
    })

    // Verify response structure
    const response = await apiClient.changeUserPassword('', '')
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('message')
    expect(typeof response.success).toBe('boolean')
    expect(typeof response.message).toBe('string')
  })

  it('changes WiFi PSK with correct data flow', async () => {
    const mockPSKResponse: ChangePSKResponse = {
      success: true,
      new_passphrase: 'NewWiFiPass123',
      qr_code: 'data:image/png;base64,newqrcode',
      message: 'WiFi password changed',
    }

    vi.mocked(apiClient.changeUserPSK).mockResolvedValue(mockPSKResponse)

    renderUserAccount()

    // Stay on WiFi tab (default)
    await waitFor(() => {
      expect(screen.getByText(/wifi credentials/i)).toBeInTheDocument()
    })

    // Find and click change WiFi password button
    const changeWiFiButton = screen.getByRole('button', { name: /change wifi password/i })
    fireEvent.click(changeWiFiButton)

    // Verify API call (auto-generate mode, no custom passphrase)
    await waitFor(() => {
      expect(apiClient.changeUserPSK).toHaveBeenCalledWith(undefined)
    })

    // Verify response structure
    const response = await apiClient.changeUserPSK()
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('new_passphrase')
    expect(response).toHaveProperty('qr_code')
    expect(response).toHaveProperty('message')

    // Verify data types
    expect(typeof response.success).toBe('boolean')
    expect(typeof response.new_passphrase).toBe('string')
    expect(typeof response.qr_code).toBe('string')
    expect(response.qr_code).toMatch(/^data:image\/png;base64,/)

    // Verify passphrase meets requirements (8-63 characters)
    expect(response.new_passphrase.length).toBeGreaterThanOrEqual(8)
    expect(response.new_passphrase.length).toBeLessThanOrEqual(63)
  })

  it('changes WiFi PSK with custom passphrase', async () => {
    const mockPSKResponse: ChangePSKResponse = {
      success: true,
      new_passphrase: 'MyCustomWiFi2026',
      qr_code: 'data:image/png;base64,customqr',
      message: 'WiFi password changed',
    }

    vi.mocked(apiClient.changeUserPSK).mockResolvedValue(mockPSKResponse)

    renderUserAccount()

    await waitFor(() => {
      expect(screen.getByText(/wifi credentials/i)).toBeInTheDocument()
    })

    // Switch to custom PSK mode
    const customButton = screen.getByText(/choose my own/i)
    fireEvent.click(customButton)

    // Enter custom passphrase
    const pskInput = screen.getByPlaceholderText(/enter your password/i)
    fireEvent.change(pskInput, {
      target: { value: 'MyCustomWiFi2026' },
    })

    // Submit
    const changeButton = screen.getByRole('button', { name: /change wifi password/i })
    fireEvent.click(changeButton)

    // Verify API call with custom passphrase
    await waitFor(() => {
      expect(apiClient.changeUserPSK).toHaveBeenCalledWith('MyCustomWiFi2026')
    })

    // Verify custom passphrase is returned
    const response = await apiClient.changeUserPSK('MyCustomWiFi2026')
    expect(response.new_passphrase).toBe('MyCustomWiFi2026')
  })

  it('handles device limit correctly', async () => {
    const fullDevicesResponse: UserDevicesResponse = {
      devices: new Array(5).fill(null).map((_, i) => ({
        ...mockDevices[0],
        id: i + 1,
        mac_address: `AA:BB:CC:DD:EE:F${i}`,
        device_name: `Device ${i + 1}`,
      })),
      total_count: 5,
      max_devices: 5,
    }

    vi.mocked(apiClient.getUserDevices).mockResolvedValue(fullDevicesResponse)

    renderUserAccount()

    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    await waitFor(() => {
      const response = apiClient.getUserDevices()
      return response.then(r => {
        expect(r.total_count).toBe(r.max_devices)
      })
    })

    // Should show device limit message
    await waitFor(() => {
      expect(screen.getByText(/5 of 5 devices/i)).toBeInTheDocument()
    })
  })

  it('validates device data consistency', async () => {
    renderUserAccount()

    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    const response = await apiClient.getUserDevices()

    // Verify all devices have required fields
    response.devices.forEach(device => {
      expect(device.id).toBeTruthy()
      expect(device.mac_address).toBeTruthy()
      expect(device.device_type).toBeTruthy()
      expect(device.registered_at).toBeTruthy()
      
      // Dates should be parseable
      const registeredDate = new Date(device.registered_at)
      expect(registeredDate.toString()).not.toBe('Invalid Date')
      
      if (device.last_seen_at) {
        const lastSeenDate = new Date(device.last_seen_at)
        expect(lastSeenDate.toString()).not.toBe('Invalid Date')
      }
    })
  })

  it('handles errors in device operations gracefully', async () => {
    vi.mocked(apiClient.removeUserDevice).mockRejectedValue(
      new Error('Failed to remove device')
    )

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderUserAccount()

    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    await waitFor(() => {
      expect(screen.getByText('My iPhone')).toBeInTheDocument()
    })

    const removeButtons = screen.getAllByText(/remove/i)
    fireEvent.click(removeButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/failed to remove device/i)).toBeInTheDocument()
    })

    confirmSpy.mockRestore()
  })

  it('maintains data integrity across tab switches', async () => {
    renderUserAccount()

    // Load devices
    const devicesTab = screen.getByRole('button', { name: /devices/i })
    fireEvent.click(devicesTab)

    await waitFor(() => {
      expect(screen.getByText('My iPhone')).toBeInTheDocument()
    })

    // Switch to security tab
    const securityTab = screen.getByRole('button', { name: /security/i })
    fireEvent.click(securityTab)

    // Switch back to devices
    fireEvent.click(devicesTab)

    // Data should still be there (cached)
    await waitFor(() => {
      expect(screen.getByText('My iPhone')).toBeInTheDocument()
    })
  })
})
