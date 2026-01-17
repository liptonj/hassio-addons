/**
 * Token utility functions for JWT token management
 */

/**
 * Decode a JWT token without verification (for checking expiration)
 * Note: This does NOT verify the signature - only decodes the payload
 */
export function decodeToken(token: string): { exp?: number; [key: string]: unknown } | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) {
      return null
    }
    
    const payload = parts[1]
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

/**
 * Check if a token is expired
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token)
  if (!payload || !payload.exp) {
    return true // If we can't decode or no expiration, consider it expired
  }
  
  // exp is in seconds since epoch, Date.now() is in milliseconds
  const expirationTime = payload.exp * 1000
  const now = Date.now()
  
  // Add 5 minute buffer to refresh before actual expiration
  return now >= (expirationTime - 5 * 60 * 1000)
}

/**
 * Get time until token expires in milliseconds
 */
export function getTokenExpirationTime(token: string): number | null {
  const payload = decodeToken(token)
  if (!payload || !payload.exp) {
    return null
  }
  
  const expirationTime = payload.exp * 1000
  const now = Date.now()
  return Math.max(0, expirationTime - now)
}

/**
 * Check if token needs refresh (expires within 5 minutes)
 */
export function needsTokenRefresh(token: string): boolean {
  return isTokenExpired(token)
}
