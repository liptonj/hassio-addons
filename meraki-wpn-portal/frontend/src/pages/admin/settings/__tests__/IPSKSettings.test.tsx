import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import IPSKSettings from '../IPSKSettings'

// Mock the API client
vi.mock('../../../../api/client', () => ({
  getAllSettings: vi.fn(() => Promise.resolve({
    default_ipsk_duration_hours: 168,
    passphrase_length: 12,
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

describe('IPSKSettings Page', () => {
  it('renders page title', async () => {
    renderWithProviders(<IPSKSettings />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /IPSK Settings/i })).toBeInTheDocument()
    })
  })

  it('renders duration field label', async () => {
    renderWithProviders(<IPSKSettings />)
    await waitFor(() => {
      expect(screen.getByText(/Duration/i)).toBeInTheDocument()
    })
  })

  it('renders passphrase length field label', async () => {
    renderWithProviders(<IPSKSettings />)
    await waitFor(() => {
      expect(screen.getByText(/Passphrase Length/i)).toBeInTheDocument()
    })
  })

  it('renders save button', async () => {
    renderWithProviders(<IPSKSettings />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Save/i })).toBeInTheDocument()
    })
  })
})
