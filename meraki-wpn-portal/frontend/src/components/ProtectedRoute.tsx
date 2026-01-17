import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { isTokenExpired } from '../utils/token'

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    // Check for admin token in localStorage
    // This can come from traditional admin login or universal login (for admin users)
    const adminToken = localStorage.getItem('admin_token')
    
    if (adminToken && !isTokenExpired(adminToken)) {
      setIsAuthenticated(true)
    } else {
      // Token expired or missing - clear it
      if (adminToken) {
        localStorage.removeItem('admin_token')
      }
      setIsAuthenticated(false)
    }
    
    setIsLoading(false)
  }, [])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="loading-spinner w-10 h-10" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
