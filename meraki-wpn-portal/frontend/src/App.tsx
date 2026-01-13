import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import SplashLanding from './pages/public/SplashLanding'
import UserAuth from './pages/public/UserAuth'
import Registration from './pages/public/Registration'
import Success from './pages/public/Success'
import MyNetwork from './pages/public/MyNetwork'
import Login from './pages/admin/Login'
import Dashboard from './pages/admin/Dashboard'
import IPSKManager from './pages/admin/IPSKManager'
import InviteCodes from './pages/admin/InviteCodes'
import Users from './pages/admin/Users'
import Settings from './pages/admin/Settings'

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/register" replace />} />
          <Route path="splash-landing" element={<SplashLanding />} />
          <Route path="user-auth" element={<UserAuth />} />
          <Route path="register" element={<Registration />} />
          <Route path="success" element={<Success />} />
          <Route path="my-network" element={<MyNetwork />} />
        </Route>

        {/* Admin Login */}
        <Route path="/admin/login" element={<Login />} />

        {/* Protected Admin Routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <Layout isAdmin />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="ipsks" element={<IPSKManager />} />
          <Route path="invite-codes" element={<InviteCodes />} />
          <Route path="users" element={<Users />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/register" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
