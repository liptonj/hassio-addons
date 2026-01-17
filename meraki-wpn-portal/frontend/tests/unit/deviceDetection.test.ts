import { describe, it, expect } from 'vitest'
import { getDeviceType, getDeviceInfo, supportsIOSProfile } from '../../src/utils/deviceDetection'

describe('deviceDetection', () => {
  const originalUserAgent = navigator.userAgent

  afterEach(() => {
    Object.defineProperty(navigator, 'userAgent', {
      value: originalUserAgent,
      configurable: true,
    })
  })

  describe('getDeviceType', () => {
    it('detects iOS device', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
        configurable: true,
      })
      expect(getDeviceType()).toBe('ios')
    })

    it('detects Android device', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Linux; Android 13) Mobile Safari',
        configurable: true,
      })
      expect(getDeviceType()).toBe('android')
    })

    it('detects macOS', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        configurable: true,
      })
      expect(getDeviceType()).toBe('macos')
    })

    it('detects Windows', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        configurable: true,
      })
      expect(getDeviceType()).toBe('windows')
    })
  })

  describe('getDeviceInfo', () => {
    it('returns iOS info', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X)',
        configurable: true,
      })
      const info = getDeviceInfo()
      expect(info.type).toBe('ios')
      expect(info.os).toBe('iOS')
      expect(info.supportsIOSProfile).toBe(true)
    })

    it('detects tablet', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X)',
        configurable: true,
      })
      const info = getDeviceInfo()
      expect(info.isTablet).toBe(true)
      expect(info.isMobile).toBe(false)
    })
  })

  describe('supportsIOSProfile', () => {
    it('returns true for iOS', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
        configurable: true,
      })
      expect(supportsIOSProfile()).toBe(true)
    })

    it('returns true for macOS', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        configurable: true,
      })
      expect(supportsIOSProfile()).toBe(true)
    })

    it('returns false for Android', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Linux; Android 13) Mobile Safari',
        configurable: true,
      })
      expect(supportsIOSProfile()).toBe(false)
    })
  })
})
