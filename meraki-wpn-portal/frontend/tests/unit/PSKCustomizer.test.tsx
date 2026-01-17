import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PSKCustomizer from '../../src/components/PSKCustomizer'

describe('PSKCustomizer', () => {
  const mockOnChange = vi.fn()

  afterEach(() => {
    mockOnChange.mockClear()
  })

  it('renders nothing when disabled', () => {
    const { container } = render(
      <PSKCustomizer
        enabled={false}
        minLength={8}
        maxLength={63}
        value=""
        onChange={mockOnChange}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows auto-generate mode by default', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value=""
        onChange={mockOnChange}
      />
    )
    expect(screen.getByText(/auto-generate/i)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/enter your password/i)).not.toBeInTheDocument()
  })

  it('switches to custom mode when toggle clicked', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value=""
        onChange={mockOnChange}
      />
    )
    
    const customButton = screen.getByText(/choose my own/i)
    fireEvent.click(customButton)
    
    expect(screen.getByPlaceholderText(/enter your password/i)).toBeInTheDocument()
  })

  it('displays password strength indicator for valid input', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value="TestPass123"
        onChange={mockOnChange}
      />
    )
    
    // Click custom mode
    fireEvent.click(screen.getByText(/choose my own/i))
    
    expect(screen.getByText(/medium strength/i)).toBeInTheDocument()
  })

  it('shows validation errors for short password', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value="short"
        onChange={mockOnChange}
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
  })

  it('generates random password when button clicked', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value=""
        onChange={mockOnChange}
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    const generateButton = screen.getByTitle(/generate random password/i)
    fireEvent.click(generateButton)
    
    expect(mockOnChange).toHaveBeenCalledWith(expect.stringMatching(/^.{16}$/))
  })

  it('toggles password visibility', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value="TestPassword"
        onChange={mockOnChange}
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    const input = screen.getByPlaceholderText(/enter your password/i) as HTMLInputElement
    
    expect(input.type).toBe('password')
    
    const toggleButton = screen.getByTitle(/show password/i)
    fireEvent.click(toggleButton)
    
    expect(input.type).toBe('text')
  })

  it('displays custom error message', () => {
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value=""
        onChange={mockOnChange}
        error="Custom error message"
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    expect(screen.getByText('Custom error message')).toBeInTheDocument()
  })

  it('shows character count', () => {
    const value = "TestPassword"
    render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value={value}
        onChange={mockOnChange}
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    expect(screen.getByText(`${value.length}/63 characters`)).toBeInTheDocument()
  })

  it('clears value when switching from custom to auto', () => {
    const { rerender } = render(
      <PSKCustomizer
        enabled={true}
        minLength={8}
        maxLength={63}
        value="TestPassword"
        onChange={mockOnChange}
      />
    )
    
    fireEvent.click(screen.getByText(/choose my own/i))
    fireEvent.click(screen.getByText(/auto-generate/i))
    
    expect(mockOnChange).toHaveBeenCalledWith('')
  })
})
