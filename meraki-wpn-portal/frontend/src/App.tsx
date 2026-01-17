import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { BrandingProvider } from './context/BrandingContext'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import SplashLanding from './pages/public/SplashLanding'
import UserAuth from './pages/public/UserAuth'
import UniversalLogin from './pages/public/UniversalLogin'
import Registration from './pages/public/Registration'
import InviteCode from './pages/public/InviteCode'
import Success from './pages/public/Success'
import MyNetwork from './pages/public/MyNetwork'
import UserAccount from './pages/public/UserAccount'
import UserCertificates from './pages/public/UserCertificates'
// Admin Login redirects to universal login
// import Login from './pages/admin/Login'
import Dashboard from './pages/admin/Dashboard'
import IPSKManager from './pages/admin/IPSKManager'
import InviteCodes from './pages/admin/InviteCodes'
import Users from './pages/admin/Users'
import Branding from './pages/admin/settings/Branding'
import MerakiAPI from './pages/admin/settings/MerakiAPI'
import NetworkSelection from './pages/admin/settings/NetworkSelection'
import SSIDConfiguration from './pages/admin/settings/SSIDConfiguration'
import WPNSetupPage from './pages/admin/settings/WPNSetupPage'
import RegistrationBasics from './pages/admin/settings/RegistrationBasics'
import LoginMethods from './pages/admin/settings/LoginMethods'
import AUPSettings from './pages/admin/settings/AUPSettings'
import CustomFields from './pages/admin/settings/CustomFields'
import IPSKInviteSettings from './pages/admin/settings/IPSKInviteSettings'
import IPSKSettings from './pages/admin/settings/IPSKSettings'
import OAuthSettings from './pages/admin/settings/OAuthSettings'
import CloudflareSettings from './pages/admin/settings/CloudflareSettings'
import AdvancedSettings from './pages/admin/settings/AdvancedSettings'
import RADIUSSettings from './pages/admin/RADIUSSettings'
import RADIUSClients from './pages/admin/RADIUSClients'
import UDNManagement from './pages/admin/UDNManagement'
import AuthenticationConfig from './pages/admin/AuthenticationConfig'
import RegisteredDevices from './pages/admin/RegisteredDevices'
import PolicyManagement from './pages/admin/PolicyManagement'
import Profiles from './pages/admin/Profiles'
import AuthorizationPolicies from './pages/admin/AuthorizationPolicies'

function App() {
  return (
    <BrandingProvider>
      <AuthProvider>
        <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/register" replace />} />
          <Route path="splash-landing" element={<SplashLanding />} />
          <Route path="login" element={<UniversalLogin />} />
          <Route path="user-auth" element={<UserAuth />} />
          <Route path="user-account" element={<UserAccount />} />
          <Route path="user-certificates" element={<UserCertificates />} />
          <Route path="register" element={<Registration />} />
          <Route path="invite-code" element={<InviteCode />} />
          <Route path="success" element={<Success />} />
          <Route path="my-network" element={<MyNetwork />} />
        </Route>

        {/* Admin Login - redirects to universal login */}
        <Route path="/admin/login" element={<Navigate to="/login" replace />} />

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
          <Route path="registered-devices" element={<RegisteredDevices />} />
          <Route path="policy-management" element={<PolicyManagement />} />
          <Route path="profiles" element={<Profiles />} />
          <Route path="authorization-policies" element={<AuthorizationPolicies />} />
          {/* Portal Settings - Individual Pages */}
          <Route path="settings/branding" element={<Branding />} />
          <Route path="settings/meraki-api" element={<MerakiAPI />} />
          <Route path="settings/ipsk" element={<IPSKSettings />} />
          <Route path="settings/oauth" element={<OAuthSettings />} />
          <Route path="settings/cloudflare" element={<CloudflareSettings />} />
          <Route path="settings/advanced" element={<AdvancedSettings />} />
          {/* Network & WPN - Multi-step Pages */}
          <Route path="settings/network/selection" element={<NetworkSelection />} />
          <Route path="settings/network/ssid" element={<SSIDConfiguration />} />
          <Route path="settings/network/wpn-setup" element={<WPNSetupPage />} />
          {/* Registration - Multi-section Pages */}
          <Route path="settings/registration/basics" element={<RegistrationBasics />} />
          <Route path="settings/registration/login-methods" element={<LoginMethods />} />
          <Route path="settings/registration/aup" element={<AUPSettings />} />
          <Route path="settings/registration/custom-fields" element={<CustomFields />} />
          <Route path="settings/registration/ipsk-invite" element={<IPSKInviteSettings />} />
          <Route path="auth-config" element={<AuthenticationConfig />} />
          <Route path="radius" element={<RADIUSSettings />} />
          <Route path="radius/clients" element={<RADIUSClients />} />
          <Route path="radius/udn" element={<UDNManagement />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/register" replace />} />
        </Routes>
      </AuthProvider>
    </BrandingProvider>
  )
}

export default App
