/**
 * PSK (Pre-Shared Key) Validation Utilities
 * 
 * Validates WiFi passwords according to WPA2 requirements
 * and provides password strength indicators
 */

export type PSKStrength = 'weak' | 'medium' | 'strong'

export interface PSKValidationResult {
  valid: boolean
  errors: string[]
}

/**
 * Validates a PSK according to WPA2 requirements
 * @param passphrase The PSK to validate
 * @param minLength Minimum length (default 8)
 * @param maxLength Maximum length (default 63)
 * @returns Validation result with errors
 */
export function validatePSK(
  passphrase: string,
  minLength: number = 8,
  maxLength: number = 63
): PSKValidationResult {
  const errors: string[] = []
  
  if (!passphrase) {
    errors.push('Password is required')
    return { valid: false, errors }
  }
  
  // Length check
  if (passphrase.length < minLength) {
    errors.push(`Password must be at least ${minLength} characters`)
  }
  
  if (passphrase.length > maxLength) {
    errors.push(`Password must be no more than ${maxLength} characters`)
  }
  
  // WPA2 only supports ASCII characters (printable)
  // eslint-disable-next-line no-control-regex
  const nonAsciiRegex = /[^\x20-\x7E]/
  if (nonAsciiRegex.test(passphrase)) {
    errors.push('Password must contain only printable ASCII characters')
  }
  
  return {
    valid: errors.length === 0,
    errors,
  }
}

/**
 * Calculates password strength
 * @param passphrase The PSK to analyze
 * @returns Strength level
 */
export function getPSKStrength(passphrase: string): PSKStrength {
  if (!passphrase || passphrase.length < 8) {
    return 'weak'
  }
  
  let score = 0
  
  // Length bonus
  if (passphrase.length >= 12) score += 1
  if (passphrase.length >= 16) score += 1
  
  // Character variety
  if (/[a-z]/.test(passphrase)) score += 1  // lowercase
  if (/[A-Z]/.test(passphrase)) score += 1  // uppercase
  if (/[0-9]/.test(passphrase)) score += 1  // numbers
  if (/[^a-zA-Z0-9]/.test(passphrase)) score += 1  // special chars
  
  // Patterns that reduce score
  if (/^[a-z]+$/.test(passphrase)) score -= 1  // only lowercase
  if (/^[0-9]+$/.test(passphrase)) score -= 2  // only numbers
  if (/(.)\1{2,}/.test(passphrase)) score -= 1  // repeated characters
  
  if (score <= 2) return 'weak'
  if (score <= 4) return 'medium'
  return 'strong'
}

/**
 * Gets a color for the strength indicator
 * @param strength The strength level
 * @returns CSS color value
 */
export function getStrengthColor(strength: PSKStrength): string {
  switch (strength) {
    case 'weak': return '#ef4444'  // red
    case 'medium': return '#f59e0b'  // orange
    case 'strong': return '#10b981'  // green
  }
}

/**
 * Gets a descriptive text for the strength
 * @param strength The strength level
 * @returns User-friendly text
 */
export function getStrengthText(strength: PSKStrength): string {
  switch (strength) {
    case 'weak': return 'Weak password'
    case 'medium': return 'Medium strength'
    case 'strong': return 'Strong password'
  }
}

/**
 * Generates a random secure PSK
 * @param length Desired length (default 16)
 * @returns A random secure passphrase
 */
export function generateRandomPSK(length: number = 16): string {
  // Character set for random generation
  // Excluding similar-looking characters: 0/O, 1/l/I
  const chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*'
  
  let result = ''
  const array = new Uint8Array(length)
  crypto.getRandomValues(array)
  
  for (let i = 0; i < length; i++) {
    result += chars[array[i] % chars.length]
  }
  
  return result
}

/**
 * Checks if a passphrase is commonly used or weak
 * @param passphrase The PSK to check
 * @returns true if the passphrase appears weak
 */
export function isCommonPassphrase(passphrase: string): boolean {
  const common = [
    'password', '12345678', 'qwerty123', 'welcome123',
    'admin123', 'letmein', 'iloveyou', 'monkey',
  ]
  
  const lower = passphrase.toLowerCase()
  return common.some(c => lower.includes(c))
}

/**
 * Gets a percentage for strength (0-100)
 * Useful for progress bars
 * @param strength The strength level
 * @returns Percentage value
 */
export function getStrengthPercentage(strength: PSKStrength): number {
  switch (strength) {
    case 'weak': return 33
    case 'medium': return 66
    case 'strong': return 100
  }
}
