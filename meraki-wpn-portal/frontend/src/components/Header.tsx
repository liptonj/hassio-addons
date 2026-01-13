import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Wifi, LayoutDashboard, Key, Ticket, Users, Settings, LogOut } from 'lucide-react'
import { getPortalOptions } from '../api/client'
import { useAuth } from '../context/AuthContext'

interface HeaderProps {
  isAdmin?: boolean
}

export default function Header({ isAdmin = false }: HeaderProps) {
  const location = useLocation()
  const { isAuthenticated, logout } = useAuth()
  
  const { data: options } = useQuery({
    queryKey: ['portal-options'],
    queryFn: getPortalOptions,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })

  const propertyName = options?.property_name || 'WiFi Portal'

  const isActive = (path: string) => location.pathname === path

  return (
    <header className="header">
      <div className="container header-content">
        <div className="header-logo">
          <Wifi size={28} />
          <Link to={isAdmin ? '/admin' : '/'} className="header-brand">
            {isAdmin ? 'WPN Admin' : propertyName}
          </Link>
        </div>

        <nav className="header-nav">
          {isAdmin ? (
            <>
              <Link
                to="/admin"
                className={`header-nav-link ${isActive('/admin') ? 'active' : ''}`}
              >
                <LayoutDashboard size={18} style={{ marginRight: '0.25rem' }} />
                Dashboard
              </Link>
              <Link
                to="/admin/ipsks"
                className={`header-nav-link ${isActive('/admin/ipsks') ? 'active' : ''}`}
              >
                <Key size={18} style={{ marginRight: '0.25rem' }} />
                IPSKs
              </Link>
              <Link
                to="/admin/invite-codes"
                className={`header-nav-link ${isActive('/admin/invite-codes') ? 'active' : ''}`}
              >
                <Ticket size={18} style={{ marginRight: '0.25rem' }} />
                Invite Codes
              </Link>
              <Link
                to="/admin/users"
                className={`header-nav-link ${isActive('/admin/users') ? 'active' : ''}`}
              >
                <Users size={18} style={{ marginRight: '0.25rem' }} />
                Users
              </Link>
              <Link
                to="/admin/settings"
                className={`header-nav-link ${isActive('/admin/settings') ? 'active' : ''}`}
              >
                <Settings size={18} style={{ marginRight: '0.25rem' }} />
                Settings
              </Link>
              {isAuthenticated && (
                <button
                  onClick={logout}
                  className="header-nav-link"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  <LogOut size={18} style={{ marginRight: '0.25rem' }} />
                  Logout
                </button>
              )}
            </>
          ) : (
            <>
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
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
