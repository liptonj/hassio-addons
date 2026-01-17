import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CustomFieldRenderer from '../../src/components/CustomFieldRenderer'
import type { CustomField } from '../../src/types/user'

describe('CustomFieldRenderer', () => {
  const mockOnChange = vi.fn()

  const textField: CustomField = {
    id: 'unit_number',
    label: 'Unit Number',
    type: 'text',
    required: true,
  }

  const selectField: CustomField = {
    id: 'parking',
    label: 'Parking Spot',
    type: 'select',
    required: false,
    options: ['A1', 'A2', 'B1', 'B2'],
  }

  const numberField: CustomField = {
    id: 'floor',
    label: 'Floor',
    type: 'number',
    required: true,
  }

  afterEach(() => {
    mockOnChange.mockClear()
  })

  it('renders nothing when fields array is empty', () => {
    const { container } = render(
      <CustomFieldRenderer
        fields={[]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders text field correctly', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    expect(screen.getByLabelText(/unit number/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/enter unit number/i)).toBeInTheDocument()
  })

  it('renders select field with options', () => {
    render(
      <CustomFieldRenderer
        fields={[selectField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    expect(screen.getByLabelText(/parking spot/i)).toBeInTheDocument()
    
    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()
    
    // Check options
    expect(screen.getByText('A1')).toBeInTheDocument()
    expect(screen.getByText('A2')).toBeInTheDocument()
    expect(screen.getByText('B1')).toBeInTheDocument()
    expect(screen.getByText('B2')).toBeInTheDocument()
  })

  it('renders number field correctly', () => {
    render(
      <CustomFieldRenderer
        fields={[numberField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    const input = screen.getByLabelText(/floor/i) as HTMLInputElement
    expect(input.type).toBe('number')
  })

  it('shows required indicator for required fields', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('handles text input change', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    const input = screen.getByPlaceholderText(/enter unit number/i)
    fireEvent.change(input, { target: { value: '101' } })
    
    expect(mockOnChange).toHaveBeenCalledWith('unit_number', '101')
  })

  it('handles select change', () => {
    render(
      <CustomFieldRenderer
        fields={[selectField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'A1' } })
    
    expect(mockOnChange).toHaveBeenCalledWith('parking', 'A1')
  })

  it('displays field values', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{ unit_number: '202' }}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    const input = screen.getByPlaceholderText(/enter unit number/i) as HTMLInputElement
    expect(input.value).toBe('202')
  })

  it('displays error messages', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{}}
        onChange={mockOnChange}
        errors={{ unit_number: 'This field is required' }}
      />
    )
    
    expect(screen.getByText('This field is required')).toBeInTheDocument()
  })

  it('renders multiple fields', () => {
    render(
      <CustomFieldRenderer
        fields={[textField, selectField, numberField]}
        values={{}}
        onChange={mockOnChange}
        errors={{}}
      />
    )
    
    expect(screen.getByLabelText(/unit number/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/parking spot/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/floor/i)).toBeInTheDocument()
  })

  it('applies error styling to fields with errors', () => {
    render(
      <CustomFieldRenderer
        fields={[textField]}
        values={{}}
        onChange={mockOnChange}
        errors={{ unit_number: 'Error' }}
      />
    )
    
    const input = screen.getByPlaceholderText(/enter unit number/i)
    expect(input).toHaveClass('error')
  })
})
