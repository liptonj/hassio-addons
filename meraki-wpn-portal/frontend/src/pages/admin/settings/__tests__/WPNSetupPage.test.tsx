import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import WPNSetupPage from '../WPNSetupPage'
import * as client from '../../../../api/client'

vi.mock('../../../../api/client')
vi.mock('qrcode.react', () => ({
  QRCodeSVG: () => <div>QR Code</div>,
}))
vi.mock('../../../../components/WPNSetup', () => ({
  default: () => <div>WPN Setup Wizard</div>,
}))

const mockSettings = {
  default_network_id: 'net123',
  default_ssid_number: 1,
  default_group_policy_id: 'gp123',
  default_group_policy_name: 'Test Policy',
  default_ssid_psk: 'test-password-123',
  splash_page_url: 'https://portal.example.com/splash',
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

describe('WPNSetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.getIPSKOptions).mockResolvedValue({
      networks: [],
      ssids: [],
      group_policies: [],
    })
  })

  it('renders without errors', async () => {
    renderWithProviders(<WPNSetupPage />)
    
    await waitFor(() => {
      expect(screen.getByText('WPN Setup Wizard')).toBeInTheDocument()
    })
  })

  it('displays WPN wizard component when prerequisites met', async () => {
    renderWithProviders(<WPNSetupPage />)

    await waitFor(() => {
      expect(screen.getByText('WPN Setup Wizard')).toBeInTheDocument()
    })
  })

  it('displays two-tier access model info', async () => {
    renderWithProviders(<WPNSetupPage />)

    await waitFor(() => {
      expect(screen.getByText('Two-Tier Access Model')).toBeInTheDocument()
    })
  })

  it('displays guest access credentials section', async () => {
    renderWithProviders(<WPNSetupPage />)

    await waitFor(() => {
      expect(screen.getByText('Guest Access Credentials')).toBeInTheDocument()
    })
  })

  it('has navigation buttons', async () => {
    renderWithProviders(<WPNSetupPage />)

    await waitFor(() => {
      expect(screen.getByText(/Back to SSID Configuration/i)).toBeInTheDocument()
      expect(screen.getByText(/Complete Setup/i)).toBeInTheDocument()
    })
  })
})
