import { createContext, useContext, useState, useEffect, ReactNode, useRef } from 'react'
import axios from 'axios'
import { isTokenExpired, getTokenExpirationTime } from '../utils/token'

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  token: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const tokenCheckIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Function to check and validate token
  const validateToken = (tokenToCheck: string | null): boolean => {
    if (!tokenToCheck) {
      return false
    }
    
    if (isTokenExpired(tokenToCheck)) {
      // Token expired - clear it
      localStorage.removeItem('admin_token')
      localStorage.removeItem('user_token')
      setToken(null)
      return false
    }
    
    return true
  }

  // Function to setup token expiration checking
  const setupTokenExpirationCheck = (currentToken: string | null) => {
    // Clear existing interval
    if (tokenCheckIntervalRef.current) {
      clearInterval(tokenCheckIntervalRef.current)
      tokenCheckIntervalRef.current = null
    }

    if (!currentToken) {
      return
    }

    // Check token expiration every minute
    tokenCheckIntervalRef.current = setInterval(() => {
      const storedToken = localStorage.getItem('admin_token')
      if (!validateToken(storedToken)) {
        // Token expired - redirect to login if on admin page
        if (window.location.pathname.startsWith('/admin') && !window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
      }
    }, 60000) // Check every minute

    // Also check expiration time and set a one-time check before expiration
    const expirationTime = getTokenExpirationTime(currentToken)
    if (expirationTime && expirationTime > 0) {
      // Set a timeout to check right before expiration (with 1 minute buffer)
      setTimeout(() => {
        const storedToken = localStorage.getItem('admin_token')
        if (!validateToken(storedToken)) {
          if (window.location.pathname.startsWith('/admin') && !window.location.pathname.includes('/login')) {
            window.location.href = '/login'
          }
        }
      }, Math.max(0, expirationTime - 60000)) // Check 1 minute before expiration
    }
  }

  useEffect(() => {
    // Check for existing admin token on mount
    // Admin token can come from:
    // 1. Traditional admin login (stored as admin_token)
    // 2. Universal login for admin users (copied to admin_token)
    const savedToken = localStorage.getItem('admin_token')
    
    if (savedToken && validateToken(savedToken)) {
      setToken(savedToken)
      setupTokenExpirationCheck(savedToken)
    } else {
      setToken(null)
    }
    
    setIsLoading(false)
    
    // Listen for storage changes (e.g., when user logs in via UniversalLogin)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'admin_token') {
        if (e.newValue && validateToken(e.newValue)) {
          setToken(e.newValue)
          setupTokenExpirationCheck(e.newValue)
        } else {
          setToken(null)
        }
      }
    }
    window.addEventListener('storage', handleStorageChange)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      if (tokenCheckIntervalRef.current) {
        clearInterval(tokenCheckIntervalRef.current)
      }
    }
  }, [])

  const login = async (username: string, password: string) => {
    setIsLoading(true)
    try {
      const response = await axios.post('/api/auth/login', { username, password })
      const accessToken = response.data.access_token
      setToken(accessToken)
      localStorage.setItem('admin_token', accessToken)
      setupTokenExpirationCheck(accessToken)
    } catch (error) {
      setIsLoading(false)
      throw error
    }
    setIsLoading(false)
  }

  const logout = () => {
    // Clear interval
    if (tokenCheckIntervalRef.current) {
      clearInterval(tokenCheckIntervalRef.current)
      tokenCheckIntervalRef.current = null
    }
    
    // Clear tokens
    setToken(null)
    localStorage.removeItem('admin_token')
    localStorage.removeItem('user_token')
    
    // Redirect to login page
    window.location.href = '/login'
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        isLoading,
        token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
