import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import LoginMethods from '../LoginMethods'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  universal_login_enabled: true,
  show_login_method_selector: false,
  auth_method_local: true,
  auth_method_oauth: false,
  auth_method_invite_code: true,
  auth_method_self_registration: true,
}

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

describe('LoginMethods Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders page title', async () => {
    renderWithProviders(<LoginMethods />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Login Methods/i })).toBeInTheDocument()
    })
  })

  it('renders form with checkboxes', async () => {
    renderWithProviders(<LoginMethods />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })

  it('renders login method options', async () => {
    renderWithProviders(<LoginMethods />)
    await waitFor(() => {
      expect(screen.getByText(/Universal Login|Login/i)).toBeInTheDocument()
    })
  })
})
