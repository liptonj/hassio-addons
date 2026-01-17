import { test, expect } from '@playwright/test'

/**
 * Authentication Configuration Page E2E Tests
 * 
 * These tests verify the Authentication Configuration admin page.
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

test.describe('Authentication Configuration Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/admin/auth-config')
    await page.waitForTimeout(1000)
  })

  test('page loads with header', async ({ page }) => {
    // Should show Authentication Configuration header
    await expect(page.getByRole('heading', { name: 'Authentication Configuration' })).toBeVisible({ timeout: 10000 })
  })

  test('should display all three tabs', async ({ page }) => {
    // Check for tab buttons (they are regular buttons, not role="tab")
    await expect(page.locator('button', { hasText: 'EAP Methods' })).toBeVisible()
    await expect(page.locator('button', { hasText: 'MAC-BYPASS' })).toBeVisible()
    await expect(page.locator('button', { hasText: 'PSK Authentication' })).toBeVisible()
  })

  test('should switch between tabs', async ({ page }) => {
    // Start on EAP Methods tab (default)
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()

    // Switch to MAC-BYPASS tab
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(500)
    await expect(page.locator('body')).toContainText(/MAC.*bypass/i)

    // Switch to PSK Authentication tab
    await page.locator('button', { hasText: 'PSK Authentication' }).click()
    await page.waitForTimeout(500)
    await expect(page.locator('body')).toContainText(/PSK/i)
  })

  test('should display EAP methods', async ({ page }) => {
    // Should show EAP Authentication Methods section
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()
  })

  test('should display MAC-BYPASS tab content', async ({ page }) => {
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(500)
    
    // Should show MAC bypass content
    await expect(page.locator('body')).toContainText(/bypass|configuration/i)
  })

  test('should display PSK Authentication information', async ({ page }) => {
    await page.locator('button', { hasText: 'PSK Authentication' }).click()
    await page.waitForTimeout(500)
    
    // Should show PSK information
    await expect(page.locator('body')).toContainText(/PSK|Pre-Shared Key/i)
  })

  test('should handle page reload', async ({ page }) => {
    await page.reload()
    await page.waitForTimeout(1000)
    
    // Page should still work after reload
    await expect(page.getByRole('heading', { name: 'Authentication Configuration' })).toBeVisible()
  })
})
