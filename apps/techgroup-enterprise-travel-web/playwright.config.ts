import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config: stubs all backend traffic via page.route (no real gateway needed).
 * The dev server is started with VITE_TRAVEL_API_BASE_URL pointing at itself so
 * the recommend request is same-origin and the route stub is deterministic.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      ...process.env,
      VITE_TRAVEL_API_BASE_URL: 'http://localhost:5173',
    },
  },
});
