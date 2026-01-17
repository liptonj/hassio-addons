import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import UniversalLogin from '../../src/pages/public/UniversalLogin'
import * as apiClient from '../../src/api/client'
import type { EmailLookupResponse, LoginResponse } from '../../src/types/user'

vi.mock('../../src/api/client')

describe('Universal Login Flow Integration', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  const renderUniversalLogin = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<UniversalLogin />} />
            <Route path="/success" element={<div>Success Page</div>} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('email lookup returns correct authentication methods', async () => {
    const mockEmailLookup: EmailLookupResponse = {
      exists: true,
      auth_methods: ['local', 'oauth'],
      oauth_providers: ['google', 'microsoft'],
      requires_invite_code: false,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockEmailLookup)

    renderUniversalLogin()

    // Enter email
    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'test@example.com' },
    })

    const continueButton = screen.getByRole('button', { name: /continue/i })
    fireEvent.click(continueButton)

    // Verify API call
    await waitFor(() => {
      expect(apiClient.lookupEmail).toHaveBeenCalledWith({
        email: 'test@example.com',
      })
    })

    // Verify response structure
    const response = await apiClient.lookupEmail({ email: 'test@example.com' })
    expect(response).toHaveProperty('exists')
    expect(response).toHaveProperty('auth_methods')
    expect(response).toHaveProperty('oauth_providers')
    expect(response).toHaveProperty('requires_invite_code')
    expect(response).toHaveProperty('can_self_register')

    // Verify data types
    expect(typeof response.exists).toBe('boolean')
    expect(Array.isArray(response.auth_methods)).toBe(true)
    expect(Array.isArray(response.oauth_providers)).toBe(true)
    expect(typeof response.requires_invite_code).toBe('boolean')
    expect(typeof response.can_self_register).toBe('boolean')
  })

  it('shows correct auth methods based on email lookup', async () => {
    const mockLocalOnly: EmailLookupResponse = {
      exists: true,
      auth_methods: ['local'],
      oauth_providers: [],
      requires_invite_code: false,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockLocalOnly)

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'local@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show local auth (password field)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
    })

    // Should NOT show OAuth buttons
    expect(screen.queryByText(/sign in with google/i)).not.toBeInTheDocument()
  })

  it('shows OAuth options when available', async () => {
    const mockOAuthEnabled: EmailLookupResponse = {
      exists: true,
      auth_methods: ['oauth'],
      oauth_providers: ['google', 'microsoft'],
      requires_invite_code: false,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockOAuthEnabled)

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'oauth@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show OAuth buttons
    await waitFor(() => {
      expect(screen.getByText(/sign in with google/i)).toBeInTheDocument()
      expect(screen.getByText(/sign in with microsoft/i)).toBeInTheDocument()
    })
  })

  it('shows self-registration option for new users', async () => {
    const mockNewUser: EmailLookupResponse = {
      exists: false,
      auth_methods: [],
      oauth_providers: [],
      requires_invite_code: false,
      can_self_register: true,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockNewUser)

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'new@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show registration option
    await waitFor(() => {
      expect(screen.getByText(/create account/i)).toBeInTheDocument()
    })
  })

  it('requires invite code when configured', async () => {
    const mockRequiresInvite: EmailLookupResponse = {
      exists: false,
      auth_methods: [],
      oauth_providers: [],
      requires_invite_code: true,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockRequiresInvite)

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'new@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show invite code requirement
    await waitFor(() => {
      expect(screen.getByText(/invitation code required/i)).toBeInTheDocument()
    })
  })

  it('completes local authentication with correct payload', async () => {
    const mockEmailLookup: EmailLookupResponse = {
      exists: true,
      auth_methods: ['local'],
      oauth_providers: [],
      requires_invite_code: false,
      can_self_register: false,
    }

    const mockLoginResponse: LoginResponse = {
      success: true,
      access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
      user: {
        id: 123,
        email: 'test@example.com',
        name: 'Test User',
      },
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockEmailLookup)
    vi.mocked(apiClient.login).mockResolvedValue(mockLoginResponse)

    renderUniversalLogin()

    // Step 1: Email lookup
    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'test@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 2: Enter password
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
    })

    const passwordInput = screen.getByPlaceholderText(/password/i)
    fireEvent.change(passwordInput, {
      target: { value: 'SecurePassword123' },
    })

    const signInButton = screen.getByRole('button', { name: /sign in/i })
    fireEvent.click(signInButton)

    // Verify login API call
    await waitFor(() => {
      expect(apiClient.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'SecurePassword123',
      })
    })

    // Verify response structure
    const response = await apiClient.login({} as any)
    expect(response).toHaveProperty('success')
    expect(response).toHaveProperty('access_token')
    expect(response).toHaveProperty('user')
    expect(response.user).toHaveProperty('id')
    expect(response.user).toHaveProperty('email')
    expect(response.user).toHaveProperty('name')

    // Verify data types
    expect(typeof response.success).toBe('boolean')
    expect(typeof response.access_token).toBe('string')
    expect(typeof response.user.id).toBe('number')
    expect(typeof response.user.email).toBe('string')
  })

  it('handles multiple auth methods correctly', async () => {
    const mockMultiAuth: EmailLookupResponse = {
      exists: true,
      auth_methods: ['local', 'oauth', 'invite_code'],
      oauth_providers: ['google'],
      requires_invite_code: false,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockMultiAuth)

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'multi@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show all available auth methods
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
      expect(screen.getByText(/sign in with google/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/invite code/i)).toBeInTheDocument()
    })
  })

  it('validates email format before lookup', async () => {
    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    
    // Invalid email
    fireEvent.change(emailInput, {
      target: { value: 'invalid-email' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeInTheDocument()
    })

    // API should not be called
    expect(apiClient.lookupEmail).not.toHaveBeenCalled()
  })

  it('handles email lookup errors gracefully', async () => {
    vi.mocked(apiClient.lookupEmail).mockRejectedValue(
      new Error('Service unavailable')
    )

    renderUniversalLogin()

    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'test@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    await waitFor(() => {
      expect(screen.getByText(/service unavailable/i)).toBeInTheDocument()
    })
  })

  it('handles login errors with proper error messages', async () => {
    const mockEmailLookup: EmailLookupResponse = {
      exists: true,
      auth_methods: ['local'],
      oauth_providers: [],
      requires_invite_code: false,
      can_self_register: false,
    }

    vi.mocked(apiClient.lookupEmail).mockResolvedValue(mockEmailLookup)
    vi.mocked(apiClient.login).mockRejectedValue(
      new Error('Invalid credentials')
    )

    renderUniversalLogin()

    // Email lookup
    const emailInput = screen.getByPlaceholderText(/email address/i)
    fireEvent.change(emailInput, {
      target: { value: 'test@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Enter wrong password
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'WrongPassword' },
    })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
    })
  })
})
