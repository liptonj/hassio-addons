import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard,
  Key,
  Ticket,
  Users,
  Settings,
  Shield,
  Lock,
  Server,
  Network,
  LogOut,
  ChevronDown,
  Smartphone,
  Palette,
  Wifi,
  UserPlus,
  Cloud,
  Wrench,
  FileCheck,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

interface AdminSidebarProps {
  isOpen: boolean
  onClose: () => void
}

export default function AdminSidebar({ isOpen, onClose }: AdminSidebarProps) {
  const location = useLocation()
  const { isAuthenticated, logout } = useAuth()
  const [radiusOpen, setRadiusOpen] = useState(true)
  const [portalOpen, setPortalOpen] = useState(true)

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`)

  const handleNavigate = () => {
    if (isOpen) {
      onClose()
    }
  }

  return (
    <>
      {isOpen && (
        <button
          type="button"
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={onClose}
          aria-label="Close menu"
        />
      )}

      <aside
        className={`fixed md:static z-50 md:z-auto top-0 left-0 h-full md:h-auto w-64 bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700 p-4 transition-transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-3">Overview</div>
        <nav className="space-y-1">
          <NavLink
            to="/admin"
            onClick={handleNavigate}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
              isActive('/admin')
                ? 'bg-meraki-blue/10 text-meraki-blue'
                : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <LayoutDashboard size={18} />
            Dashboard
          </NavLink>
        </nav>

        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 mt-6 mb-3">Access</div>
        <nav className="space-y-1">
          <NavLink
            to="/admin/ipsks"
            onClick={handleNavigate}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
              isActive('/admin/ipsks')
                ? 'bg-meraki-blue/10 text-meraki-blue'
                : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <Key size={18} />
            IPSKs
          </NavLink>
          <NavLink
            to="/admin/invite-codes"
            onClick={handleNavigate}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
              isActive('/admin/invite-codes')
                ? 'bg-meraki-blue/10 text-meraki-blue'
                : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <Ticket size={18} />
            Invite Codes
          </NavLink>
        </nav>

        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 mt-6 mb-3">RADIUS</div>
        <div className="space-y-1">
          <button
            type="button"
            onClick={() => setRadiusOpen(prev => !prev)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
              isActive('/admin/users') || isActive('/admin/auth-config') || isActive('/admin/radius') || isActive('/admin/registered-devices') || isActive('/admin/policy-management') || isActive('/admin/profiles') || isActive('/admin/authorization-policies')
                ? 'bg-meraki-blue/10 text-meraki-blue'
                : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <span className="flex items-center gap-2">
              <Server size={18} />
              RADIUS
            </span>
            <ChevronDown
              size={16}
              className={`transition-transform ${radiusOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {radiusOpen && (
            <div className="ml-6 space-y-1">
              <NavLink
                to="/admin/users"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/users')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Users size={16} />
                Users
              </NavLink>
              <NavLink
                to="/admin/registered-devices"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/registered-devices')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Smartphone size={16} />
                Devices
              </NavLink>
              <NavLink
                to="/admin/auth-config"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/auth-config')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Lock size={16} />
                Auth Config
              </NavLink>
              <NavLink
                to="/admin/authorization-policies"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/authorization-policies')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <FileCheck size={16} />
                Auth Policies
              </NavLink>
              <NavLink
                to="/admin/profiles"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/profiles')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Settings size={16} />
                Profiles
              </NavLink>
              <NavLink
                to="/admin/radius"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/radius') && !isActive('/admin/radius/clients') && !isActive('/admin/radius/udn')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Settings size={16} />
                Settings
              </NavLink>
              <NavLink
                to="/admin/radius/clients"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/radius/clients')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Network size={16} />
                Clients
              </NavLink>
              <NavLink
                to="/admin/radius/udn"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/radius/udn')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Shield size={16} />
                UDN
              </NavLink>
            </div>
          )}
        </div>

        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 mt-6 mb-3">Portal</div>
        <div className="space-y-1">
          <button
            type="button"
            onClick={() => setPortalOpen(prev => !prev)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
              isActive('/admin/settings')
                ? 'bg-meraki-blue/10 text-meraki-blue'
                : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <span className="flex items-center gap-2">
              <Settings size={18} />
              Settings
            </span>
            <ChevronDown
              size={16}
              className={`transition-transform ${portalOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {portalOpen && (
            <div className="ml-6 space-y-1">
              <NavLink
                to="/admin/settings/branding"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/branding')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Palette size={16} />
                Branding
              </NavLink>
              <NavLink
                to="/admin/settings/meraki-api"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/meraki-api')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Key size={16} />
                Meraki API
              </NavLink>
              <NavLink
                to="/admin/settings/network/selection"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/network')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Wifi size={16} />
                Network
              </NavLink>
              <NavLink
                to="/admin/settings/registration/basics"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/registration')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <UserPlus size={16} />
                Registration
              </NavLink>
              <NavLink
                to="/admin/settings/oauth"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/oauth')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Shield size={16} />
                OAuth / SSO
              </NavLink>
              <NavLink
                to="/admin/settings/cloudflare"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/cloudflare')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Cloud size={16} />
                Cloudflare Tunnel
              </NavLink>
              <NavLink
                to="/admin/settings/advanced"
                onClick={handleNavigate}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isActive('/admin/settings/advanced')
                    ? 'bg-meraki-blue/10 text-meraki-blue'
                    : 'text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                <Wrench size={16} />
                Advanced
              </NavLink>
            </div>
          )}
        </div>

        {isAuthenticated && (
          <div className="mt-8 pt-4 border-t border-gray-200 dark:border-slate-700">
            <button
              type="button"
              onClick={() => {
                logout()
                onClose()
              }}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700 w-full"
            >
              <LogOut size={18} />
              Logout
            </button>
          </div>
        )}
      </aside>
    </>
  )
}
