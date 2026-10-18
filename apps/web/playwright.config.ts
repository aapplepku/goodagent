import { defineConfig, devices } from "@playwright/test";

// E2E uses the running Compose stack, including its real database and worker.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 30_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ??
      `http://127.0.0.1:${process.env.WEB_PORT ?? "3000"}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
