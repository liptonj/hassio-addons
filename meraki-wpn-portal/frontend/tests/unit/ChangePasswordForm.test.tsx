import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ChangePasswordForm from '../../src/components/ChangePasswordForm'
import * as apiClient from '../../src/api/client'

vi.mock('../../src/api/client', () => ({
  changeUserPassword: vi.fn(),
}))

describe('ChangePasswordForm', () => {
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

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <ChangePasswordForm />
      </QueryClientProvider>
    )
  }

  it('renders all form fields', () => {
    renderComponent()
    
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/new password/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument()
  })

  it('shows validation error when current password is empty', async () => {
    renderComponent()
    
    const submitButton = screen.getByText(/change password/i)
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(screen.getByText(/current password is required/i)).toBeInTheDocument()
    })
  })

  it('shows validation error when new password is too short', async () => {
    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'currentpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'short' },
    })
    
    const submitButton = screen.getByText(/change password/i)
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
    })
  })

  it('shows validation error when passwords do not match', async () => {
    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'currentpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'newpassword' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'differentpass' },
    })
    
    const submitButton = screen.getByText(/change password/i)
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    })
  })

  it('submits form with valid data', async () => {
    vi.mocked(apiClient.changeUserPassword).mockResolvedValue({
      success: true,
      message: 'Password changed',
    })

    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'currentpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'newpassword' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'newpassword' },
    })
    
    const submitButton = screen.getByText(/change password/i)
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(apiClient.changeUserPassword).toHaveBeenCalledWith(
        'currentpass',
        'newpassword'
      )
    })
  })

  it('shows success message after successful change', async () => {
    vi.mocked(apiClient.changeUserPassword).mockResolvedValue({
      success: true,
      message: 'Password changed',
    })

    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'currentpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'newpassword' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'newpassword' },
    })
    
    fireEvent.click(screen.getByText(/change password/i))
    
    await waitFor(() => {
      expect(screen.getByText(/password changed successfully/i)).toBeInTheDocument()
    })
  })

  it('shows error message when API call fails', async () => {
    vi.mocked(apiClient.changeUserPassword).mockRejectedValue(
      new Error('Incorrect current password')
    )

    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'wrongpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'newpassword' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'newpassword' },
    })
    
    fireEvent.click(screen.getByText(/change password/i))
    
    await waitFor(() => {
      expect(screen.getByText(/incorrect current password/i)).toBeInTheDocument()
    })
  })

  it('toggles password visibility', () => {
    renderComponent()
    
    const currentPasswordInput = screen.getByLabelText(/current password/i) as HTMLInputElement
    expect(currentPasswordInput.type).toBe('password')
    
    const toggleButtons = screen.getAllByRole('button', { name: '' })
    const showCurrentButton = toggleButtons[0]
    
    fireEvent.click(showCurrentButton)
    expect(currentPasswordInput.type).toBe('text')
    
    fireEvent.click(showCurrentButton)
    expect(currentPasswordInput.type).toBe('password')
  })

  it('clears form after successful submission', async () => {
    vi.mocked(apiClient.changeUserPassword).mockResolvedValue({
      success: true,
      message: 'Password changed',
    })

    renderComponent()
    
    const currentInput = screen.getByLabelText(/current password/i) as HTMLInputElement
    const newInput = screen.getByLabelText(/new password/i) as HTMLInputElement
    const confirmInput = screen.getByLabelText(/confirm new password/i) as HTMLInputElement
    
    fireEvent.change(currentInput, { target: { value: 'currentpass' } })
    fireEvent.change(newInput, { target: { value: 'newpassword' } })
    fireEvent.change(confirmInput, { target: { value: 'newpassword' } })
    
    fireEvent.click(screen.getByText(/change password/i))
    
    await waitFor(() => {
      expect(currentInput.value).toBe('')
      expect(newInput.value).toBe('')
      expect(confirmInput.value).toBe('')
    })
  })

  it('disables submit button while loading', async () => {
    vi.mocked(apiClient.changeUserPassword).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    )

    renderComponent()
    
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: 'currentpass' },
    })
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'newpassword' },
    })
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: 'newpassword' },
    })
    
    const submitButton = screen.getByText(/change password/i)
    fireEvent.click(submitButton)
    
    expect(submitButton).toBeDisabled()
  })
})
