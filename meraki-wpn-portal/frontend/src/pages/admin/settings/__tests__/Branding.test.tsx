import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import Branding from '../Branding'
import * as client from '../../../../api/client'

// Mock API calls
vi.mock('../../../../api/client')

const mockSettings = {
  property_name: 'Test Property',
  logo_url: 'https://example.com/logo.png',
  primary_color: '#00A4E4',
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

describe('Branding Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getAllSettings).mockResolvedValue(mockSettings)
    vi.mocked(client.updateSettings).mockResolvedValue({
      message: 'Settings saved successfully',
      requires_restart: false,
    })
  })

  it('renders without errors', async () => {
    renderWithProviders(<Branding />)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Portal Branding', level: 1 })).toBeInTheDocument()
    })
  })

  it('loads and displays current settings', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const propertyNameInput = screen.getByPlaceholderText('My Property') as HTMLInputElement
      expect(propertyNameInput.value).toBe('Test Property')
    })

    const logoUrlInput = screen.getByPlaceholderText('https://example.com/logo.png') as HTMLInputElement
    expect(logoUrlInput.value).toBe('https://example.com/logo.png')
  })

  it('updates form fields correctly', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const propertyNameInput = screen.getByPlaceholderText('My Property') as HTMLInputElement
      expect(propertyNameInput).toBeInTheDocument()
    })

    const propertyNameInput = screen.getByPlaceholderText('My Property') as HTMLInputElement
    fireEvent.change(propertyNameInput, { target: { value: 'New Property Name' } })
    
    expect(propertyNameInput.value).toBe('New Property Name')
  })

  it('calls API with correct payload on save', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const saveButton = screen.getByText('Save Changes')
      expect(saveButton).toBeInTheDocument()
    })

    const propertyNameInput = screen.getByPlaceholderText('My Property') as HTMLInputElement
    fireEvent.change(propertyNameInput, { target: { value: 'Updated Property' } })

    const saveButton = screen.getByText('Save Changes')
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(client.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          property_name: 'Updated Property',
        })
      )
    })
  })

  it('displays success notification after save', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const saveButton = screen.getByText('Save Changes')
      expect(saveButton).toBeInTheDocument()
    })

    const saveButton = screen.getByText('Save Changes')
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText('Settings saved successfully')).toBeInTheDocument()
    })
  })

  it('displays error notification on save failure', async () => {
    vi.mocked(client.updateSettings).mockRejectedValue(new Error('Network error'))

    renderWithProviders(<Branding />)

    await waitFor(() => {
      const saveButton = screen.getByText('Save Changes')
      expect(saveButton).toBeInTheDocument()
    })

    const saveButton = screen.getByText('Save Changes')
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('color picker updates primary color', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const colorInput = screen.getByDisplayValue('#00A4E4') as HTMLInputElement
      expect(colorInput).toBeInTheDocument()
    })

    const colorInputs = screen.getAllByDisplayValue('#00A4E4') as HTMLInputElement[]
    const colorPicker = colorInputs[0]
    
    fireEvent.change(colorPicker, { target: { value: '#FF5733' } })
    expect(colorPicker.value).toBe('#FF5733')
  })

  it('applies dark mode classes correctly', async () => {
    renderWithProviders(<Branding />)

    await waitFor(() => {
      const heading = screen.getByRole('heading', { name: 'Portal Branding', level: 1 })
      expect(heading).toHaveClass('text-2xl', 'font-bold')
    })
  })
})
