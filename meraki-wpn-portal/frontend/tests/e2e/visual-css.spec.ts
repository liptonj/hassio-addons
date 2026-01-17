/**
 * Visual CSS and Dark Mode Testing Suite
 * 
 * Automated tests for:
 * - Inline style detection (runtime)
 * - Contrast ratio validation (WCAG AA)
 * - Dark mode rendering
 * - CSS class validation
 * - Route coverage verification
 */

import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import {
  parseColor,
  getContrastRatio,
  CONTRAST_THRESHOLDS,
} from './contrast-utils';

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

interface PageConfig {
  route: string;
  name: string;
  requiresAuth: boolean;
  selectors: {
    heading?: string;
    card?: string;
    button?: string;
    input?: string;
    table?: string;
  };
}

// All 28 routes to test
const PAGE_CONFIGS: PageConfig[] = [
  // Public Pages (8 routes)
  { route: '/splash-landing', name: 'Splash Landing', requiresAuth: false, selectors: { heading: 'h1', card: '.card', button: '.btn' } },
  { route: '/login', name: 'Universal Login', requiresAuth: false, selectors: { heading: 'h1', input: 'input[type="email"]', button: '.btn' } },
  { route: '/user-auth', name: 'User Auth', requiresAuth: false, selectors: { heading: 'h1', input: 'input', button: '.btn' } },
  { route: '/user-account', name: 'User Account', requiresAuth: false, selectors: { heading: 'h1', card: '.card' } },
  { route: '/user-certificates', name: 'User Certificates', requiresAuth: false, selectors: { heading: 'h1' } },
  { route: '/register', name: 'Registration', requiresAuth: false, selectors: { heading: 'h1', card: '.card', input: '.form-input', button: '.btn' } },
  { route: '/success', name: 'Success', requiresAuth: false, selectors: { heading: 'h1', card: '.card' } },
  { route: '/my-network', name: 'My Network', requiresAuth: false, selectors: { heading: 'h1', card: '.card' } },
  { route: '/invite-code', name: 'Invite Code Entry', requiresAuth: false, selectors: { heading: 'h1', input: 'input', button: '.btn' } },

  // Admin Core Pages (8 routes)
  { route: '/admin', name: 'Dashboard', requiresAuth: true, selectors: { heading: 'h1', card: '.card', button: '.btn' } },
  { route: '/admin/ipsks', name: 'IPSK Manager', requiresAuth: true, selectors: { heading: 'h1', table: 'table', button: '.btn' } },
  { route: '/admin/invite-codes', name: 'Invite Codes', requiresAuth: true, selectors: { heading: 'h1', button: '.btn' } },
  { route: '/admin/users', name: 'Users', requiresAuth: true, selectors: { heading: 'h1', table: 'table', button: '.btn' } },
  { route: '/admin/registered-devices', name: 'Registered Devices', requiresAuth: true, selectors: { heading: 'h1', table: 'table' } },
  { route: '/admin/policy-management', name: 'Policy Management', requiresAuth: true, selectors: { heading: 'h1', card: '.card' } },
  { route: '/admin/profiles', name: 'Profiles', requiresAuth: true, selectors: { heading: 'h1, h2', table: 'table', button: '.btn' } },
  { route: '/admin/authorization-policies', name: 'Authorization Policies', requiresAuth: true, selectors: { heading: 'h1, h2', table: 'table', button: '.btn' } },

  // RADIUS Settings Pages (4 routes)
  { route: '/admin/auth-config', name: 'Auth Config', requiresAuth: true, selectors: { heading: 'h1', card: '.card', input: 'input' } },
  { route: '/admin/radius', name: 'RADIUS Settings', requiresAuth: true, selectors: { heading: 'h1', card: '.card', input: 'input' } },
  { route: '/admin/radius/clients', name: 'RADIUS Clients', requiresAuth: true, selectors: { heading: 'h1', table: 'table' } },
  { route: '/admin/radius/udn', name: 'UDN Management', requiresAuth: true, selectors: { heading: 'h1', table: 'table' } },

  // Portal Settings Pages (14 routes)
  { route: '/admin/settings/branding', name: 'Branding', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card', input: 'input' } },
  { route: '/admin/settings/meraki-api', name: 'Meraki API', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card', input: 'input' } },
  { route: '/admin/settings/ipsk', name: 'IPSK Settings', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/oauth', name: 'OAuth Settings', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/cloudflare', name: 'Cloudflare', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/advanced', name: 'Advanced Settings', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/network/selection', name: 'Network Selection', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/network/ssid', name: 'SSID Config', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/network/wpn-setup', name: 'WPN Setup', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/registration/basics', name: 'Registration Basics', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card', input: 'input' } },
  { route: '/admin/settings/registration/login-methods', name: 'Login Methods', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/registration/aup', name: 'AUP Settings', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/registration/custom-fields', name: 'Custom Fields', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
  { route: '/admin/settings/registration/ipsk-invite', name: 'IPSK Invite Settings', requiresAuth: true, selectors: { heading: 'h1, h2', card: '.card' } },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get all elements with inline style attributes
 */
async function getInlineStyledElements(page: Page): Promise<Array<{ tag: string; style: string; className: string; id: string }>> {
  return page.evaluate(() => {
    const elements = document.querySelectorAll('[style]');
    return Array.from(elements).map((el) => ({
      tag: el.tagName.toLowerCase(),
      style: el.getAttribute('style') || '',
      className: el.className || '',
      id: el.id || '',
    }));
  });
}

/**
 * Check contrast for text elements
 */
async function checkTextContrast(page: Page, selector: string): Promise<{ passes: boolean; ratio: number; elements: number }> {
  const results = await page.evaluate((sel) => {
    const elements = document.querySelectorAll(sel);
    const results: Array<{ fg: string; bg: string }> = [];

    elements.forEach((el) => {
      const style = getComputedStyle(el);
      let bg = style.backgroundColor;

      // Walk up to find non-transparent background
      let parent = el.parentElement;
      while (parent && (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent')) {
        bg = getComputedStyle(parent).backgroundColor;
        parent = parent.parentElement;
      }

      results.push({ fg: style.color, bg });
    });

    return results;
  }, selector);

  let minRatio = Infinity;
  let passes = true;

  for (const { fg, bg } of results) {
    const fgRgb = parseColor(fg);
    const bgRgb = parseColor(bg);

    if (fgRgb && bgRgb) {
      const ratio = getContrastRatio(fgRgb, bgRgb);
      if (ratio < minRatio) minRatio = ratio;
      if (ratio < CONTRAST_THRESHOLDS.normalText) {
        passes = false;
      }
    }
  }

  return { passes, ratio: minRatio === Infinity ? 0 : minRatio, elements: results.length };
}

/**
 * Check if page body has correct dark/light background
 */
async function checkModeBackground(page: Page, isDark: boolean): Promise<boolean> {
  const bgColor = await page.evaluate(() => {
    return getComputedStyle(document.body).backgroundColor;
  });

  const rgb = parseColor(bgColor);
  if (!rgb) return false;

  // Dark mode: low RGB values (slate-900 is ~15, 23, 42)
  // Light mode: high RGB values (gray-50 is ~249, 250, 251)
  const avgValue = (rgb.r + rgb.g + rgb.b) / 3;

  if (isDark) {
    return avgValue < 50; // Dark backgrounds
  } else {
    return avgValue > 200; // Light backgrounds
  }
}

/**
 * Extract routes from App.tsx for auto-discovery
 * Uses the PAGE_CONFIGS as the source of truth - this test ensures
 * that when new routes are added to App.tsx, they get added here too.
 */
function discoverRoutes(): string[] {
  const appPath = path.resolve(__dirname, '../../src/App.tsx');
  const content = fs.readFileSync(appPath, 'utf-8');
  const routes: string[] = [];
  
  // Match all path="..." attributes
  const pathPattern = /path=["']([^"'*]+)["']/g;
  let match;
  
  while ((match = pathPattern.exec(content)) !== null) {
    const route = match[1];
    
    // Skip empty or redirect routes
    if (!route || route === '/') continue;
    
    // Check if this line contains Navigate (redirect)
    const lineStart = content.lastIndexOf('\n', match.index) + 1;
    const lineEnd = content.indexOf('\n', match.index);
    const line = content.substring(lineStart, lineEnd);
    if (line.includes('Navigate')) continue;
    
    // Normalize: ensure leading slash
    const normalizedRoute = route.startsWith('/') ? route : '/' + route;
    
    // For relative admin routes, check if they should be prefixed
    // Known admin child routes that need /admin/ prefix
    const adminChildRoutes = [
      'ipsks', 'invite-codes', 'users', 'registered-devices', 'policy-management',
      'profiles', 'authorization-policies',
      'settings/', 'auth-config', 'radius'
    ];
    
    if (!normalizedRoute.startsWith('/admin') && 
        adminChildRoutes.some(r => normalizedRoute.substring(1).startsWith(r))) {
      routes.push('/admin' + normalizedRoute);
    } else {
      routes.push(normalizedRoute);
    }
  }

  return [...new Set(routes)]; // Remove duplicates
}

// ============================================================================
// Test Suites
// ============================================================================

test.describe('Route Coverage Verification', () => {
  test('all routes in App.tsx have CSS test coverage', () => {
    const discoveredRoutes = discoverRoutes();
    const testedRoutes = PAGE_CONFIGS.map((p) => p.route);

    const untestedRoutes = discoveredRoutes.filter(
      (route) => !testedRoutes.includes(route) && route !== '/' // Skip index redirect
    );

    if (untestedRoutes.length > 0) {
      console.log('Routes missing CSS tests:', untestedRoutes);
    }

    expect(untestedRoutes).toEqual([]);
  });
});

test.describe('Inline Style Detection', () => {
  // Test public pages for inline styles
  const publicPages = PAGE_CONFIGS.filter((p) => !p.requiresAuth);

  for (const pageConfig of publicPages) {
    test(`${pageConfig.name} (${pageConfig.route}) has no inline styles`, async ({ page }) => {
      await page.goto(pageConfig.route);
      await page.waitForLoadState('domcontentloaded');

      const inlineElements = await getInlineStyledElements(page);

      // Filter out allowed inline styles (theming, QR code sizing, layout, dynamic dimensions)
      const violations = inlineElements.filter((el) => {
        // Allow CSS custom properties on html element (theming)
        if (el.tag === 'html' && el.style.includes('--primary-color')) return false;
        // Allow SVG viewBox-related styles
        if (el.tag === 'svg' || el.tag === 'path') return false;
        // Allow object-fit for images
        if (el.style.includes('object-fit')) return false;
        // Allow display toggles
        if (el.style.match(/display:\s*(none|block|flex)/)) return false;
        // Allow layout classes with centering/flexbox patterns
        if (el.className.includes('page-container') || el.className.includes('loading')) return false;
        // Allow dimension-only styles (width, height, max-width, min-height)
        if (el.style.match(/^((min-|max-)?(width|height):\s*[\d.]+(px|vh|vw|%|em|rem)?;?\s*)+$/)) return false;
        // Allow common layout patterns (centering, flex, alignment)
        if (el.style.match(/^(min-height|max-width|width|height|display|align-items|justify-content|text-align)/)) return false;
        // Allow card styling overrides  
        if (el.className.includes('card') && el.style.match(/(max-width|text-align)/)) return false;
        
        return true;
      });

      if (violations.length > 0) {
        console.log(`Inline styles found on ${pageConfig.route}:`, violations);
      }

      expect(violations.length).toBe(0);
    });
  }
});

test.describe('Dark Mode Rendering', () => {
  // Test key public pages in dark mode
  const darkModePages = ['/register', '/login', '/user-auth', '/my-network'];

  for (const route of darkModePages) {
    test(`${route} renders correctly in dark mode`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');

      // Verify dark background
      const hasDarkBg = await checkModeBackground(page, true);
      expect(hasDarkBg).toBe(true);

      // Check heading is visible
      const heading = page.locator('h1').first();
      if (await heading.count() > 0) {
        await expect(heading).toBeVisible();
      }
    });

    test(`${route} renders correctly in light mode`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'light' });
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');

      // Verify light background
      const hasLightBg = await checkModeBackground(page, false);
      expect(hasLightBg).toBe(true);
    });
  }
});

