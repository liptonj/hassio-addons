import { test, expect } from '@playwright/test'

test.describe('Public UI smoke tests (backend-enabled)', () => {
  test('registration page renders', async ({ page }) => {
    await page.goto('/register')
    // The heading shows the property name from settings, so just check h1 exists
    await expect(page.locator('h1').first()).toBeVisible()
    await expect(page.getByRole('button', { name: /get my wifi/i })).toBeVisible()
  })

  test('registration page renders in dark mode', async ({ page }) => {
    // Emulate dark mode preference
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.goto('/register')
    
    // Check page renders
    await expect(page.locator('h1').first()).toBeVisible()
    
    // Verify dark mode is applied by checking computed background color
    const bodyBg = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor
    })
    
    // Dark mode should have a dark background (rgb values should be low)
    // gray-900 is approximately rgb(15, 23, 42) or rgb(17, 24, 39)
    expect(bodyBg).toMatch(/rgb\(1[0-9], 2[0-9], [34][0-9]\)/)
  })

  test('universal login renders email step', async ({ page }) => {
    await page.goto('/login')
    // Check for the email input field by placeholder
    await expect(page.getByPlaceholder('john@example.com')).toBeVisible()
    await expect(page.getByRole('button', { name: /continue/i })).toBeVisible()
  })

  test('user auth page renders', async ({ page }) => {
    await page.goto('/user-auth')
    // Check for the heading and form fields by placeholder
    await expect(page.locator('h1').first()).toBeVisible()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
    await expect(page.getByPlaceholder(/password/i)).toBeVisible()
  })

  test('admin login redirects to universal login', async ({ page }) => {
    // Admin login now redirects to universal login
    await page.goto('/admin/login')
    
    // Should be redirected to /login (universal login)
    await expect(page).toHaveURL('/login')
    
    // Check the universal login page renders
    await expect(page.locator('h1').first()).toBeVisible()
    await expect(page.getByPlaceholder('john@example.com')).toBeVisible()
  })

  test('register via API then check my-network page', async ({ page }, testInfo) => {
    const optionsResponse = await page.request.get('/api/options')
    expect(optionsResponse.ok()).toBeTruthy()
    const options = await optionsResponse.json()

    const uniqueEmail = `smoke_${Date.now()}_${testInfo.workerIndex}@example.com`
    const requestPayload: Record<string, unknown> = {
      name: 'Smoke Test',
      email: uniqueEmail,
      auth_method: 'ipsk',
      accept_aup: false,
      user_agent: 'playwright',
    }

    if (options.require_unit_number) {
      if (options.unit_source === 'ha_areas') {
        requestPayload.area_id = 'unit_101'
      } else if (options.unit_source === 'manual_list') {
        const firstUnit = options.units?.[0]?.area_id || '101'
        requestPayload.unit = firstUnit
      } else {
        requestPayload.unit = '101'
      }
    }

    const registerResponse = await page.request.post('/api/register', {
      data: requestPayload,
    })
    const registerBody = await registerResponse.text()
    
    // Log the response for debugging if it fails
    if (!registerResponse.ok()) {
      console.log('Registration failed:', registerBody)
    }
    expect(registerResponse.ok(), registerBody).toBeTruthy()
    
    // After registration, just verify my-network page loads
    await page.goto('/my-network')
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 })
  })

  test('dark mode theme persistence across navigation', async ({ page }) => {
    // Emulate dark mode preference
    await page.emulateMedia({ colorScheme: 'dark' })
    
    // Navigate to registration page
    await page.goto('/register')
    await expect(page.locator('h1').first()).toBeVisible()
    
    // Check body has dark background
    const bodyBgOnRegister = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor
    })
    expect(bodyBgOnRegister).toMatch(/rgb\(1[0-9], 2[0-9], [34][0-9]\)/)
    
    // Navigate to another page
    await page.goto('/user-auth')
    await expect(page.locator('h1').first()).toBeVisible()
    
    // Dark mode should persist
    const bodyBgOnAuth = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor
    })
    expect(bodyBgOnAuth).toMatch(/rgb\(1[0-9], 2[0-9], [34][0-9]\)/)
  })

  test('light mode renders correctly (default)', async ({ page }) => {
    // Explicitly set light mode
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('/register')
    
    await expect(page.locator('h1').first()).toBeVisible()
    
    // Light mode should have light background (gray-50 approximately rgb(249, 250, 251) or rgb(250, 251, 252))
    const bodyBg = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor
    })
    expect(bodyBg).toMatch(/rgb\(2[4-5][0-9], 25[0-9], 25[0-9]\)/)
  })
})
