/**
 * Captive Portal Detection Utilities
 * 
 * Detects if the application is running in a captive portal browser
 * and provides appropriate UI hints for the user.
 */

export type CaptivePortalType = 'ios' | 'android' | 'macos' | 'none'

/**
 * Detects if the current browser is a captive portal browser
 * @returns true if running in a captive portal
 */
export function isCaptivePortal(): boolean {
  const ua = navigator.userAgent
  
  // iOS/macOS Captive Network Assistant
  if (ua.includes('CaptiveNetworkSupport')) {
    return true
  }
  
  // WeChat in-app browser (common in China)
  if (ua.includes('MicroMessenger')) {
    return true
  }
  
  // iOS Safari in standalone mode (home screen web app)
  if ((window.navigator as any).standalone === false) {
    return true
  }
  
  return false
}

/**
 * Gets the specific type of captive portal
 * @returns The portal type or 'none'
 */
export function getCaptivePortalType(): CaptivePortalType {
  const ua = navigator.userAgent
  
  if (ua.includes('CaptiveNetworkSupport')) {
    // Check if it's iOS or macOS
    if (/iPhone|iPad|iPod/.test(ua)) {
      return 'ios'
    }
    if (/Macintosh/.test(ua)) {
      return 'macos'
    }
  }
  
  // Android captive portal detection
  if (ua.includes('Chrome') && /Android/.test(ua)) {
    // Android captive portal uses Chrome but has limited functionality
    // Check for specific Android portal indicators
    if (document.referrer.includes('connectivity-check')) {
      return 'android'
    }
  }
  
  return 'none'
}

/**
 * Determines if we should show the "Done" button hint
 * @returns true if the hint should be displayed
 */
export function showCaptivePortalDoneButton(): boolean {
  return isCaptivePortal()
}

/**
 * Gets user-friendly instructions for the detected portal type
 * @returns Instructions string
 */
export function getCaptivePortalInstructions(): string {
  const type = getCaptivePortalType()
  
  switch (type) {
    case 'ios':
      return 'Tap "Done" in the top corner when finished'
    case 'macos':
      return 'Click "Done" in the top corner when finished'
    case 'android':
      return 'Tap "X" or "Close" when finished'
    default:
      return ''
  }
}
