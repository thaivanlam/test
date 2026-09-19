import { defineConfig, devices } from "@playwright/test";

/**
 * These tests run against an already-running stack, and deliberately have no
 * `webServer` block to start one. The workflow is to bring the whole Compose
 * stack up first and confirm it is healthy, then run the suite. Keeping
 * startup out of Playwright means a test run never depends on how long the
 * stack takes to come up, and every run sees the same environment.
 *
 *   docker compose up -d
 *   cd e2e && npm test
 *
 * Set BASE_URL to point at a frontend that is not on the default port.
 */
const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],

  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: BASE_URL,
    // Traces and screenshots are kept only for failing tests. The HTML report
    // is written on every run; it and test-results/ are gitignored.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
