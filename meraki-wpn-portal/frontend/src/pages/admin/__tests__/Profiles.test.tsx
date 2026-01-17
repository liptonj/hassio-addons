import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import Profiles from '../Profiles'

// Mock the radiusClient
vi.mock('../../../api/radiusClient', () => ({
  listPolicies: vi.fn(),
  createPolicy: vi.fn(),
  updatePolicy: vi.fn(),
  deletePolicy: vi.fn(),
}))

import { listPolicies, createPolicy, updatePolicy, deletePolicy } from '../../../api/radiusClient'

const mockProfiles = [
  {
    id: 1,
    name: 'Full Access Profile',
    description: 'Profile for full network access',
    priority: 100,
    policy_type: 'user',
    vlan_id: 100,
    vlan_name: 'Corporate',
    bandwidth_limit_up: 100000,
    bandwidth_limit_down: 500000,
    session_timeout: 3600,
    idle_timeout: 600,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Guest Profile',
    description: 'Limited access for guests',
    priority: 200,
    policy_type: 'user',
    vlan_id: 200,
    vlan_name: 'Guest',
    bandwidth_limit_up: 10000,
    bandwidth_limit_down: 50000,
    session_timeout: 1800,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('Profiles Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listPolicies as ReturnType<typeof vi.fn>).mockResolvedValue({ items: mockProfiles })
  })

  it('renders the profiles page title', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('RADIUS Profiles')).toBeInTheDocument()
    })
  })

  it('displays profiles in the table', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('Full Access Profile')).toBeInTheDocument()
      expect(screen.getByText('Guest Profile')).toBeInTheDocument()
    })
  })

  it('shows VLAN information for profiles', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('100')).toBeInTheDocument()
      expect(screen.getByText('(Corporate)')).toBeInTheDocument()
    })
  })

  it('shows Add Profile button', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('Add Profile')).toBeInTheDocument()
    })
  })

  it('opens add profile modal when clicking Add Profile', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('Add Profile')).toBeInTheDocument()
    })
    
    fireEvent.click(screen.getByText('Add Profile'))
    
    await waitFor(() => {
      expect(screen.getByText('Add New Profile')).toBeInTheDocument()
    })
  })

  it('shows empty state when no profiles exist', async () => {
    ;(listPolicies as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [] })
    
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('No profiles yet')).toBeInTheDocument()
    })
  })

  it('shows loading state', () => {
    ;(listPolicies as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}))
    
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    expect(screen.getByText('Loading profiles...')).toBeInTheDocument()
  })

  it('shows active/inactive status badges', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getAllByText('Active').length).toBeGreaterThan(0)
    })
  })
})

describe('Profiles Form', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listPolicies as ReturnType<typeof vi.fn>).mockResolvedValue({ items: mockProfiles })
    ;(createPolicy as ReturnType<typeof vi.fn>).mockResolvedValue({ ...mockProfiles[0], id: 3 })
  })

  it('creates a new profile', async () => {
    render(<Profiles />, { wrapper: createTestWrapper() })
    
    await waitFor(() => {
      expect(screen.getByText('Add Profile')).toBeInTheDocument()
    })
    
    // Open modal
    fireEvent.click(screen.getByText('Add Profile'))
    
    await waitFor(() => {
      expect(screen.getByText('Add New Profile')).toBeInTheDocument()
    })
    
    // Fill form
    const nameInput = screen.getByLabelText(/Name/i)
    fireEvent.change(nameInput, { target: { value: 'New Test Profile' } })
    
    // Submit
    const submitButton = screen.getByText('Create Profile')
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(createPolicy).toHaveBeenCalled()
    })
  })
})
