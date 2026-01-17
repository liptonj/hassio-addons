import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import RegistrationBasics from '../RegistrationBasics'

// Mock the API client
vi.mock('../../../../api/client', () => ({
  getAllSettings: vi.fn(() => Promise.resolve({
    allow_user_signup: true,
    allow_guest_registration: false,
    auth_self_registration: true,
    auth_email_verification: true,
    auth_sms_verification: false,
    require_unit_number: false,
  })),
  updateSettings: vi.fn(() => Promise.resolve({ success: true, message: 'Saved' })),
}))

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {component}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RegistrationBasics Settings Page', () => {
  it('renders page title', async () => {
    renderWithProviders(<RegistrationBasics />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Registration Basics/i })).toBeInTheDocument()
    })
  })

  it('renders form with checkboxes', async () => {
    renderWithProviders(<RegistrationBasics />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })

  it('renders verification options', async () => {
    renderWithProviders(<RegistrationBasics />)
    await waitFor(() => {
      expect(screen.getByText(/Verification/i)).toBeInTheDocument()
    })
  })

  it('renders save button', async () => {
    renderWithProviders(<RegistrationBasics />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Save/i })).toBeInTheDocument()
    })
  })
})