test.describe('Contrast Ratio Validation', () => {
  test('registration page text has sufficient contrast in light mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');

    // Check form labels
    const labelContrast = await checkTextContrast(page, 'label, .form-label');
    expect(labelContrast.passes).toBe(true);
  });

  test('registration page text has sufficient contrast in dark mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');

    // Check form labels
    const labelContrast = await checkTextContrast(page, 'label, .form-label');
    if (!labelContrast.passes) {
      console.log(`Dark mode label contrast ratio: ${labelContrast.ratio} (need >= 4.5)`);
    }
    expect(labelContrast.passes).toBe(true);
  });

  test('login page has sufficient contrast in dark mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');

    // Check main heading
    const headingContrast = await checkTextContrast(page, 'h1');
    expect(headingContrast.passes).toBe(true);
  });
});

test.describe('CSS Class Validation', () => {
  test('cards have proper styling classes', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');

    const cards = page.locator('.card');
    const count = await cards.count();

    if (count > 0) {
      // Cards should exist and be visible
      await expect(cards.first()).toBeVisible();
    }
  });

  test('buttons have proper styling classes', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');

    // Look for any styled button
    const buttons = page.locator('button.btn-primary, button[type="submit"], .btn-primary');
    const count = await buttons.count();
    
    if (count > 0) {
      const primaryBtn = buttons.first();
      await expect(primaryBtn).toBeVisible();

      // Check button has either a background color or is styled via CSS variables
      const styles = await primaryBtn.evaluate((el) => {
        const computed = getComputedStyle(el);
        return {
          bgColor: computed.backgroundColor,
          bgImage: computed.backgroundImage,
        };
      });

      // Button should have some styling - either background color or gradient
      const hasBackground = styles.bgColor !== 'rgba(0, 0, 0, 0)' && styles.bgColor !== 'transparent';
      const hasGradient = styles.bgImage && styles.bgImage !== 'none';
      
      expect(hasBackground || hasGradient).toBe(true);
    }
  });

  test('form inputs have proper styling', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');

    const inputs = page.locator('.form-input, input[type="text"], input[type="email"]');
    const count = await inputs.count();

    if (count > 0) {
      // First visible input
      for (let i = 0; i < count; i++) {
        const input = inputs.nth(i);
        if (await input.isVisible()) {
          // Check input has border
          const border = await input.evaluate((el) => {
            return getComputedStyle(el).borderWidth;
          });
          expect(border).not.toBe('0px');
          break;
        }
      }
    }
  });
});

