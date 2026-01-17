import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Users from '../Users'

// Mock the API client
vi.mock('../../../api/client', () => ({
  getUsers: vi.fn(() => Promise.resolve({
    success: true,
    total: 2,
    users: [
      { id: 1, email: 'approved@test.com', name: 'Approved User', is_admin: false, is_active: true, has_ipsk: true },
      { id: 2, email: 'admin@test.com', name: 'Admin User', is_admin: true, is_active: true, has_ipsk: false },
    ],
  })),
  createUser: vi.fn(),
  toggleUserAdmin: vi.fn(),
  deleteUser: vi.fn(),
  getPendingUsers: vi.fn(() => Promise.resolve({
    total: 2,
    users: [
      { id: 10, email: 'pending1@test.com', name: 'Pending User 1', approval_status: 'pending', created_at: '2026-01-15T10:00:00Z' },
      { id: 11, email: 'pending2@test.com', name: 'Pending User 2', approval_status: 'pending', unit: '101', created_at: '2026-01-14T10:00:00Z' },
    ],
  })),
  approveUser: vi.fn(() => Promise.resolve({
    success: true,
    message: 'User approved',
    user: { id: 10, email: 'pending1@test.com', approval_status: 'approved' },
    credentials: { passphrase: 'TestPass123', ssid_name: 'Test-WiFi', ipsk_name: 'User-Pending1' },
  })),
  rejectUser: vi.fn(() => Promise.resolve({
    success: true,
    message: 'User rejected',
    user: { id: 11, email: 'pending2@test.com', approval_status: 'rejected' },
  })),
}))

// Import mocked functions
import { getPendingUsers, approveUser, rejectUser } from '../../../api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
})

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('User Approval Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient.clear()
  })

  describe('Pending Tab', () => {
    it('shows pending approval tab with count badge', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument() // Badge count
      })
    })

    it('shows pending users when tab is clicked', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 1')).toBeInTheDocument()
        expect(screen.getByText('Pending User 2')).toBeInTheDocument()
      })
    })

    it('shows approve and reject buttons for pending users', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        const approveButtons = screen.getAllByRole('button', { name: /approve/i })
        const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
        
        expect(approveButtons.length).toBe(2)
        expect(rejectButtons.length).toBe(2)
      })
    })
  })

  describe('Approve User', () => {
    it('calls approveUser API when approve button is clicked', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 1')).toBeInTheDocument()
      })
      
      const approveButtons = screen.getAllByRole('button', { name: /approve/i })
      fireEvent.click(approveButtons[0])
      
      await waitFor(() => {
        expect(approveUser).toHaveBeenCalledWith(10)
      })
    })
  })

  describe('Reject User', () => {
    it('shows rejection modal when reject button is clicked', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 2')).toBeInTheDocument()
      })
      
      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      fireEvent.click(rejectButtons[1])
      
      await waitFor(() => {
        expect(screen.getByText('Reject User')).toBeInTheDocument()
        expect(screen.getByPlaceholderText(/reason for rejection/i)).toBeInTheDocument()
      })
    })

    it('calls rejectUser API with notes when confirmed', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 2')).toBeInTheDocument()
      })
      
      // Open rejection modal
      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      fireEvent.click(rejectButtons[1])
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/reason for rejection/i)).toBeInTheDocument()
      })
      
      // Enter rejection notes
      const notesInput = screen.getByPlaceholderText(/reason for rejection/i)
      fireEvent.change(notesInput, { target: { value: 'Invalid registration' } })
      
      // Confirm rejection
      const confirmButton = screen.getByRole('button', { name: /reject user/i })
      fireEvent.click(confirmButton)
      
      await waitFor(() => {
        expect(rejectUser).toHaveBeenCalledWith(11, 'Invalid registration')
      })
    })

    it('closes modal when cancel is clicked', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 1')).toBeInTheDocument()
      })
      
      // Open rejection modal
      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      fireEvent.click(rejectButtons[0])
      
      await waitFor(() => {
        expect(screen.getByText('Reject User')).toBeInTheDocument()
      })
      
      // Cancel
      fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
      
      await waitFor(() => {
        expect(screen.queryByText('Reject User')).not.toBeInTheDocument()
      })
    })
  })

  describe('Tab Filtering', () => {
    it('shows all users on All Users tab', async () => {
      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Approved User')).toBeInTheDocument()
        expect(screen.getByText('Admin User')).toBeInTheDocument()
      })
    })

    it('switches between tabs correctly', async () => {
      renderWithProviders(<Users />)
      
      // Start on All Users tab
      await waitFor(() => {
        expect(screen.getByText('Approved User')).toBeInTheDocument()
      })
      
      // Switch to Pending
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText('Pending User 1')).toBeInTheDocument()
        expect(screen.queryByText('Approved User')).not.toBeInTheDocument()
      })
      
      // Switch back to All Users
      fireEvent.click(screen.getByText('All Users'))
      
      await waitFor(() => {
        expect(screen.getByText('Approved User')).toBeInTheDocument()
        expect(screen.queryByText('Pending User 1')).not.toBeInTheDocument()
      })
    })
  })

  describe('Empty States', () => {
    it('shows empty message when no pending users', async () => {
      ;(getPendingUsers as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        total: 0,
        users: [],
      })

      renderWithProviders(<Users />)
      
      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
      
      fireEvent.click(screen.getByText('Pending Approval'))
      
      await waitFor(() => {
        expect(screen.getByText(/no users pending approval/i)).toBeInTheDocument()
      })
    })
  })
})
