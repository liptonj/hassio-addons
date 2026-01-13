import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogIn, AlertCircle } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

export default function Login() {
  const navigate = useNavigate()
  const { login, isLoading } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      await login(username, password)
      navigate('/admin')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid username or password')
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #00c6ff 0%, var(--meraki-blue) 50%, #0056b3 100%)',
        padding: '1.5rem',
      }}
    >
      <div
        style={{
          maxWidth: '440px',
          width: '100%',
          background: 'white',
          borderRadius: '16px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
          padding: '3rem 2.5rem',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div
            style={{
              width: '72px',
              height: '72px',
              background: 'linear-gradient(135deg, var(--meraki-blue), #0056b3)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem',
              boxShadow: '0 8px 20px rgba(0, 164, 228, 0.3)',
            }}
          >
            <LogIn size={36} color="white" />
          </div>
          <h1 style={{ 
            marginBottom: '0.5rem', 
            fontSize: '1.75rem',
            color: 'var(--gray-900)',
            fontWeight: 600,
          }}>
            Admin Portal
          </h1>
          <p style={{ 
            color: 'var(--gray-600)',
            fontSize: '0.95rem',
            marginBottom: 0,
          }}>
            Sign in to manage your network
          </p>
        </div>

        {error && (
          <div
            style={{
              background: '#FEE2E2',
              border: '1px solid #FCA5A5',
              borderRadius: '8px',
              padding: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'start', gap: '0.75rem' }}>
              <AlertCircle size={20} style={{ color: '#DC2626', flexShrink: 0, marginTop: '2px' }} />
              <p style={{ marginBottom: 0, color: '#991B1B', fontSize: '0.9rem' }}>{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label 
              htmlFor="username" 
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: 500,
                color: 'var(--gray-700)',
                marginBottom: '0.5rem',
              }}
            >
              Username
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                fontSize: '1rem',
                border: '2px solid var(--gray-300)',
                borderRadius: '8px',
                outline: 'none',
                transition: 'all 0.2s ease',
                backgroundColor: 'white',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'var(--meraki-blue)'
                e.target.style.boxShadow = '0 0 0 3px rgba(0, 164, 228, 0.1)'
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--gray-300)'
                e.target.style.boxShadow = 'none'
              }}
              placeholder="Enter your username"
              required
              autoFocus
              disabled={isLoading}
            />
          </div>

          <div style={{ marginBottom: '2rem' }}>
            <label 
              htmlFor="password"
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: 500,
                color: 'var(--gray-700)',
                marginBottom: '0.5rem',
              }}
            >
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                fontSize: '1rem',
                border: '2px solid var(--gray-300)',
                borderRadius: '8px',
                outline: 'none',
                transition: 'all 0.2s ease',
                backgroundColor: 'white',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'var(--meraki-blue)'
                e.target.style.boxShadow = '0 0 0 3px rgba(0, 164, 228, 0.1)'
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--gray-300)'
                e.target.style.boxShadow = 'none'
              }}
              placeholder="Enter your password"
              required
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            style={{
              width: '100%',
              padding: '0.875rem 1.5rem',
              fontSize: '1rem',
              fontWeight: 600,
              color: 'white',
              background: isLoading 
                ? 'var(--gray-400)' 
                : 'linear-gradient(135deg, var(--meraki-blue), #0056b3)',
              border: 'none',
              borderRadius: '8px',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 4px 12px rgba(0, 164, 228, 0.3)',
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.currentTarget.style.transform = 'translateY(-1px)'
                e.currentTarget.style.boxShadow = '0 6px 16px rgba(0, 164, 228, 0.4)'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 164, 228, 0.3)'
            }}
            disabled={isLoading}
          >
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                <span className="loading-spinner" style={{ width: '16px', height: '16px' }} />
                Signing in...
              </span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div
          style={{
            marginTop: '2rem',
            paddingTop: '1.5rem',
            borderTop: '1px solid var(--gray-200)',
            textAlign: 'center',
          }}
        >
          <a
            href="/"
            style={{
              color: 'var(--meraki-blue)',
              textDecoration: 'none',
              fontSize: '0.875rem',
              fontWeight: 500,
              transition: 'color 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#0056b3'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--meraki-blue)'
            }}
          >
            ← Back to Public Portal
          </a>
        </div>
      </div>
    </div>
  )
}
