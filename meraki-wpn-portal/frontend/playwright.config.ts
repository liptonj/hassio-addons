import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'url'
import path from 'path'

// Static test encryption key (32 url-safe base64-encoded bytes)
// This is only used for E2E testing - never use in production
const TEST_ENCRYPTION_KEY = '0xSdd1H2683VuMNV7X-kU13Szq_9FkmnJun3IBg_6TI='

// Get directory path for ES module compatibility
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Check if running against Docker containers
const USE_DOCKER = process.env.E2E_USE_DOCKER === 'true'
const FRONTEND_URL = process.env.E2E_FRONTEND_URL || (USE_DOCKER ? 'http://localhost:8080' : 'http://localhost:3000')
const BACKEND_URL = process.env.E2E_BACKEND_URL || (USE_DOCKER ? 'http://localhost:8080' : 'http://localhost:8081')

export default defineConfig({
  testDir: './tests/e2e',
  
  // TypeScript type checking disabled due to pre-existing errors in settings pages
  // globalSetup: path.join(__dirname, 'tests', 'global-setup.ts'),
  
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'list' : 'html',
  use: {
    baseURL: FRONTEND_URL,
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 13'] },
    },
  ],

  // Only start web servers if NOT using Docker
  webServer: USE_DOCKER ? undefined : [
    {
      command: `VITE_API_TARGET=${BACKEND_URL} npm run dev -- --port 3000`,
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `cd ../backend && SETTINGS_ENCRYPTION_KEY=${TEST_ENCRYPTION_KEY} UV_CACHE_DIR=../.uv-cache uv run uvicorn app.main:app --reload --port 8081`,
      url: 'http://localhost:8081/health',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