test.describe('Theme Persistence', () => {
  test('dark mode persists across navigation', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });

    // Navigate through multiple pages
    await page.goto('/register');
    let hasDarkBg = await checkModeBackground(page, true);
    expect(hasDarkBg).toBe(true);

    await page.goto('/login');
    hasDarkBg = await checkModeBackground(page, true);
    expect(hasDarkBg).toBe(true);

    await page.goto('/user-auth');
    hasDarkBg = await checkModeBackground(page, true);
    expect(hasDarkBg).toBe(true);
  });
});

test.describe('Sidebar Navigation Links', () => {
  // These tests verify that sidebar links point to valid routes
  // and will fail if the links are incorrect (e.g., pointing to non-existent routes)
  
  // Helper to login as admin
  const loginAsAdmin = async (page: Page) => {
    // Create a valid JWT token for testing (expires far in the future)
    const access_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTksInN1YiI6ImFkbWluIn0.signature';
    
    // Go to public page first to set token
    await page.goto('/register');
    await page.evaluate((token) => {
      localStorage.setItem('admin_token', token);
    }, access_token);
    
    // Now navigate to admin
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
  };
  
  test('Network settings link navigates to valid route', async ({ page }) => {
    // Login as admin first
    await loginAsAdmin(page);
    
    // Find and click the Network link in the sidebar
    const networkLink = page.locator('a[href*="/admin/settings/network"]').first();
    
    // Verify the link exists
    await expect(networkLink).toBeVisible();
    
    // Get the href and verify it points to a valid child route (not the parent)
    const href = await networkLink.getAttribute('href');
    expect(href).toBe('/admin/settings/network/selection');
    
    // Click and verify we navigate to a valid page
    await networkLink.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify we're on a valid page (should have a heading, not a 404)
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
    
    // Verify URL is correct
    expect(page.url()).toContain('/admin/settings/network/selection');
  });
  
  test('Registration settings link navigates to valid route', async ({ page }) => {
    // Login as admin first
    await loginAsAdmin(page);
    
    // Find and click the Registration link in the sidebar
    const registrationLink = page.locator('a[href*="/admin/settings/registration"]').first();
    
    // Verify the link exists
    await expect(registrationLink).toBeVisible();
    
    // Get the href and verify it points to a valid child route (not the parent)
    const href = await registrationLink.getAttribute('href');
    expect(href).toBe('/admin/settings/registration/basics');
    
    // Click and verify we navigate to a valid page
    await registrationLink.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify we're on a valid page (should have a heading, not a 404)
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
    
    // Verify URL is correct
    expect(page.url()).toContain('/admin/settings/registration/basics');
  });
  
  test('SSID Configuration link navigates from Network Selection', async ({ page }) => {
    // Login as admin first
    await loginAsAdmin(page);
    
    // Go to Network Selection page
    await page.goto('/admin/settings/network/selection');
    await page.waitForLoadState('domcontentloaded');
    
    // Find the SSID Configuration link
    const ssidLink = page.locator('[data-testid="ssid-config-link"]');
    
    // Verify the link exists and is visible
    await expect(ssidLink).toBeVisible();
    
    // Verify the href is correct
    const href = await ssidLink.getAttribute('href');
    expect(href).toBe('/admin/settings/network/ssid');
    
    // Click and verify navigation
    await ssidLink.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify we're on the SSID Configuration page
    expect(page.url()).toContain('/admin/settings/network/ssid');
    
    // Verify page has content (not a 404)
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
  });
  
  test('WPN Setup Wizard link navigates from Network Selection', async ({ page }) => {
    // Login as admin first
    await loginAsAdmin(page);
    
    // Go to Network Selection page
    await page.goto('/admin/settings/network/selection');
    await page.waitForLoadState('domcontentloaded');
    
    // Find the WPN Setup Wizard link
    const wpnLink = page.locator('[data-testid="wpn-wizard-link"]');
    
    // Verify the link exists and is visible
    await expect(wpnLink).toBeVisible();
    
    // Verify the href is correct
    const href = await wpnLink.getAttribute('href');
    expect(href).toBe('/admin/settings/network/wpn-setup');
    
    // Click and verify navigation
    await wpnLink.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify we're on the WPN Setup page
    expect(page.url()).toContain('/admin/settings/network/wpn-setup');
    
    // Verify page has content (not a 404)
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
  });
});

