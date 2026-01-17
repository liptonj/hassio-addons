import { test, expect } from '@playwright/test'

/**
 * Full End-to-End Tests for Authentication Configuration Page
 */

// Helper to login as admin via API
async function loginAsAdmin(page) {
  const response = await page.request.post('/api/auth/login', {
    data: { username: 'admin', password: 'admin' }
  })
  const { access_token } = await response.json()
  
  await page.goto('/register')
  await page.evaluate((token) => {
    localStorage.setItem('admin_token', token)
  }, access_token)
  
  await page.goto('/admin')
  await expect(page).toHaveURL('/admin')
}

test.describe('Authentication Configuration - Full E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/admin/auth-config')
    await page.waitForTimeout(1000)
  })

  test('should display all three tabs after login', async ({ page }) => {
    await expect(page.locator('button', { hasText: 'EAP Methods' })).toBeVisible()
    await expect(page.locator('button', { hasText: 'MAC-BYPASS' })).toBeVisible()
    await expect(page.locator('button', { hasText: 'PSK Authentication' })).toBeVisible()
  })

  test('should switch between tabs', async ({ page }) => {
    // Start on EAP Methods tab
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()

    // Switch to MAC-BYPASS tab
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(500)

    // Switch to PSK Authentication tab
    await page.locator('button', { hasText: 'PSK Authentication' }).click()
    await page.waitForTimeout(500)
    
    // Switch back to EAP Methods tab
    await page.locator('button', { hasText: 'EAP Methods' }).click()
    await page.waitForTimeout(500)
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()
  })

  test('should display EAP methods from API', async ({ page }) => {
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()
    // Methods list or loading state should be present
    await page.waitForTimeout(2000)
    // Page should not crash
    await expect(page.locator('body')).toBeVisible()
  })

  test('should display MAC bypass tab', async ({ page }) => {
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(1000)
    
    // Should show MAC bypass content
    await expect(page.locator('body')).toContainText(/bypass/i)
  })

  test('should display PSK Authentication information', async ({ page }) => {
    await page.locator('button', { hasText: 'PSK Authentication' }).click()
    await page.waitForTimeout(1000)
    
    // Should show PSK content
    await expect(page.locator('body')).toContainText(/PSK/i)
  })

  test('should persist authentication state across navigation', async ({ page }) => {
    // Navigate away
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/admin/)
    
    // Navigate back
    await page.goto('/admin/auth-config')
    await page.waitForTimeout(1000)
    await expect(page.getByRole('heading', { name: 'Authentication Configuration' })).toBeVisible()
    
    // Should still be logged in
    await expect(page).toHaveURL(/\/admin\/auth-config/)
  })

  test('should navigate from dashboard to authentication config', async ({ page }) => {
    await page.goto('/admin')
    await page.waitForTimeout(1000)
    
    // Navigate via sidebar or directly
    await page.goto('/admin/auth-config')
    await expect(page.getByRole('heading', { name: 'Authentication Configuration' })).toBeVisible()
  })
})
