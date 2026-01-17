/**
 * WCAG 2.1 Contrast Ratio Utilities
 * 
 * These utilities calculate color contrast ratios for accessibility testing.
 * WCAG AA requires:
 * - 4.5:1 for normal text (< 18pt or < 14pt bold)
 * - 3:1 for large text (>= 18pt or >= 14pt bold)
 * - 3:1 for UI components and graphical objects
 */

export interface RGB {
  r: number;
  g: number;
  b: number;
}

export interface ContrastResult {
  ratio: number;
  passesAA: boolean;
  passesAALarge: boolean;
  passesAAA: boolean;
  passesAAALarge: boolean;
}

/**
 * Parse a CSS color string into RGB values
 * Supports: rgb(), rgba(), hex (#fff, #ffffff)
 */
export function parseColor(color: string): RGB | null {
  if (!color || color === 'transparent' || color === 'rgba(0, 0, 0, 0)') {
    return null;
  }

  // Handle rgb/rgba
  const rgbMatch = color.match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (rgbMatch) {
    return {
      r: parseInt(rgbMatch[1], 10),
      g: parseInt(rgbMatch[2], 10),
      b: parseInt(rgbMatch[3], 10),
    };
  }

  // Handle hex colors
  const hexMatch = color.match(/^#([a-fA-F0-9]{3,8})$/);
  if (hexMatch) {
    let hex = hexMatch[1];
    // Expand shorthand (#fff -> #ffffff)
    if (hex.length === 3) {
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    }
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16),
    };
  }

  return null;
}

/**
 * Calculate relative luminance of a color
 * Formula from WCAG 2.1: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 */
export function getLuminance(rgb: RGB): number {
  const [r, g, b] = [rgb.r, rgb.g, rgb.b].map((v) => {
    const sRGB = v / 255;
    return sRGB <= 0.03928
      ? sRGB / 12.92
      : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculate contrast ratio between two colors
 * Formula from WCAG 2.1: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */
export function getContrastRatio(fg: RGB, bg: RGB): number {
  const l1 = getLuminance(fg);
  const l2 = getLuminance(bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Check if a contrast ratio meets WCAG standards
 */
export function checkContrast(ratio: number): ContrastResult {
  return {
    ratio: Math.round(ratio * 100) / 100,
    passesAA: ratio >= 4.5,        // Normal text
    passesAALarge: ratio >= 3,     // Large text (18pt+ or 14pt+ bold)
    passesAAA: ratio >= 7,         // Enhanced: normal text
    passesAAALarge: ratio >= 4.5,  // Enhanced: large text
  };
}

/**
 * Calculate contrast result between two color strings
 */
export function calculateContrast(fgColor: string, bgColor: string): ContrastResult | null {
  const fg = parseColor(fgColor);
  const bg = parseColor(bgColor);

  if (!fg || !bg) {
    return null;
  }

  const ratio = getContrastRatio(fg, bg);
  return checkContrast(ratio);
}

/**
 * Get element colors from Playwright page
 */
export async function getElementColors(
  page: { evaluate: (fn: (selector: string) => { color: string; background: string } | null, selector: string) => Promise<{ color: string; background: string } | null> },
  selector: string
): Promise<{ color: string; background: string } | null> {
  return page.evaluate((sel: string) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const style = getComputedStyle(el);
    return {
      color: style.color,
      background: style.backgroundColor,
    };
  }, selector);
}

/**
 * Check contrast for an element on a Playwright page
 */
export async function checkElementContrast(
  page: { evaluate: (fn: (selector: string) => { color: string; background: string } | null, selector: string) => Promise<{ color: string; background: string } | null> },
  selector: string,
  options: { isLargeText?: boolean } = {}
): Promise<{ passes: boolean; ratio: number; details: ContrastResult | null }> {
  const colors = await getElementColors(page, selector);
  
  if (!colors) {
    return { passes: false, ratio: 0, details: null };
  }

  const result = calculateContrast(colors.color, colors.background);
  
  if (!result) {
    return { passes: false, ratio: 0, details: null };
  }

  const passes = options.isLargeText ? result.passesAALarge : result.passesAA;
  
  return { passes, ratio: result.ratio, details: result };
}

/**
 * Standard dark mode background colors to check against
 */
export const DARK_MODE_BACKGROUNDS = {
  body: 'rgb(15, 23, 42)',        // slate-900
  card: 'rgb(30, 41, 59)',        // slate-800
  input: 'rgb(30, 41, 59)',       // slate-800
  table: 'rgb(30, 41, 59)',       // slate-800
};

/**
 * Standard light mode background colors
 */
export const LIGHT_MODE_BACKGROUNDS = {
  body: 'rgb(249, 250, 251)',     // gray-50
  card: 'rgb(255, 255, 255)',     // white
  input: 'rgb(255, 255, 255)',    // white
  table: 'rgb(255, 255, 255)',    // white
};

/**
 * Minimum acceptable contrast ratios
 */
export const CONTRAST_THRESHOLDS = {
  normalText: 4.5,    // WCAG AA
  largeText: 3,       // WCAG AA for 18pt+ or 14pt+ bold
  uiComponents: 3,    // Buttons, form controls, icons
};
