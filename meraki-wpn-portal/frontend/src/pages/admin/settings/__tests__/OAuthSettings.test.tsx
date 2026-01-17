import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import OAuthSettings from '../OAuthSettings'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  enable_oauth: false,
  oauth_provider: 'none',
  oauth_admin_only: false,
  oauth_auto_provision: true,
  oauth_callback_url: '',
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

describe('OAuthSettings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders page title', async () => {
    renderWithProviders(<OAuthSettings />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    })
  })

  it('renders enable OAuth checkbox', async () => {
    renderWithProviders(<OAuthSettings />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })
})