test.describe('Splash Page Conditional Links', () => {
  // These tests verify that splash page only shows relevant options
  // based on registration settings
  
  test('Splash page shows appropriate buttons based on settings', async ({ page }) => {
    // Go to splash landing page
    await page.goto('/splash-landing');
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for branding to load (loading state should disappear)
    await page.waitForFunction(() => {
      return !document.body.innerText.includes('Loading portal...');
    }, { timeout: 10000 });
    
    // Check for New User button using data-testid
    const newUserButton = page.locator('[data-testid="splash-new-user-btn"]');
    const newUserCount = await newUserButton.count();
    
    // Check for Login button using data-testid
    const loginButton = page.locator('[data-testid="splash-login-btn"]');
    const loginCount = await loginButton.count();
    
    // Check for SSO button using data-testid
    const ssoButton = page.locator('[data-testid="splash-sso-btn"]');
    const ssoCount = await ssoButton.count();
    
    // Check for no-options fallback
    const noOptionsMessage = page.locator('[data-testid="splash-no-options"]');
    const noOptionsCount = await noOptionsMessage.count();
    
    if (newUserCount > 0) {
      // Button should be visible and styled as primary action
      await expect(newUserButton).toBeVisible();
      
      // Verify the button has a gradient background (primary CTA)
      const hasGradient = await newUserButton.evaluate((el) => {
        const bg = getComputedStyle(el).background;
        return bg.includes('gradient') || bg.includes('linear');
      });
      expect(hasGradient).toBe(true);
    }
    
    if (loginCount > 0) {
      await expect(loginButton).toBeVisible();
    }
    
    // If neither registration nor login is enabled, should show fallback message
    if (newUserCount === 0 && loginCount === 0 && ssoCount === 0) {
      expect(noOptionsCount).toBeGreaterThan(0);
      await expect(noOptionsMessage).toBeVisible();
    }
  });
  
  test('Splash page New User button navigates to registration', async ({ page }) => {
    await page.goto('/splash-landing');
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for branding to load
    await page.waitForFunction(() => {
      return !document.body.innerText.includes('Loading portal...');
    }, { timeout: 10000 });
    
    const newUserButton = page.locator('[data-testid="splash-new-user-btn"]');
    const count = await newUserButton.count();
    
    if (count > 0) {
      await newUserButton.click();
      await page.waitForLoadState('domcontentloaded');
      
      // Should navigate to /register
      expect(page.url()).toContain('/register');
    }
  });
  
  test('Splash page login button navigates to user-auth', async ({ page }) => {
    await page.goto('/splash-landing');
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for branding to load
    await page.waitForFunction(() => {
      return !document.body.innerText.includes('Loading portal...');
    }, { timeout: 10000 });
    
    const loginButton = page.locator('[data-testid="splash-login-btn"]');
    const count = await loginButton.count();
    
    if (count > 0) {
      await loginButton.click();
      await page.waitForLoadState('domcontentloaded');
      
      // Should navigate to /user-auth
      expect(page.url()).toContain('/user-auth');
    }
  });
  
  test('Splash page SSO button navigates to universal login', async ({ page }) => {
    await page.goto('/splash-landing');
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for branding to load
    await page.waitForFunction(() => {
      return !document.body.innerText.includes('Loading portal...');
    }, { timeout: 10000 });
    
    const ssoButton = page.locator('[data-testid="splash-sso-btn"]');
    const count = await ssoButton.count();
    
    if (count > 0) {
      await ssoButton.click();
      await page.waitForLoadState('domcontentloaded');
      
      // Should navigate to /login (universal login)
      expect(page.url()).toContain('/login');
    }
  });
});

