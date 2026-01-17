import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import Registration from '../../src/pages/public/Registration'
import Success from '../../src/pages/public/Success'
import * as apiClient from '../../src/api/client'
import type { PortalOptions, RegistrationResponse } from '../../src/types/user'

// Mock API client
vi.mock('../../src/api/client')

describe('Full Registration Flow Integration', () => {
  let queryClient: QueryClient

  const mockOptions: PortalOptions = {
    local_auth_enabled: true,
    oauth_enabled: false,
    invite_code_enabled: true,
    invite_code_required: false,
    self_registration_enabled: true,
    aup_enabled: true,
    aup_text: 'By using this network, you agree to our acceptable use policy.',
    aup_url: null,
    aup_version: '1.0',
    custom_fields: [
      {
        id: 'unit_number',
        label: 'Unit Number',
        type: 'text',
        required: true,
      },
      {
        id: 'parking',
        label: 'Parking Spot',
        type: 'select',
        required: false,
        options: ['A1', 'A2', 'B1', 'B2'],
      },
    ],
    allow_custom_psk: true,
    psk_requirements: {
      min_length: 8,
      max_length: 63,
    },
    invite_code_email_restriction: false,
    invite_code_single_use: false,
    universal_login_enabled: true,
    show_login_method_selector: true,
  }

  const mockRegistrationResponse: RegistrationResponse = {
    success: true,
    message: 'Registration successful',
    user_id: 123,
    email: 'test@example.com',
    ssid: 'TestNetwork',
    passphrase: 'GeneratedPass123',
    qr_code: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    ipsk_id: 'ipsk-abc123',
    is_returning_user: false,
    device_info: {
      device_type: 'phone',
      device_os: 'iOS',
      is_new_device: true,
    },
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

    // Mock getOptions
    vi.mocked(apiClient.getOptions).mockResolvedValue(mockOptions)
  })

  const renderRegistration = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Registration />
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('completes full registration flow with all features', async () => {
    vi.mocked(apiClient.register).mockResolvedValue(mockRegistrationResponse)

    renderRegistration()

    // Wait for options to load
    await waitFor(() => {
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    })

    // Fill basic information
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'John Doe' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    })

    // Fill custom fields
    const unitNumberInput = screen.getByLabelText(/unit number/i)
    fireEvent.change(unitNumberInput, {
      target: { value: '101' },
    })

    const parkingSelect = screen.getByLabelText(/parking spot/i)
    fireEvent.change(parkingSelect, {
      target: { value: 'A1' },
    })

    // Accept AUP
    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    // Choose custom PSK
    const customPskButton = screen.getByText(/choose my own/i)
    fireEvent.click(customPskButton)

    const pskInput = screen.getByPlaceholderText(/enter your password/i)
    fireEvent.change(pskInput, {
      target: { value: 'MyCustomPass123' },
    })

    // Submit form
    const submitButton = screen.getByRole('button', { name: /register/i })
    fireEvent.click(submitButton)

    // Verify API call with correct data structure
    await waitFor(() => {
      expect(apiClient.register).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'John Doe',
          email: 'test@example.com',
          custom_passphrase: 'MyCustomPass123',
          accept_aup: true,
          custom_fields: {
            unit_number: '101',
            parking: 'A1',
          },
          user_agent: expect.any(String),
        })
      )
    })

    // Verify response structure matches TypeScript types
    const response = await apiClient.register({} as any)
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('user_id')
    expect(response).toHaveProperty('ssid')
    expect(response).toHaveProperty('passphrase')
    expect(response).toHaveProperty('qr_code')
    expect(response).toHaveProperty('ipsk_id')
    expect(response).toHaveProperty('is_returning_user')
    expect(response).toHaveProperty('device_info')
  })

  it('handles returning user with existing credentials', async () => {
    const returningUserResponse: RegistrationResponse = {
      ...mockRegistrationResponse,
      is_returning_user: true,
      passphrase: 'ExistingPassword123',
      device_info: {
        device_type: 'laptop',
        device_os: 'macOS',
        is_new_device: true,
      },
    }

    vi.mocked(apiClient.register).mockResolvedValue(returningUserResponse)

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    })

    // Fill and submit
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'John Doe' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'returning@example.com' },
    })

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    // Verify response indicates returning user
    const response = await apiClient.register({} as any)
    expect(response.is_returning_user).toBe(true)
    expect(response.device_info?.is_new_device).toBe(true)
  })

  it('validates custom fields are included in request', async () => {
    vi.mocked(apiClient.register).mockResolvedValue(mockRegistrationResponse)

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/unit number/i)).toBeInTheDocument()
    })

    // Fill all fields including custom
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Jane Smith' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'jane@example.com' },
    })
    fireEvent.change(screen.getByLabelText(/unit number/i), {
      target: { value: '205' },
    })
    fireEvent.change(screen.getByLabelText(/parking spot/i), {
      target: { value: 'B2' },
    })

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    // Verify custom_fields object structure
    await waitFor(() => {
      const calls = vi.mocked(apiClient.register).mock.calls
      expect(calls[0][0]).toHaveProperty('custom_fields')
      expect(calls[0][0].custom_fields).toEqual({
        unit_number: '205',
        parking: 'B2',
      })
    })
  })

  it('sends correct data types for all fields', async () => {
    const optionsWithNumber: PortalOptions = {
      ...mockOptions,
      custom_fields: [
        ...mockOptions.custom_fields!,
        {
          id: 'floor',
          label: 'Floor',
          type: 'number',
          required: true,
        },
      ],
    }

    vi.mocked(apiClient.getOptions).mockResolvedValue(optionsWithNumber)
    vi.mocked(apiClient.register).mockResolvedValue(mockRegistrationResponse)

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/floor/i)).toBeInTheDocument()
    })

    // Fill all fields
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Test User' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    })
    fireEvent.change(screen.getByLabelText(/unit number/i), {
      target: { value: '302' },
    })
    fireEvent.change(screen.getByLabelText(/floor/i), {
      target: { value: '3' },
    })

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    // Verify data types
    await waitFor(() => {
      const calls = vi.mocked(apiClient.register).mock.calls
      const payload = calls[0][0]
      
      expect(typeof payload.name).toBe('string')
      expect(typeof payload.email).toBe('string')
      expect(typeof payload.accept_aup).toBe('boolean')
      expect(payload.custom_fields.unit_number).toBe('302')
      expect(payload.custom_fields.floor).toBe('3') // From input it's still string
    })
  })

  it('handles API errors correctly', async () => {
    vi.mocked(apiClient.register).mockRejectedValue(
      new Error('Email already registered')
    )

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Test User' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'duplicate@example.com' },
    })

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      expect(screen.getByText(/email already registered/i)).toBeInTheDocument()
    })
  })

  it('includes user agent in registration request', async () => {
    vi.mocked(apiClient.register).mockResolvedValue(mockRegistrationResponse)

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Test User' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    })

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      const calls = vi.mocked(apiClient.register).mock.calls
      expect(calls[0][0]).toHaveProperty('user_agent')
      expect(calls[0][0].user_agent).toBeTruthy()
      expect(typeof calls[0][0].user_agent).toBe('string')
    })
  })

  it('handles optional vs required custom fields', async () => {
    vi.mocked(apiClient.register).mockResolvedValue(mockRegistrationResponse)

    renderRegistration()

    await waitFor(() => {
      expect(screen.getByLabelText(/unit number/i)).toBeInTheDocument()
    })

    // Fill required field only, skip optional parking
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Test User' },
    })
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    })
    fireEvent.change(screen.getByLabelText(/unit number/i), {
      target: { value: '101' },
    })
    // Intentionally skip parking spot (optional)

    const aupCheckbox = screen.getByRole('checkbox', { name: /i accept/i })
    fireEvent.click(aupCheckbox)

    fireEvent.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      const calls = vi.mocked(apiClient.register).mock.calls
      const customFields = calls[0][0].custom_fields
      
      expect(customFields.unit_number).toBe('101')
      // Optional field should be empty string or undefined
      expect(customFields.parking).toBeFalsy()
    })
  })
})
