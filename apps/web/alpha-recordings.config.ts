import { defineConfig, devices } from "@playwright/test";
import { loopbackOrigin } from "./capture/alpha-recording-utils";

if (process.env.CAPTURE_ALPHA !== "1" || !process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN) {
  throw new Error("Requires explicit alpha capture and a fresh disposable instance token");
}
const baseURL = loopbackOrigin(process.env.PLAYWRIGHT_BASE_URL);
loopbackOrigin(process.env.SHOPPER_PLAYWRIGHT_BASE_URL);

export default defineConfig({
  testDir: "./capture",
  testMatch: "alpha-recordings.spec.ts",
  outputDir: "test-results/alpha-recordings",
  workers: 1,
  retries: 0,
  timeout: 600000,
  expect: { timeout: 30000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    viewport: { width: 1440, height: 1000 },
    locale: "en-US",
    timezoneId: "UTC",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
