import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DeviceCard from '../../src/components/DeviceCard'
import type { UserDevice } from '../../src/types/user'

describe('DeviceCard', () => {
  const mockDevice: UserDevice = {
    id: 1,
    mac_address: 'AA:BB:CC:DD:EE:FF',
    device_type: 'phone',
    device_os: 'iOS',
    device_model: 'iPhone 15 Pro',
    device_name: 'My iPhone',
    registered_at: '2026-01-14T10:00:00Z',
    last_seen_at: '2026-01-14T12:00:00Z',
    is_active: true,
  }

  it('renders device information', () => {
    render(<DeviceCard device={mockDevice} />)
    
    expect(screen.getByText('My iPhone')).toBeInTheDocument()
    expect(screen.getByText(/iOS phone/i)).toBeInTheDocument()
    expect(screen.getByText(/AA:BB:CC:DD:EE:FF/)).toBeInTheDocument()
  })

  it('shows active badge for recently seen devices', () => {
    const recentDevice = {
      ...mockDevice,
      last_seen_at: new Date().toISOString(),
    }
    
    render(<DeviceCard device={recentDevice} />)
    
    expect(screen.getByText(/active/i)).toBeInTheDocument()
  })

  it('uses device model when no custom name', () => {
    const deviceNoName = {
      ...mockDevice,
      device_name: undefined,
    }
    
    render(<DeviceCard device={deviceNoName} />)
    
    expect(screen.getByText('iPhone 15 Pro')).toBeInTheDocument()
  })

  it('generates friendly name from OS and type when model unknown', () => {
    const deviceGeneric = {
      ...mockDevice,
      device_name: undefined,
      device_model: 'Unknown',
    }
    
    render(<DeviceCard device={deviceGeneric} />)
    
    expect(screen.getByText(/iOS phone/i)).toBeInTheDocument()
  })

  it('shows rename button when onRename provided', () => {
    const onRename = vi.fn()
    render(<DeviceCard device={mockDevice} onRename={onRename} />)
    
    expect(screen.getByText(/rename/i)).toBeInTheDocument()
  })

  it('shows remove button when onRemove provided', () => {
    const onRemove = vi.fn()
    render(<DeviceCard device={mockDevice} onRemove={onRemove} />)
    
    expect(screen.getByText(/remove/i)).toBeInTheDocument()
  })

  it('calls onRename with new name when rename clicked', () => {
    const onRename = vi.fn()
    const promptMock = vi.spyOn(window, 'prompt').mockReturnValue('New Name')
    
    render(<DeviceCard device={mockDevice} onRename={onRename} />)
    
    fireEvent.click(screen.getByText(/rename/i))
    
    expect(promptMock).toHaveBeenCalledWith(
      'Enter a new name for this device:',
      'My iPhone'
    )
    expect(onRename).toHaveBeenCalledWith(1, 'New Name')
    
    promptMock.mockRestore()
  })

  it('does not call onRename when prompt cancelled', () => {
    const onRename = vi.fn()
    const promptMock = vi.spyOn(window, 'prompt').mockReturnValue(null)
    
    render(<DeviceCard device={mockDevice} onRename={onRename} />)
    
    fireEvent.click(screen.getByText(/rename/i))
    
    expect(onRename).not.toHaveBeenCalled()
    
    promptMock.mockRestore()
  })

  it('calls onRemove with confirmation when remove clicked', () => {
    const onRemove = vi.fn()
    const confirmMock = vi.spyOn(window, 'confirm').mockReturnValue(true)
    
    render(<DeviceCard device={mockDevice} onRemove={onRemove} />)
    
    fireEvent.click(screen.getByText(/remove/i))
    
    expect(confirmMock).toHaveBeenCalled()
    expect(onRemove).toHaveBeenCalledWith(1)
    
    confirmMock.mockRestore()
  })

  it('does not call onRemove when confirmation cancelled', () => {
    const onRemove = vi.fn()
    const confirmMock = vi.spyOn(window, 'confirm').mockReturnValue(false)
    
    render(<DeviceCard device={mockDevice} onRemove={onRemove} />)
    
    fireEvent.click(screen.getByText(/remove/i))
    
    expect(onRemove).not.toHaveBeenCalled()
    
    confirmMock.mockRestore()
  })

  it('displays last seen time', () => {
    render(<DeviceCard device={mockDevice} />)
    
    expect(screen.getByText(/last seen/i)).toBeInTheDocument()
  })

  it('displays registered time when last_seen not available', () => {
    const deviceNoLastSeen = {
      ...mockDevice,
      last_seen_at: undefined,
    }
    
    render(<DeviceCard device={deviceNoLastSeen} />)
    
    expect(screen.getByText(/registered/i)).toBeInTheDocument()
  })

  it('styles inactive devices differently', () => {
    const inactiveDevice = {
      ...mockDevice,
      is_active: false,
    }
    
    const { container } = render(<DeviceCard device={inactiveDevice} />)
    
    const iconContainer = container.querySelector('.bg-gray-100')
    expect(iconContainer).toBeInTheDocument()
  })

  it('hides action buttons when neither callback provided', () => {
    render(<DeviceCard device={mockDevice} />)
    
    expect(screen.queryByText(/rename/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/remove/i)).not.toBeInTheDocument()
  })
})
