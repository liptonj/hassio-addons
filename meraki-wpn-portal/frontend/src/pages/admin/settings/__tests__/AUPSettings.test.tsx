import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import AUPSettings from '../AUPSettings'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  aup_enabled: true,
  aup_text: 'Test AUP text',
  aup_url: 'https://example.com/aup',
  aup_version: 1,
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

describe('AUPSettings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders page title', async () => {
    renderWithProviders(<AUPSettings />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    })
  })

  it('renders form with checkbox', async () => {
    renderWithProviders(<AUPSettings />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })
})
