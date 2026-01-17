import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InviteCode from '../InviteCode'

// Mock the API client
vi.mock('../../../api/client', () => ({
  validateInviteCode: vi.fn(),
  register: vi.fn(),
  getPortalOptions: vi.fn(() => Promise.resolve({
    property_name: 'Test Property',
    logo_url: '',
    primary_color: '#00A4E4',
  })),
}))

// Import mocked functions
import { validateInviteCode, register } from '../../../api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
})

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('InviteCode Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient.clear()
  })

  describe('Code Entry Step', () => {
    it('renders the code entry form', () => {
      renderWithProviders(<InviteCode />)
      
      expect(screen.getByText(/enter your invite code/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText('XXXXXX')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument()
    })

    it('shows error for empty code submission', async () => {
      renderWithProviders(<InviteCode />)
      
      const submitButton = screen.getByRole('button', { name: /continue/i })
      fireEvent.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/please enter an invite code/i)).toBeInTheDocument()
      })
    })

    it('converts code to uppercase', () => {
      renderWithProviders(<InviteCode />)
      
      const input = screen.getByPlaceholderText('XXXXXX') as HTMLInputElement
      fireEvent.change(input, { target: { value: 'abcdef' } })
      
      expect(input.value).toBe('ABCDEF')
    })

    it('removes special characters from code', () => {
      renderWithProviders(<InviteCode />)
      
      const input = screen.getByPlaceholderText('XXXXXX') as HTMLInputElement
      fireEvent.change(input, { target: { value: 'ABC-123!' } })
      
      expect(input.value).toBe('ABC123')
    })

    it('shows error for invalid code', async () => {
      ;(validateInviteCode as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        valid: false,
        error: 'Invalid code',
      })

      renderWithProviders(<InviteCode />)
      
      const input = screen.getByPlaceholderText('XXXXXX')
      fireEvent.change(input, { target: { value: 'INVALID' } })
      
      const submitButton = screen.getByRole('button', { name: /continue/i })
      fireEvent.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/invalid code/i)).toBeInTheDocument()
      })
    })

    it('proceeds to form on valid code', async () => {
      ;(validateInviteCode as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        valid: true,
        code_info: {
          max_uses: 10,
          uses: 2,
          remaining_uses: 8,
        },
      })

      renderWithProviders(<InviteCode />)
      
      const input = screen.getByPlaceholderText('XXXXXX')
      fireEvent.change(input, { target: { value: 'VALIDCODE' } })
      
      const submitButton = screen.getByRole('button', { name: /continue/i })
      fireEvent.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/almost there/i)).toBeInTheDocument()
      })
    })
  })

  describe('Registration Form Step', () => {
    beforeEach(async () => {
      ;(validateInviteCode as ReturnType<typeof vi.fn>).mockResolvedValue({
        valid: true,
        code_info: { max_uses: 10, uses: 0, remaining_uses: 10 },
      })
    })

    it('shows name and email fields after valid code', async () => {
      renderWithProviders(<InviteCode />)
      
      // Enter valid code
      const input = screen.getByPlaceholderText('XXXXXX')
      fireEvent.change(input, { target: { value: 'VALID123' } })
      fireEvent.click(screen.getByRole('button', { name: /continue/i }))
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/john smith/i)).toBeInTheDocument()
        expect(screen.getByPlaceholderText(/john@example.com/i)).toBeInTheDocument()
      })
    })

    it('validates required fields', async () => {
      renderWithProviders(<InviteCode />)
      
      // Get to form step
      const input = screen.getByPlaceholderText('XXXXXX')
      fireEvent.change(input, { target: { value: 'VALID123' } })
      fireEvent.click(screen.getByRole('button', { name: /continue/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/almost there/i)).toBeInTheDocument()
      })
      
      // Submit empty form
      fireEvent.click(screen.getByRole('button', { name: /get wifi access/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        expect(screen.getByText(/email is required/i)).toBeInTheDocument()
      })
    })

    it('validates email format', async () => {
      renderWithProviders(<InviteCode />)
      
      // Get to form step
      const codeInput = screen.getByPlaceholderText('XXXXXX')
      fireEvent.change(codeInput, { target: { value: 'VALID123' } })
      fireEvent.click(screen.getByRole('button', { name: /continue/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/almost there/i)).toBeInTheDocument()
      })
      
      // Enter invalid email
      const nameInput = screen.getByPlaceholderText(/john smith/i)
      const emailInput = screen.getByPlaceholderText(/john@example.com/i)
      
      fireEvent.change(nameInput, { target: { value: 'Test User' } })
      fireEvent.change(emailInput, { target: { value: 'invalid-email' } })
      
      fireEvent.click(screen.getByRole('button', { name: /get wifi access/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/please enter a valid email/i)).toBeInTheDocument()
      })
    })
  })

  describe('Success Step', () => {
    it('shows credentials after successful registration', async () => {
      ;(validateInviteCode as ReturnType<typeof vi.fn>).mockResolvedValue({
        valid: true,
        code_info: { max_uses: 10, uses: 0, remaining_uses: 10 },
      })
      ;(register as ReturnType<typeof vi.fn>).mockResolvedValue({
        success: true,
        ssid_name: 'Test-WiFi',
        passphrase: 'TestPass123',
        qr_code: 'data:image/png;base64,ABC123',
      })

      renderWithProviders(<InviteCode />)
      
      // Enter code
      fireEvent.change(screen.getByPlaceholderText('XXXXXX'), { target: { value: 'VALID' } })
      fireEvent.click(screen.getByRole('button', { name: /continue/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/almost there/i)).toBeInTheDocument()
      })
      
      // Fill form
      fireEvent.change(screen.getByPlaceholderText(/john smith/i), { target: { value: 'Test User' } })
      fireEvent.change(screen.getByPlaceholderText(/john@example.com/i), { target: { value: 'test@example.com' } })
      fireEvent.click(screen.getByRole('button', { name: /get wifi access/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/you're connected/i)).toBeInTheDocument()
        expect(screen.getByText('Test-WiFi')).toBeInTheDocument()
        expect(screen.getByText('TestPass123')).toBeInTheDocument()
      })
    })
  })

  describe('Pending Approval Step', () => {
    it('shows pending message when approval is required', async () => {
      ;(validateInviteCode as ReturnType<typeof vi.fn>).mockResolvedValue({
        valid: true,
        code_info: { max_uses: 10, uses: 0, remaining_uses: 10 },
      })
      ;(register as ReturnType<typeof vi.fn>).mockResolvedValue({
        success: true,
        ssid_name: 'Test-WiFi',
        pending_approval: true,
        pending_message: 'Your registration is pending admin approval.',
      })

      renderWithProviders(<InviteCode />)
      
      // Complete flow
      fireEvent.change(screen.getByPlaceholderText('XXXXXX'), { target: { value: 'VALID' } })
      fireEvent.click(screen.getByRole('button', { name: /continue/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/almost there/i)).toBeInTheDocument()
      })
      
      fireEvent.change(screen.getByPlaceholderText(/john smith/i), { target: { value: 'Test User' } })
      fireEvent.change(screen.getByPlaceholderText(/john@example.com/i), { target: { value: 'test@example.com' } })
      fireEvent.click(screen.getByRole('button', { name: /get wifi access/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/pending approval/i)).toBeInTheDocument()
        expect(screen.getByText(/your registration is pending admin approval/i)).toBeInTheDocument()
      })
    })
  })
})
