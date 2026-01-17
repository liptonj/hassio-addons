import { describe, it, expect } from 'vitest'
import { isCaptivePortal, getCaptivePortalType, getCaptivePortalInstructions } from '../../src/utils/captivePortal'

describe('captivePortal', () => {
  const originalUserAgent = navigator.userAgent

  afterEach(() => {
    // Restore original user agent
    Object.defineProperty(navigator, 'userAgent', {
      value: originalUserAgent,
      configurable: true,
    })
  })

  describe('isCaptivePortal', () => {
    it('detects iOS captive portal', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) CaptiveNetworkSupport',
        configurable: true,
      })
      expect(isCaptivePortal()).toBe(true)
    })

    it('detects regular browser', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
        configurable: true,
      })
      expect(isCaptivePortal()).toBe(false)
    })
  })

  describe('getCaptivePortalType', () => {
    it('identifies iOS captive portal', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) CaptiveNetworkSupport',
        configurable: true,
      })
      expect(getCaptivePortalType()).toBe('ios')
    })

    it('identifies macOS captive portal', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CaptiveNetworkSupport',
        configurable: true,
      })
      expect(getCaptivePortalType()).toBe('macos')
    })

    it('returns none for regular browser', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
        configurable: true,
      })
      expect(getCaptivePortalType()).toBe('none')
    })
  })

  describe('getCaptivePortalInstructions', () => {
    it('returns iOS instructions', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) CaptiveNetworkSupport',
        configurable: true,
      })
      const instructions = getCaptivePortalInstructions()
      expect(instructions).toContain('Done')
    })

    it('returns empty for non-captive', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
        configurable: true,
      })
      expect(getCaptivePortalInstructions()).toBe('')
    })
  })
})
