import { test, expect } from '@playwright/test'

const mockSettings = {
  run_mode: 'standalone',
  is_standalone: true,
  editable_settings: true,
  meraki_api_key: '',
  meraki_org_id: '',
}

// Create a valid JWT token with a far-future expiration
// Format: header.payload.signature (all base64 encoded)
// Payload: {"exp": 9999999999, "sub": "admin"} - expires in year 2286
const validJwtToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTksInN1YiI6ImFkbWluIn0.signature'

test.describe('Meraki org selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((token) => {
      window.localStorage.setItem('admin_token', token)
    }, validJwtToken)

    await page.route('**/api/admin/settings/all', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSettings),
      })
    })

    await page.route('**/api/admin/ipsk-options', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ networks: [], ssids: [], group_policies: [] }),
      })
    })

    await page.route('**/api/admin/settings/test-connection', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          overall_success: true,
          tests: {
            meraki_api: {
              success: true,
              message: 'Connected successfully.',
              organizations: [{ id: 'org_1', name: 'Org One' }],
            },
          },
        }),
      })
    })
  })

  test('loads orgs after test connection', async ({ page }) => {
    await page.goto('/admin/settings/meraki-api')
    
    // Wait for page to fully load (button appears after loading state)
    const testConnectionButton = page.getByRole('button', { name: /test connection/i })
    await expect(testConnectionButton).toBeVisible({ timeout: 10000 })
    await testConnectionButton.click()
    
    // Wait for the organization dropdown to be populated
    // Use locator for select element and check that it contains the expected option
    const orgSelect = page.locator('select').filter({ has: page.locator('option[value="org_1"]') })
    await expect(orgSelect).toBeVisible()
    
    // Also verify the option text is correct by checking the select has our org
    await expect(orgSelect.locator('option[value="org_1"]')).toHaveText('Org One')
  })
})
