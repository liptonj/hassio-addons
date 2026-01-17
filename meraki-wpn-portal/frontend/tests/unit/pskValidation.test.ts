import { describe, it, expect } from 'vitest'
import { validatePSK, getPSKStrength, generateRandomPSK, isCommonPassphrase } from '../../src/utils/pskValidation'

describe('pskValidation', () => {
  describe('validatePSK', () => {
    it('rejects empty passphrase', () => {
      const result = validatePSK('', 8, 63)
      expect(result.valid).toBe(false)
      expect(result.errors).toContain('Password is required')
    })

    it('rejects passphrase too short', () => {
      const result = validatePSK('short', 8, 63)
      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('at least 8'))).toBe(true)
    })

    it('rejects passphrase too long', () => {
      const result = validatePSK('A'.repeat(64), 8, 63)
      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('no more than 63'))).toBe(true)
    })

    it('accepts valid passphrase', () => {
      const result = validatePSK('ValidPass123', 8, 63)
      expect(result.valid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('rejects non-ASCII characters', () => {
      const result = validatePSK('password™', 8, 63)
      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('ASCII'))).toBe(true)
    })
  })

  describe('getPSKStrength', () => {
    it('returns weak for short password', () => {
      expect(getPSKStrength('pass')).toBe('weak')
    })

    it('returns weak for only lowercase', () => {
      expect(getPSKStrength('password')).toBe('weak')
    })

    it('returns medium for mixed case with numbers', () => {
      expect(getPSKStrength('Password123')).toBe('medium')
    })

    it('returns strong for complex password', () => {
      expect(getPSKStrength('P@ssw0rd!2023')).toBe('strong')
    })
  })

  describe('generateRandomPSK', () => {
    it('generates PSK of correct length', () => {
      const psk = generateRandomPSK(16)
      expect(psk).toHaveLength(16)
    })

    it('generates different PSKs on each call', () => {
      const psk1 = generateRandomPSK(16)
      const psk2 = generateRandomPSK(16)
      expect(psk1).not.toBe(psk2)
    })

    it('uses only allowed characters', () => {
      const psk = generateRandomPSK(100)
      // Should not contain 0, O, 1, l, I
      expect(psk).not.toMatch(/[0OI1l]/)
    })
  })

  describe('isCommonPassphrase', () => {
    it('detects common passwords', () => {
      expect(isCommonPassphrase('password')).toBe(true)
      expect(isCommonPassphrase('12345678')).toBe(true)
      expect(isCommonPassphrase('qwerty123')).toBe(true)
    })

    it('allows uncommon passwords', () => {
      expect(isCommonPassphrase('MyUn1qu3P@ss')).toBe(false)
    })

    it('is case insensitive', () => {
      expect(isCommonPassphrase('PASSWORD')).toBe(true)
      expect(isCommonPassphrase('Password')).toBe(true)
    })
  })
})
