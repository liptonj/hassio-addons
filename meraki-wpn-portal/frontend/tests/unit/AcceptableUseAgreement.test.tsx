import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AcceptableUseAgreement from '../../src/components/AcceptableUseAgreement'

describe('AcceptableUseAgreement', () => {
  const mockOnAcceptChange = vi.fn()

  afterEach(() => {
    mockOnAcceptChange.mockClear()
  })

  it('renders nothing when disabled', () => {
    const { container } = render(
      <AcceptableUseAgreement
        enabled={false}
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders with text when provided', () => {
    render(
      <AcceptableUseAgreement
        enabled={true}
        text="Test AUP text"
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
      />
    )
    expect(screen.getByText(/Test AUP text/)).toBeInTheDocument()
  })

  it('shows external link when URL is provided', () => {
    render(
      <AcceptableUseAgreement
        enabled={true}
        url="https://example.com/aup"
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
      />
    )
    const link = screen.getByText(/View Acceptable Use Policy/)
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', 'https://example.com/aup')
  })

  it('handles checkbox change', () => {
    render(
      <AcceptableUseAgreement
        enabled={true}
        text="Test AUP"
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
      />
    )
    const checkbox = screen.getByRole('checkbox')
    fireEvent.click(checkbox)
    expect(mockOnAcceptChange).toHaveBeenCalledWith(true)
  })

  it('displays error message', () => {
    render(
      <AcceptableUseAgreement
        enabled={true}
        text="Test AUP"
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
        error="You must accept the policy"
      />
    )
    expect(screen.getByText('You must accept the policy')).toBeInTheDocument()
  })

  it('shows modal for long text', () => {
    const longText = 'A'.repeat(300)
    render(
      <AcceptableUseAgreement
        enabled={true}
        text={longText}
        accepted={false}
        onAcceptChange={mockOnAcceptChange}
      />
    )
    const readFullButton = screen.getByText(/Read full policy/)
    fireEvent.click(readFullButton)
    expect(screen.getByText('Acceptable Use Policy')).toBeInTheDocument()
  })
})
