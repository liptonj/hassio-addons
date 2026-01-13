import { Outlet } from 'react-router-dom'
import Header from './Header'
import Footer from './Footer'

interface LayoutProps {
  isAdmin?: boolean
}

export default function Layout({ isAdmin = false }: LayoutProps) {
  return (
    <div className="page-wrapper">
      <Header isAdmin={isAdmin} />
      <main className="container" style={{ flex: 1, paddingTop: '2rem', paddingBottom: '2rem' }}>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
