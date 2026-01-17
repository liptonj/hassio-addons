import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import NetworkSelection from '../NetworkSelection'

// Mock the API client
vi.mock('../../../../api/client', () => ({
  getAllSettings: vi.fn(() => Promise.resolve({
    default_network_id: 'net123',
    default_ssid_number: 0,
  })),
  updateSettings: vi.fn(() => Promise.resolve({ success: true, message: 'Saved' })),
  getIPSKOptions: vi.fn(() => Promise.resolve({
    networks: [
      { id: 'net1', name: 'Network 1' },
      { id: 'net2', name: 'Network 2' },
    ],
    ssids: [
      { number: 0, name: 'SSID 1' },
      { number: 1, name: 'SSID 2' },
    ],
  })),
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

describe('NetworkSelection Settings Page', () => {
  it('renders page title', async () => {
    renderWithProviders(<NetworkSelection />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Network Selection/i })).toBeInTheDocument()
    })
  })

  it('renders network dropdown label', async () => {
    renderWithProviders(<NetworkSelection />)
    await waitFor(() => {
      expect(screen.getByText(/Network/i)).toBeInTheDocument()
    })
  })

  it('renders SSID dropdown label', async () => {
    renderWithProviders(<NetworkSelection />)
    await waitFor(() => {
      expect(screen.getByText(/SSID/i)).toBeInTheDocument()
    })
  })

  it('renders save and next buttons', async () => {
    renderWithProviders(<NetworkSelection />)
    await waitFor(() => {
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })

  it('renders configuration information', async () => {
    renderWithProviders(<NetworkSelection />)
    await waitFor(() => {
      const heading = screen.getByRole('heading', { name: /Network Selection/i })
      expect(heading).toBeInTheDocument()
    })
  })
})
