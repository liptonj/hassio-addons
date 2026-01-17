import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import SSIDConfiguration from '../SSIDConfiguration'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')

const mockSettings = {
  default_network_id: 'net123',
  default_ssid_number: 1,
  default_group_policy_id: 'gp123',
  default_group_policy_name: 'Test Policy',
}

const mockIpskOptions = {
  networks: [{ id: 'net123', name: 'Test Network' }],
  ssids: [{ number: 1, name: 'Test SSID' }],
  group_policies: [
    { id: 'gp123', name: 'Test Policy' },
    { id: 'gp456', name: 'Guest Policy' },
  ],
}

function renderWithProviders(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{component}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('SSIDConfiguration Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.getIPSKOptions).mockResolvedValue(mockIpskOptions)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders without errors', async () => {
    renderWithProviders(<SSIDConfiguration />)
    
    await waitFor(() => {
      expect(screen.getByText('SSID Configuration')).toBeInTheDocument()
    })
  })

  it('displays group policy assignment section', async () => {
    renderWithProviders(<SSIDConfiguration />)

    await waitFor(() => {
      expect(screen.getByText('Group Policy Assignment')).toBeInTheDocument()
    })
  })

  it('displays two-tier model explanation', async () => {
    renderWithProviders(<SSIDConfiguration />)

    await waitFor(() => {
      expect(screen.getByText(/Two-Tier Access Model/i)).toBeInTheDocument()
    })
  })

  it('displays registered users policy dropdown', async () => {
    renderWithProviders(<SSIDConfiguration />)

    await waitFor(() => {
      expect(screen.getByText(/Registered Users Group Policy/i)).toBeInTheDocument()
    })
  })

  it('displays guest policy dropdown', async () => {
    renderWithProviders(<SSIDConfiguration />)

    await waitFor(() => {
      expect(screen.getByText(/Guest\/Default Users Group Policy/i)).toBeInTheDocument()
    })
  })

  it('has navigation buttons', async () => {
    renderWithProviders(<SSIDConfiguration />)

    await waitFor(() => {
      expect(screen.getByText(/Back to Network Selection/i)).toBeInTheDocument()
      expect(screen.getByText(/Next: Run WPN Wizard/i)).toBeInTheDocument()
    })
  })
})
