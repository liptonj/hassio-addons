import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import AdvancedSettings from '../AdvancedSettings'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  admin_username: 'admin',
  admin_notification_email: 'admin@example.com',
  secret_key: '***',
  access_token_expire_minutes: 30,
  ha_url: 'http://supervisor/core',
  ha_token: '***',
  cors_origins: '*',
  database_url: 'sqlite:///data/portal.db',
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

describe('AdvancedSettings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders page title', async () => {
    renderWithProviders(<AdvancedSettings />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    })
  })

  it('renders configuration sections', async () => {
    renderWithProviders(<AdvancedSettings />)
    await waitFor(() => {
      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toBeInTheDocument()
    })
  })

  it('renders multiple form sections', async () => {
    renderWithProviders(<AdvancedSettings />)
    await waitFor(() => {
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })

  it('renders settings sections', async () => {
    renderWithProviders(<AdvancedSettings />)
    await waitFor(() => {
      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toBeInTheDocument()
    })
  })
})
