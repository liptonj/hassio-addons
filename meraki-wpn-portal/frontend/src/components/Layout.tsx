import { Outlet } from 'react-router-dom'
import { useState } from 'react'
import Header from './Header'
import Footer from './Footer'
import AdminSidebar from './AdminSidebar'

interface LayoutProps {
  isAdmin?: boolean
}

export default function Layout({ isAdmin = false }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  if (isAdmin) {
    return (
      <div className="page-wrapper">
        <Header isAdmin onAdminMenuToggle={() => setSidebarOpen(prev => !prev)} />
        <div className="flex flex-1">
          <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <main className="flex-1 py-8 px-6 md:px-10 bg-gray-50 dark:bg-gray-900 min-h-screen">
            <Outlet />
          </main>
        </div>
        <Footer />
      </div>
    )
  }

  return (
    <div className="page-wrapper">
      <Header />
      <main className="container flex-1 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
