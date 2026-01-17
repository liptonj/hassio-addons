import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AuthenticationConfig from '../AuthenticationConfig'
import * as radiusClient from '../../../api/radiusClient'

// Mock the API client
vi.mock('../../../api/radiusClient', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock the portal API client
vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('AuthenticationConfig', () => {
  let queryClient: QueryClient
  const mockRadiusApi = radiusClient.default as any

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <AuthenticationConfig />
      </QueryClientProvider>
    )
  }

  describe('EAP Methods Tab', () => {
    beforeEach(() => {
      mockRadiusApi.get.mockImplementation((url: string) => {
        if (url === '/api/v1/eap/config') {
          return Promise.resolve({
            data: [
              {
                id: 1,
                name: 'Default EAP Config',
                description: 'Default configuration',
                default_eap_type: 'tls',
                enabled_methods: ['tls', 'ttls'],
                tls_min_version: '1.2',
                tls_max_version: '1.3',
                is_active: true,
              },
            ],
          })
        }
        if (url === '/api/v1/eap/methods') {
          return Promise.resolve({
            data: [
              {
                id: 1,
                method_name: 'tls',
                is_enabled: true,
                auth_attempts: 100,
                auth_successes: 95,
                auth_failures: 5,
              },
              {
                id: 2,
                method_name: 'ttls',
                is_enabled: false,
                auth_attempts: 50,
                auth_successes: 45,
                auth_failures: 5,
              },
            ],
          })
        }
        return Promise.resolve({ data: [] })
      })
    })

    it('should display EAP Methods tab by default', async () => {
      renderComponent()

      await waitFor(() => {
        expect(screen.getByText('EAP Authentication Methods')).toBeInTheDocument()
      })

      expect(screen.getByText('TLS')).toBeInTheDocument()
      expect(screen.getByText('TTLS')).toBeInTheDocument()
    })

    it('should show EAP method status', async () => {
      renderComponent()

      await waitFor(() => {
        expect(screen.getByText('TLS')).toBeInTheDocument()
      })

      const tlsRow = screen.getByText('TLS').closest('div')?.parentElement
      expect(within(tlsRow!).getByText('Enabled')).toBeInTheDocument()
    })

    it('should toggle EAP method enable/disable', async () => {
      mockRadiusApi.post.mockResolvedValue({ data: {} })

      renderComponent()

      await waitFor(() => {
        expect(screen.getByText('TLS')).toBeInTheDocument()
      })

      const checkbox = screen.getAllByRole('checkbox')[0]
      expect(checkbox).toBeChecked()

      await userEvent.click(checkbox)

      await waitFor(() => {
        expect(mockRadiusApi.post).toHaveBeenCalledWith(
          '/api/v1/eap/methods/tls/disable',
          expect.anything()
        )
      })
    })
  })

  describe('MAC-BYPASS Tab', () => {
    beforeEach(() => {
      mockRadiusApi.get.mockImplementation((url: string) => {
        if (url === '/api/v1/mac-bypass/config') {
          return Promise.resolve({
            data: [
              {
                id: 1,
                name: 'Test Bypass',
                description: 'Test description',
                mac_addresses: ['aa:bb:cc:dd:ee:ff'],
                bypass_mode: 'whitelist',
                require_registration: false,
                is_active: true,
                created_at: '2024-01-01T00:00:00Z',
                updated_at: '2024-01-01T00:00:00Z',
              },
            ],
          })
        }
        return Promise.resolve({ data: [] })
      })
    })

    it('should display MAC-BYPASS tab', async () => {
      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Test Bypass')).toBeInTheDocument()
      })
    })

    it('should show MAC bypass configurations in table', async () => {
      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Test Bypass')).toBeInTheDocument()
        expect(screen.getByText('whitelist')).toBeInTheDocument()
        expect(screen.getByText('1 address')).toBeInTheDocument()
      })
    })

    it('should open modal to create new MAC bypass config', async () => {
      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Add MAC Bypass Config')).toBeInTheDocument()
      })

      const addButton = screen.getByText('Add MAC Bypass Config')
      await userEvent.click(addButton)

      await waitFor(() => {
        expect(screen.getByText('Add MAC Bypass Config')).toBeInTheDocument()
      })

      expect(screen.getByLabelText('Name')).toBeInTheDocument()
      expect(screen.getByLabelText('Bypass Mode')).toBeInTheDocument()
    })

    it('should create new MAC bypass config', async () => {
      mockRadiusApi.post.mockResolvedValue({
        data: {
          id: 2,
          name: 'New Bypass',
          mac_addresses: ['aa:bb:cc:dd:ee:ff'],
          bypass_mode: 'whitelist',
          is_active: true,
        },
      })

      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Add MAC Bypass Config')).toBeInTheDocument()
      })

      const addButton = screen.getByText('Add MAC Bypass Config')
      await userEvent.click(addButton)

      await waitFor(() => {
        const nameInput = screen.getByLabelText('Name')
        await userEvent.type(nameInput, 'New Bypass')

        const macInput = screen.getByPlaceholderText('aa:bb:cc:dd:ee:ff')
        await userEvent.type(macInput, 'aa:bb:cc:dd:ee:ff')

        const addMacButton = screen.getByText('Add')
        await userEvent.click(addMacButton)

        const saveButton = screen.getByText('Save')
        await userEvent.click(saveButton)
      })

      await waitFor(() => {
        expect(mockRadiusApi.post).toHaveBeenCalledWith(
          '/api/v1/mac-bypass/config',
          expect.objectContaining({
            name: 'New Bypass',
            mac_addresses: ['aa:bb:cc:dd:ee:ff'],
          })
        )
      })
    })

    it('should delete MAC bypass config', async () => {
      mockRadiusApi.delete.mockResolvedValue({})

      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Test Bypass')).toBeInTheDocument()
      })

      // Find delete button (trash icon)
      const deleteButtons = screen.getAllByTitle('Delete')
      await userEvent.click(deleteButtons[0])

      // Confirm deletion
      window.confirm = vi.fn(() => true)

      await waitFor(() => {
        expect(mockRadiusApi.delete).toHaveBeenCalledWith(
          '/api/v1/mac-bypass/config/1'
        )
      })
    })
  })

  describe('PSK Authentication Tab', () => {
    it('should display PSK Authentication tab', async () => {
      mockRadiusApi.get.mockResolvedValue({ data: [] })
      renderComponent()

      const pskTab = screen.getByText('PSK Authentication')
      await userEvent.click(pskTab)

      await waitFor(() => {
        expect(screen.getByText('PSK Authentication')).toBeInTheDocument()
        expect(screen.getByText('Generic PSK')).toBeInTheDocument()
        expect(screen.getByText('User PSK')).toBeInTheDocument()
      })
    })

    it('should show PSK information', async () => {
      mockRadiusApi.get.mockResolvedValue({ data: [] })
      renderComponent()

      const pskTab = screen.getByText('PSK Authentication')
      await userEvent.click(pskTab)

      await waitFor(() => {
        expect(
          screen.getByText(/Generic PSK allows all MAC addresses/)
        ).toBeInTheDocument()
        expect(
          screen.getByText(/User-specific PSK configurations are managed/)
        ).toBeInTheDocument()
      })
    })
  })

  describe('Notifications', () => {
    it('should show success notification on create', async () => {
      mockRadiusApi.get.mockResolvedValue({ data: [] })
      mockRadiusApi.post.mockResolvedValue({
        data: {
          id: 1,
          name: 'New Config',
          mac_addresses: [],
          bypass_mode: 'whitelist',
          is_active: true,
        },
      })

      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Add MAC Bypass Config')).toBeInTheDocument()
      })

      const addButton = screen.getByText('Add MAC Bypass Config')
      await userEvent.click(addButton)

      await waitFor(async () => {
        const nameInput = screen.getByLabelText('Name')
        await userEvent.type(nameInput, 'New Config')

        const saveButton = screen.getByText('Save')
        await userEvent.click(saveButton)
      })

      await waitFor(() => {
        expect(
          screen.getByText(/MAC bypass config created successfully/)
        ).toBeInTheDocument()
      })
    })

    it('should show error notification on failure', async () => {
      mockRadiusApi.get.mockResolvedValue({ data: [] })
      mockRadiusApi.post.mockRejectedValue(
        new Error('Failed to create config')
      )

      renderComponent()

      const macBypassTab = screen.getByText('MAC-BYPASS')
      await userEvent.click(macBypassTab)

      await waitFor(() => {
        expect(screen.getByText('Add MAC Bypass Config')).toBeInTheDocument()
      })

      const addButton = screen.getByText('Add MAC Bypass Config')
      await userEvent.click(addButton)

      await waitFor(async () => {
        const nameInput = screen.getByLabelText('Name')
        await userEvent.type(nameInput, 'New Config')

        const saveButton = screen.getByText('Save')
        await userEvent.click(saveButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Failed to create config')).toBeInTheDocument()
      })
    })
  })
})
