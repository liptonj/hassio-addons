import { Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { Wifi, Menu, ChevronDown } from 'lucide-react'
import { useBranding } from '../context/BrandingContext'
import { useAuth } from '../context/AuthContext'

interface HeaderProps {
  isAdmin?: boolean
  onAdminMenuToggle?: () => void
}

export default function Header({ isAdmin = false, onAdminMenuToggle }: HeaderProps) {
  const location = useLocation()
  const { isAuthenticated, logout } = useAuth()
  const { propertyName, logoUrl } = useBranding()
  const [menuOpen, setMenuOpen] = useState(false)

  const isActive = (path: string) => location.pathname === path

  return (
    <header className="header">
      <div className="container header-content">
        <div className="flex items-center justify-between w-full md:w-auto">
          <div className="header-logo">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={propertyName}
                className="h-8 w-auto object-contain"
                onError={(e) => {
                  // Fallback to WiFi icon if logo fails to load
                  e.currentTarget.style.display = 'none'
                  const fallback = e.currentTarget.nextElementSibling
                  if (fallback) {
                    (fallback as HTMLElement).style.display = 'block'
                  }
                }}
              />
            ) : null}
            {/* Fallback icon - hidden if logo loads successfully */}
            <Wifi 
              size={28} 
              className={logoUrl ? 'hidden' : 'block'}
            />
            <Link to={isAdmin ? '/admin' : '/'} className="header-brand">
              {isAdmin ? 'WPN Admin' : propertyName}
            </Link>
          </div>

          {isAdmin && onAdminMenuToggle && (
            <button
              onClick={onAdminMenuToggle}
              className="md:hidden p-2 text-white hover:bg-white/15 rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              <Menu size={24} />
            </button>
          )}
        </div>

        {!isAdmin && (
          <nav className="header-nav flex">
            <Link
              to="/register"
              className={`header-nav-link ${isActive('/register') ? 'active' : ''}`}
            >
              Register
            </Link>
            <Link
              to="/my-network"
              className={`header-nav-link ${isActive('/my-network') ? 'active' : ''}`}
            >
              My Network
            </Link>
          </nav>
        )}
        {isAdmin && (
          <div className="flex items-center gap-3 ml-auto">
            <Link
              to="/admin"
              className={`header-nav-link ${isActive('/admin') ? 'active' : ''}`}
            >
              Dashboard
            </Link>
            {isAuthenticated && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen(prev => !prev)}
                  className="flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-white text-sm font-semibold"
                  aria-label="Open admin menu"
                >
                  <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white text-sm font-bold text-primary">
                    AD
                  </span>
                  <ChevronDown size={16} />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-50 dark:bg-gray-800 dark:border-gray-700">
                    <Link
                      to="/admin/settings#change-password"
                      onClick={() => setMenuOpen(false)}
                      className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-700"
                    >
                      Change Password
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        logout()
                        setMenuOpen(false)
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-700"
                    >
                      Logout
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
