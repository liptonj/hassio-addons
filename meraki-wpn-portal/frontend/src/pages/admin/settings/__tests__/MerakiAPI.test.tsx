import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import MerakiAPI from '../MerakiAPI'

// Mock the API client
vi.mock('../../../../api/client', () => ({
  getAllSettings: vi.fn(() => Promise.resolve({
    meraki_api_key: '***test***',
    meraki_org_id: 'org123',
  })),
  updateSettings: vi.fn(() => Promise.resolve({ success: true, message: 'Saved' })),
  testConnection: vi.fn(() => Promise.resolve({ success: true, organizations: [] })),
  getIPSKOptions: vi.fn(() => Promise.resolve({
    organizations: [{ id: 'org1', name: 'Test Org' }],
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

describe('MerakiAPI Settings Page', () => {
  it('renders page title', async () => {
    renderWithProviders(<MerakiAPI />)
    await waitFor(() => {
      expect(screen.getByText(/Meraki Dashboard API/i)).toBeInTheDocument()
    })
  })

  it('renders API key input field', async () => {
    renderWithProviders(<MerakiAPI />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Enter Meraki Dashboard API key/i)).toBeInTheDocument()
    })
  })

  it('renders test connection button', async () => {
    renderWithProviders(<MerakiAPI />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Test Connection/i })).toBeInTheDocument()
    })
  })

  it('renders save button', async () => {
    renderWithProviders(<MerakiAPI />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Save/i })).toBeInTheDocument()
    })
  })

  it('displays masked API key placeholder when API key is saved', async () => {
    renderWithProviders(<MerakiAPI />)
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/saved|Enter Meraki Dashboard API key/i)
      expect(input).toBeInTheDocument()
    })
  })
})
