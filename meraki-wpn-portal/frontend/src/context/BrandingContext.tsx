import { createContext, useContext, useEffect, ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPortalOptions } from '../api/client'
import type { PortalOptions } from '../types/user'

interface BrandingContextType {
  options: PortalOptions | null
  isLoading: boolean
  propertyName: string
  logoUrl: string | null
  primaryColor: string
  // New registration modes
  openRegistrationEnabled: boolean       // Anyone can sign up, immediate access
  openRegistrationApprovalEnabled: boolean // Sign up requires admin approval
  accountOnlyEnabled: boolean            // Existing accounts only
  inviteCodeAccountEnabled: boolean      // Invite code required to create account
  inviteCodeOnlyEnabled: boolean         // Enter code → get PSK (no account)
  // Legacy flags (for backwards compatibility)
  selfRegistrationEnabled: boolean
  inviteCodesEnabled: boolean
  // Login methods
  localAuthEnabled: boolean
  oauthEnabled: boolean
  ipskEnabled: boolean
  eapEnabled: boolean
  universalLoginEnabled: boolean
}

const defaultPrimaryColor = '#00a4e4' // Meraki blue

const BrandingContext = createContext<BrandingContextType | null>(null)

/**
 * Converts a hex color to an RGB string for CSS custom properties
 */
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (result) {
    return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
  }
  return '0, 164, 228' // Default meraki blue RGB
}

/**
 * Darken a hex color by a percentage
 */
function darkenColor(hex: string, percent: number): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return hex
  
  const r = Math.max(0, Math.floor(parseInt(result[1], 16) * (1 - percent / 100)))
  const g = Math.max(0, Math.floor(parseInt(result[2], 16) * (1 - percent / 100)))
  const b = Math.max(0, Math.floor(parseInt(result[3], 16) * (1 - percent / 100)))
  
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const { data: options, isLoading } = useQuery({
    queryKey: ['portal-options'],
    queryFn: getPortalOptions,
    staleTime: 1000 * 60 * 10, // 10 minutes
    retry: 2,
  })

  // Apply CSS custom properties when options change
  useEffect(() => {
    const root = document.documentElement
    const color = options?.primary_color || defaultPrimaryColor
    
    // Set primary color and variants
    root.style.setProperty('--primary-color', color)
    root.style.setProperty('--primary-color-rgb', hexToRgb(color))
    root.style.setProperty('--primary-color-dark', darkenColor(color, 20))
    root.style.setProperty('--primary-color-light', `${color}15`) // 15% opacity
    
    // Cleanup on unmount
    return () => {
      root.style.removeProperty('--primary-color')
      root.style.removeProperty('--primary-color-rgb')
      root.style.removeProperty('--primary-color-dark')
      root.style.removeProperty('--primary-color-light')
    }
  }, [options?.primary_color])

  const value: BrandingContextType = {
    options: options || null,
    isLoading,
    propertyName: options?.property_name || 'WiFi Portal',
    logoUrl: options?.logo_url || null,
    primaryColor: options?.primary_color || defaultPrimaryColor,
    // New registration modes
    openRegistrationEnabled: options?.auth_methods?.open_registration ?? options?.auth_methods?.self_registration ?? false,
    openRegistrationApprovalEnabled: options?.auth_methods?.open_registration_approval ?? false,
    accountOnlyEnabled: options?.auth_methods?.account_only ?? false,
    inviteCodeAccountEnabled: options?.auth_methods?.invite_code_account ?? options?.auth_methods?.invite_codes ?? false,
    inviteCodeOnlyEnabled: options?.auth_methods?.invite_code_only ?? false,
    // Legacy flags (for backwards compatibility)
    selfRegistrationEnabled: options?.auth_methods?.self_registration ?? false,
    inviteCodesEnabled: options?.auth_methods?.invite_codes ?? false,
    // Login methods
    localAuthEnabled: options?.auth_methods?.local ?? true,
    oauthEnabled: options?.auth_methods?.oauth ?? false,
    ipskEnabled: options?.auth_ipsk_enabled ?? true,
    eapEnabled: options?.auth_eap_enabled ?? false,
    universalLoginEnabled: options?.universal_login_enabled ?? true,
  }

  return (
    <BrandingContext.Provider value={value}>
      {children}
    </BrandingContext.Provider>
  )
}

export function useBranding() {
  const context = useContext(BrandingContext)
  if (!context) {
    throw new Error('useBranding must be used within a BrandingProvider')
  }
  return context
}

/**
 * Hook to check if any login method is available
 */
export function useHasLoginMethods() {
  const { localAuthEnabled, oauthEnabled } = useBranding()
  return localAuthEnabled || oauthEnabled
}

/**
 * Hook to check if registration is available (any registration mode enabled)
 */
export function useCanRegister() {
  const { 
    openRegistrationEnabled, 
    openRegistrationApprovalEnabled,
    inviteCodeAccountEnabled,
    inviteCodeOnlyEnabled 
  } = useBranding()
  return openRegistrationEnabled || openRegistrationApprovalEnabled || inviteCodeAccountEnabled || inviteCodeOnlyEnabled
}
