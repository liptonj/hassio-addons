import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import IPSKInviteSettings from '../IPSKInviteSettings'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  ipsk_expiration_check_enabled: true,
  ipsk_expiration_check_interval_hours: 1,
  ipsk_cleanup_action: 'soft_delete',
  ipsk_expiration_warning_days: '7,3,1',
  ipsk_expiration_email_enabled: false,
  auth_invite_codes: true,
  invite_code_email_restriction: false,
  invite_code_single_use: false,
}

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{component}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('IPSKInviteSettings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders page title', async () => {
    renderWithProviders(<IPSKInviteSettings />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    })
  })

  it('renders form with checkboxes', async () => {
    renderWithProviders(<IPSKInviteSettings />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })

  it('renders settings sections', async () => {
    renderWithProviders(<IPSKInviteSettings />)
    await waitFor(() => {
      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toBeInTheDocument()
    })
  })
})