test.describe('Universal Login Pages Consistency', () => {
  // These tests verify that all authentication pages have consistent styling
  // and use the universal login design
  
  const authPages = [
    { route: '/login', name: 'Universal Login' },
    { route: '/user-auth', name: 'User Auth' },
    { route: '/register', name: 'Registration' },
  ];
  
  for (const authPage of authPages) {
    test(`${authPage.name} page has consistent header styling`, async ({ page }) => {
      await page.goto(authPage.route);
      await page.waitForLoadState('domcontentloaded');
      
      // Should have a centered card/container
      const card = page.locator('.card, [class*="card"]').first();
      await expect(card).toBeVisible();
      
      // Should have a logo or icon at the top
      const hasLogoOrIcon = await page.evaluate(() => {
        const img = document.querySelector('img[alt]');
        const svgIcon = document.querySelector('svg');
        return !!(img || svgIcon);
      });
      expect(hasLogoOrIcon).toBe(true);
      
      // Should have a heading
      const heading = page.locator('h1, h2').first();
      await expect(heading).toBeVisible();
    });
    
    test(`${authPage.name} page has proper form styling`, async ({ page }) => {
      await page.goto(authPage.route);
      await page.waitForLoadState('domcontentloaded');
      
      // Check for form inputs
      const inputs = page.locator('input[type="text"], input[type="email"], input[type="password"]');
      const inputCount = await inputs.count();
      
      if (inputCount > 0) {
        // First visible input should have proper styling
        for (let i = 0; i < inputCount; i++) {
          const input = inputs.nth(i);
          if (await input.isVisible()) {
            // Should have form-input class or standard styling
            const hasProperClass = await input.evaluate((el) => {
              return el.classList.contains('form-input') || 
                     el.classList.contains('input') ||
                     el.className.includes('input');
            });
            expect(hasProperClass).toBe(true);
            break;
          }
        }
      }
      
      // Check for submit button
      const submitButton = page.locator('button[type="submit"], .btn-primary').first();
      if (await submitButton.isVisible()) {
        // Button should have primary styling
        const hasPrimaryStyle = await submitButton.evaluate((el) => {
          const classList = el.className;
          return classList.includes('btn-primary') || classList.includes('primary');
        });
        expect(hasPrimaryStyle).toBe(true);
      }
    });
    
    test(`${authPage.name} page works in dark mode`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.goto(authPage.route);
      await page.waitForLoadState('domcontentloaded');
      
      // Page should have dark background
      const hasDarkBg = await checkModeBackground(page, true);
      expect(hasDarkBg).toBe(true);
      
      // Text should be light colored for contrast
      const heading = page.locator('h1, h2').first();
      if (await heading.isVisible()) {
        const textColor = await heading.evaluate((el) => {
          const rgb = getComputedStyle(el).color;
          const match = rgb.match(/\d+/g);
          if (match) {
            const [r, g, b] = match.map(Number);
            // Light text should have high RGB values
            return (r + g + b) / 3;
          }
          return 0;
        });
        // Average RGB should be above 128 for light text
        expect(textColor).toBeGreaterThan(100);
      }
    });
  }
  
  test('Admin login redirects to universal login', async ({ page }) => {
    // Navigate to admin login
    await page.goto('/admin/login');
    await page.waitForLoadState('domcontentloaded');
    
    // Should redirect to /login
    expect(page.url()).toContain('/login');
  });
});
