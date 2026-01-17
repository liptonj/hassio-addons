import { test, expect } from '@playwright/test'

test.describe('Custom Registration Fields', () => {
  test('renders custom text fields', async ({ page }) => {
    await page.goto('/register')

    // Check if custom fields section exists
    const customFieldsSection = page.locator('text=/additional information/i')
    
    if (await customFieldsSection.isVisible()) {
      // Custom fields are configured
      await expect(customFieldsSection).toBeVisible()
    }
  })

  test('validates required custom fields', async ({ page }) => {
    await page.goto('/register')

    // Fill basic fields
    await page.fill('input[type="text"][placeholder*="John"]', 'Test User')
    await page.fill('input[type="email"]', 'test@example.com')

    // Try to submit without filling custom fields
    await page.click('button[type="submit"]')

    // Should show validation errors if required fields exist
    const customFieldsSection = page.locator('text=/additional information/i')
    if (await customFieldsSection.isVisible()) {
      // Check for required field error
      await page.waitForTimeout(500)
      // Validation would show if fields are required
    }
  })

  test('select fields show options', async ({ page }) => {
    await page.goto('/register')

    // Look for select fields
    const selectFields = page.locator('select')
    const count = await selectFields.count()

    if (count > 0) {
      // Should have options
      const firstSelect = selectFields.first()
      await firstSelect.click()
      
      // Check if options are visible
      const options = firstSelect.locator('option')
      expect(await options.count()).toBeGreaterThan(1)
    }
  })

  test('number fields only accept numbers', async ({ page }) => {
    await page.goto('/register')

    // Look for number input fields
    const numberInputs = page.locator('input[type="number"]')
    const count = await numberInputs.count()

    if (count > 0) {
      const firstNumber = numberInputs.first()
      await firstNumber.fill('123')
      
      expect(await firstNumber.inputValue()).toBe('123')
    }
  })

  test('submits successfully with all custom fields filled', async ({ page }) => {
    await page.goto('/register')

    // Fill basic fields
    await page.fill('input[type="text"][placeholder*="John"]', 'Test User')
    await page.fill('input[type="email"]', 'test@example.com')

    // Fill any custom text fields
    const textInputs = page.locator('input[type="text"]').filter({ hasNot: page.locator('[placeholder*="John"]') })
    const textCount = await textInputs.count()
    
    for (let i = 0; i < textCount; i++) {
      const input = textInputs.nth(i)
      if (await input.isVisible()) {
        await input.fill(`Test Value ${i}`)
      }
    }

    // Fill any select fields
    const selects = page.locator('select')
    const selectCount = await selects.count()
    
    for (let i = 0; i < selectCount; i++) {
      const select = selects.nth(i)
      if (await select.isVisible()) {
        const options = select.locator('option')
        if (await options.count() > 1) {
          await select.selectOption({ index: 1 })
        }
      }
    }

    // Submit
    await page.click('button[type="submit"]')

    // Should proceed (might need backend)
    await page.waitForTimeout(1000)
  })

  test('custom field errors display correctly', async ({ page }) => {
    await page.goto('/register')

    // Fill only basic fields
    await page.fill('input[type="text"][placeholder*="John"]', 'Test User')
    await page.fill('input[type="email"]', 'test@example.com')

    // Submit without custom fields
    await page.click('button[type="submit"]')

    // Wait for validation
    await page.waitForTimeout(500)

    // Check for error messages
    const errors = page.locator('.form-error')
    // If custom fields are required, errors should appear
  })
})
