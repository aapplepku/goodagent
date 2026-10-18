import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL;
if (
  process.env.CAPTURE_DEMO !== "1" ||
  !baseURL ||
  !["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)
)
  throw new Error(
    "Capture requires CAPTURE_DEMO=1 and an explicit loopback PLAYWRIGHT_BASE_URL",
  );

export default defineConfig({
  testDir: "./capture",
  outputDir: "test-results/capture",
  workers: 1,
  timeout: 300_000,
  expect: { timeout: 30_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    viewport: { width: 1440, height: 1000 },
    locale: "en-US",
    timezoneId: "UTC",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    video: process.env.CAPTURE_VIDEO === "1" ? "on" : "off",
  },
});
