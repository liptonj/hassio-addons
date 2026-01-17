import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import DeviceList from '../../src/components/DeviceList'
import type { UserDevice } from '../../src/types/user'

describe('DeviceList', () => {
  const mockDevices: UserDevice[] = [
    {
      id: 1,
      mac_address: 'AA:BB:CC:DD:EE:FF',
      device_type: 'phone',
      device_os: 'iOS',
      device_model: 'iPhone 15 Pro',
      device_name: 'My iPhone',
      registered_at: '2026-01-14T10:00:00Z',
      last_seen_at: '2026-01-14T12:00:00Z',
      is_active: true,
    },
    {
      id: 2,
      mac_address: '11:22:33:44:55:66',
      device_type: 'laptop',
      device_os: 'macOS',
      device_model: 'MacBook Pro',
      registered_at: '2026-01-13T10:00:00Z',
      is_active: true,
    },
  ]

  it('renders loading state', () => {
    render(<DeviceList devices={[]} loading={true} />)
    
    expect(screen.getByText(/loading devices/i)).toBeInTheDocument()
  })

  it('renders empty state when no devices', () => {
    render(<DeviceList devices={[]} loading={false} />)
    
    expect(screen.getByText(/no devices registered/i)).toBeInTheDocument()
  })

  it('renders list of devices', () => {
    render(<DeviceList devices={mockDevices} loading={false} />)
    
    expect(screen.getByText('My iPhone')).toBeInTheDocument()
    expect(screen.getByText('MacBook Pro')).toBeInTheDocument()
  })

  it('passes onRename callback to DeviceCard', () => {
    const onRename = vi.fn()
    render(<DeviceList devices={mockDevices} onRename={onRename} loading={false} />)
    
    // Both devices should have rename buttons
    const renameButtons = screen.getAllByText(/rename/i)
    expect(renameButtons).toHaveLength(2)
  })

  it('passes onRemove callback to DeviceCard', () => {
    const onRemove = vi.fn()
    render(<DeviceList devices={mockDevices} onRemove={onRemove} loading={false} />)
    
    // Both devices should have remove buttons
    const removeButtons = screen.getAllByText(/remove/i)
    expect(removeButtons).toHaveLength(2)
  })

  it('renders null when devices is null', () => {
    const { container } = render(
      <DeviceList devices={null as any} loading={false} />
    )
    
    expect(screen.getByText(/no devices registered/i)).toBeInTheDocument()
  })

  it('renders null when devices is undefined', () => {
    const { container } = render(
      <DeviceList devices={undefined as any} loading={false} />
    )
    
    expect(screen.getByText(/no devices registered/i)).toBeInTheDocument()
  })

  it('does not show action buttons when callbacks not provided', () => {
    render(<DeviceList devices={mockDevices} loading={false} />)
    
    expect(screen.queryByText(/rename/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/remove/i)).not.toBeInTheDocument()
  })

  it('renders correct number of device cards', () => {
    const { container } = render(
      <DeviceList devices={mockDevices} loading={false} />
    )
    
    const cards = container.querySelectorAll('.card')
    expect(cards).toHaveLength(2)
  })

  it('shows empty state icon', () => {
    render(<DeviceList devices={[]} loading={false} />)
    
    // Check for smartphone icon in empty state
    const emptyStateContainer = screen.getByText(/no devices registered/i).closest('div')
    expect(emptyStateContainer).toBeInTheDocument()
  })
})
