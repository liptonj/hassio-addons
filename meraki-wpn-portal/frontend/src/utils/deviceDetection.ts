/**
 * Device Detection Utilities
 * 
 * Detects device type and capabilities from User-Agent
 */

export type DeviceType = 'ios' | 'android' | 'macos' | 'windows' | 'linux' | 'other'

export interface DeviceInfo {
  type: DeviceType
  os: string
  osVersion: string
  browser: string
  isTablet: boolean
  isMobile: boolean
  supportsIOSProfile: boolean
}

/**
 * Gets the device type from User-Agent
 * @returns The device type
 */
export function getDeviceType(): DeviceType {
  const ua = navigator.userAgent.toLowerCase()
  
  if (/iphone|ipad|ipod/.test(ua)) {
    return 'ios'
  }
  
  if (/android/.test(ua)) {
    return 'android'
  }
  
  if (/macintosh|mac os x/.test(ua)) {
    return 'macos'
  }
  
  if (/windows/.test(ua)) {
    return 'windows'
  }
  
  if (/linux/.test(ua)) {
    return 'linux'
  }
  
  return 'other'
}

/**
 * Gets detailed device information
 * @returns Device info object
 */
export function getDeviceInfo(): DeviceInfo {
  const ua = navigator.userAgent
  const type = getDeviceType()
  
  // Extract OS version
  let osVersion = 'Unknown'
  if (type === 'ios') {
    const match = ua.match(/OS (\d+)[._](\d+)/)
    if (match) {
      osVersion = `${match[1]}.${match[2]}`
    }
  } else if (type === 'android') {
    const match = ua.match(/Android (\d+\.?\d*)/)
    if (match) {
      osVersion = match[1]
    }
  } else if (type === 'macos') {
    const match = ua.match(/Mac OS X (\d+)[._](\d+)/)
    if (match) {
      osVersion = `${match[1]}.${match[2]}`
    }
  } else if (type === 'windows') {
    if (ua.includes('Windows NT 10.0')) osVersion = '10'
    else if (ua.includes('Windows NT 11.0')) osVersion = '11'
    else if (ua.includes('Windows NT 6.3')) osVersion = '8.1'
    else if (ua.includes('Windows NT 6.2')) osVersion = '8'
    else if (ua.includes('Windows NT 6.1')) osVersion = '7'
  }
  
  // Detect browser
  let browser = 'Unknown'
  if (ua.includes('Firefox')) browser = 'Firefox'
  else if (ua.includes('Chrome') && !ua.includes('Edge')) browser = 'Chrome'
  else if (ua.includes('Safari') && !ua.includes('Chrome')) browser = 'Safari'
  else if (ua.includes('Edge')) browser = 'Edge'
  
  // Detect tablet
  const isTablet = /ipad|tablet|kindle|silk/i.test(ua) || 
    (/android/i.test(ua) && !/mobile/i.test(ua))
  
  // Detect mobile
  const isMobile = /iphone|ipod|android.*mobile|windows phone/i.test(ua)
  
  // Check iOS profile support
  const supportsIOSProfile = type === 'ios' || type === 'macos'
  
  return {
    type,
    os: getOSName(type),
    osVersion,
    browser,
    isTablet,
    isMobile,
    supportsIOSProfile,
  }
}

/**
 * Gets friendly OS name
 */
function getOSName(type: DeviceType): string {
  switch (type) {
    case 'ios': return 'iOS'
    case 'android': return 'Android'
    case 'macos': return 'macOS'
    case 'windows': return 'Windows'
    case 'linux': return 'Linux'
    default: return 'Unknown'
  }
}

/**
 * Checks if the device supports iOS mobileconfig profiles
 * @returns true if iOS or macOS
 */
export function supportsIOSProfile(): boolean {
  const type = getDeviceType()
  return type === 'ios' || type === 'macos'
}

/**
 * Gets the current User-Agent string
 * Useful for passing to backend APIs
 * @returns The User-Agent string
 */
export function getUserAgent(): string {
  return navigator.userAgent
}

/**
 * Gets a friendly device description for display
 * @returns A user-friendly string like "iPhone (iOS 16.5)"
 */
export function getDeviceDescription(): string {
  const info = getDeviceInfo()
  
  if (info.type === 'ios') {
    if (navigator.userAgent.includes('iPad')) {
      return `iPad (iOS ${info.osVersion})`
    }
    return `iPhone (iOS ${info.osVersion})`
  }
  
  if (info.type === 'android') {
    return `Android ${info.osVersion}`
  }
  
  if (info.type === 'macos') {
    return `Mac (macOS ${info.osVersion})`
  }
  
  if (info.type === 'windows') {
    return `Windows ${info.osVersion}`
  }
  
  return info.os
}
