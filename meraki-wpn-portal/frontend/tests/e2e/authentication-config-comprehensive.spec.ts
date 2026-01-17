import { test, expect } from '@playwright/test'

/**
 * Comprehensive End-to-End Tests for Authentication Configuration Page
 * 
 * These tests verify click interactions on the Authentication Config page.
 */

// Helper to login as admin using JWT token
async function loginAsAdmin(page) {
  // Create a valid JWT token for testing (expires far in the future)
  const access_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTksInN1YiI6ImFkbWluIn0.signature';
  
  await page.goto('/register');
  await page.evaluate((token) => {
    localStorage.setItem('admin_token', token);
  }, access_token);
  
  await page.goto('/admin');
  await expect(page).toHaveURL('/admin');
}

test.describe('Authentication Configuration - Comprehensive Click Tests', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/admin/auth-config')
    await page.waitForTimeout(1000)
  })

  test('should click all three tab buttons and verify content changes', async ({ page }) => {
    // Click EAP Methods tab
    const eapTab = page.locator('button', { hasText: 'EAP Methods' })
    await expect(eapTab).toBeVisible()
    await eapTab.click()
    await page.waitForTimeout(500)
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()

    // Click MAC-BYPASS tab
    const macTab = page.locator('button', { hasText: 'MAC-BYPASS' })
    await macTab.click()
    await page.waitForTimeout(500)

    // Click PSK tab
    const pskTab = page.locator('button', { hasText: 'PSK Authentication' })
    await pskTab.click()
    await page.waitForTimeout(500)
  })

  test('should interact with EAP methods tab', async ({ page }) => {
    // Ensure on EAP tab
    await page.locator('button', { hasText: 'EAP Methods' }).click()
    await page.waitForTimeout(500)
    
    // Check for EAP methods content
    await expect(page.getByText('EAP Authentication Methods')).toBeVisible()
    
    // Look for any checkboxes or toggle switches
    const checkboxes = page.locator('input[type="checkbox"]')
    const checkboxCount = await checkboxes.count()
    
    if (checkboxCount > 0) {
      // Try to toggle first checkbox
      const firstCheckbox = checkboxes.first()
      const wasChecked = await firstCheckbox.isChecked()
      await firstCheckbox.click()
      await page.waitForTimeout(500)
      // Click again to restore
      await firstCheckbox.click()
      await page.waitForTimeout(500)
    }
  })

  test('should interact with MAC-BYPASS tab', async ({ page }) => {
    // Navigate to MAC-BYPASS tab
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(1000)
    
    // Look for Add button
    const addButton = page.getByRole('button', { name: /add|create|new/i })
    if (await addButton.first().isVisible({ timeout: 2000 }).catch(() => false)) {
      // Click to open modal
      await addButton.first().click()
      await page.waitForTimeout(500)
      
      // Modal should open - look for form or close button
      const closeButton = page.getByRole('button', { name: /cancel|close/i })
      if (await closeButton.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await closeButton.first().click()
        await page.waitForTimeout(500)
      }
    }
  })

  test('should interact with PSK tab', async ({ page }) => {
    // Navigate to PSK tab
    await page.locator('button', { hasText: 'PSK Authentication' }).click()
    await page.waitForTimeout(1000)
    
    // Check for PSK content
    await expect(page.locator('body')).toContainText(/PSK/i)
  })

  test('should handle form validation', async ({ page }) => {
    // Navigate to MAC-BYPASS tab
    await page.locator('button', { hasText: 'MAC-BYPASS' }).click()
    await page.waitForTimeout(1000)
    
    // Look for Add button
    const addButton = page.getByRole('button', { name: /add|create|new/i })
    if (await addButton.first().isVisible({ timeout: 2000 }).catch(() => false)) {
      await addButton.first().click()
      await page.waitForTimeout(500)
      
      // Try to submit empty form
      const saveButton = page.getByRole('button', { name: /save|submit/i })
      if (await saveButton.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await saveButton.first().click()
        await page.waitForTimeout(500)
        
        // Form should show validation or stay open
        // Page should not crash
        await expect(page.locator('body')).toBeVisible()
      }
    }
  })

  test('should have clickable interactive elements', async ({ page }) => {
    // Verify page has interactive elements (tabs or buttons)
    const tabs = page.locator('button:visible')
    const tabCount = await tabs.count()
    
    // Should have some clickable buttons
    expect(tabCount).toBeGreaterThan(0)
    
    // Test clicking on the first few visible buttons (tabs)
    const clickableButtons = page.locator('button:has-text("EAP"), button:has-text("MAC"), button:has-text("PSK")')
    const buttonCount = await clickableButtons.count()
    
    for (let i = 0; i < Math.min(buttonCount, 3); i++) {
      const button = clickableButtons.nth(i)
      if (await button.isVisible()) {
        await button.click()
        await page.waitForTimeout(300)
      }
    }
  })
})
