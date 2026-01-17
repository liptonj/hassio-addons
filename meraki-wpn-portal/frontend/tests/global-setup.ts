/**
 * Global setup for Playwright tests.
 * Runs before all tests to ensure code quality.
 */

import { execSync } from 'child_process'

async function globalSetup() {
  console.log('\n🔍 Running TypeScript type checking before tests...\n')

  try {
    // Run TypeScript type checking
    execSync('npx tsc --noEmit', {
      cwd: process.cwd(),
      stdio: 'inherit',
    })
    console.log('\n✅ TypeScript type checking passed\n')
  } catch (error) {
    console.error('\n❌ TypeScript type checking failed!')
    console.error('Fix the type errors above before running tests.\n')
    process.exit(1)
  }
}

export default globalSetup
