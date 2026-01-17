import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QRCodeActions from '../../src/components/QRCodeActions'
import * as apiClient from '../../src/api/client'

// Mock API client
vi.mock('../../src/api/client', () => ({
  createQRToken: vi.fn(),
}))

describe('QRCodeActions', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  const defaultProps = {
    qrCodeDataUrl: 'data:image/png;base64,test',
    ssid: 'TestNetwork',
    passphrase: 'TestPassword123',
    wifiConfigString: 'WIFI:T:WPA;S:TestNetwork;P:TestPassword123;;',
  }

  const renderComponent = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <QRCodeActions {...defaultProps} {...props} />
      </QueryClientProvider>
    )
  }

  it('renders QR code with actions', () => {
    renderComponent()
    
    expect(screen.getByAltText(/wifi qr code/i)).toBeInTheDocument()
    expect(screen.getByText(/print/i)).toBeInTheDocument()
    expect(screen.getByText(/download/i)).toBeInTheDocument()
  })

  it('shows share button when ipskId is provided', () => {
    renderComponent({ ipskId: 'test-ipsk-123' })
    
    expect(screen.getByText(/share link/i)).toBeInTheDocument()
  })

  it('hides share button when ipskId is not provided', () => {
    renderComponent()
    
    expect(screen.queryByText(/share link/i)).not.toBeInTheDocument()
  })

  it('opens print window when print button clicked', () => {
    const mockOpen = vi.fn(() => ({
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    }))
    window.open = mockOpen as any

    renderComponent()
    
    const printButton = screen.getByText(/print/i)
    fireEvent.click(printButton)
    
    expect(mockOpen).toHaveBeenCalledWith('', '_blank')
  })

  it('triggers download when download button clicked', async () => {
    // Mock fetch for data URL
    global.fetch = vi.fn(() =>
      Promise.resolve({
        blob: () => Promise.resolve(new Blob(['test'])),
      })
    ) as any

    const createElementSpy = vi.spyOn(document, 'createElement')
    
    renderComponent()
    
    const downloadButton = screen.getByText(/download/i)
    fireEvent.click(downloadButton)
    
    await waitFor(() => {
      expect(createElementSpy).toHaveBeenCalledWith('a')
    })
  })

  it('creates share link when share button clicked', async () => {
    const mockToken = {
      token: 'abc123',
      public_url: 'https://example.com/wifi-qr/abc123',
      expires_at: '2026-02-14T00:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(mockToken)

    renderComponent({ ipskId: 'test-ipsk-123' })
    
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)
    
    await waitFor(() => {
      expect(screen.getByText(/share link created/i)).toBeInTheDocument()
      expect(screen.getByDisplayValue(mockToken.public_url)).toBeInTheDocument()
    })
  })

  it('shows error when share fails', async () => {
    vi.mocked(apiClient.createQRToken).mockRejectedValue(new Error('Failed to create share link'))

    renderComponent({ ipskId: 'test-ipsk-123' })
    
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)
    
    await waitFor(() => {
      expect(screen.getByText(/failed to create share link/i)).toBeInTheDocument()
    })
  })

  it('copies share URL to clipboard', async () => {
    const mockToken = {
      token: 'abc123',
      public_url: 'https://example.com/wifi-qr/abc123',
      expires_at: '2026-02-14T00:00:00Z',
    }

    vi.mocked(apiClient.createQRToken).mockResolvedValue(mockToken)
    const writeTextMock = vi.fn(() => Promise.resolve())
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    })

    renderComponent({ ipskId: 'test-ipsk-123' })
    
    // Generate share link first
    fireEvent.click(screen.getByText(/share link/i))
    
    await waitFor(() => {
      expect(screen.getByText(/share link created/i)).toBeInTheDocument()
    })
    
    // Click copy button
    const copyButton = screen.getByText(/copy/i)
    fireEvent.click(copyButton)
    
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(mockToken.public_url)
      expect(screen.getByText(/copied/i)).toBeInTheDocument()
    })
  })

  it('displays loading state while sharing', async () => {
    vi.mocked(apiClient.createQRToken).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    )

    renderComponent({ ipskId: 'test-ipsk-123' })
    
    const shareButton = screen.getByText(/share link/i)
    fireEvent.click(shareButton)
    
    expect(screen.getByText(/generating/i)).toBeInTheDocument()
  })

  it('shows error when ipskId missing for share', async () => {
    renderComponent({ ipskId: undefined })
    
    // Share button should not be visible
    expect(screen.queryByText(/share link/i)).not.toBeInTheDocument()
  })
})
