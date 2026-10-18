import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { loopbackOrigin } from "./capture/alpha-recording-utils";
import { captureScratchPath, newPrivateCapturePath } from "./capture/catalog-demo-utils";

if (process.env.OPEN_COMMERCE_CAPTURE_CATALOG_DEMO !== "1" ||
    !process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN || !process.env.CATALOG_DEMO_OUTPUT ||
    !process.env.CATALOG_DEMO_TEST_OUTPUT || !process.env.CATALOG_DEMO_RUNTIME_DIR) {
  throw new Error("Requires an explicitly guarded disposable Basic-mode capture");
}
const baseURL = loopbackOrigin(process.env.PLAYWRIGHT_BASE_URL);
loopbackOrigin(process.env.SHOPPER_PLAYWRIGHT_BASE_URL);
const root = path.resolve(import.meta.dirname, "../..");
const output = newPrivateCapturePath(root, process.env.CATALOG_DEMO_OUTPUT);
const testOutput = captureScratchPath(root, process.env.CATALOG_DEMO_TEST_OUTPUT, {
  connected: process.connected === true,
  canSend: typeof process.send === "function",
  index: process.env.TEST_WORKER_INDEX,
});
if (output === testOutput || output.startsWith(testOutput + path.sep) || testOutput.startsWith(output + path.sep)) {
  throw new Error("Capture and Playwright output must be separate new directories");
}

export default defineConfig({
  testDir: "./capture",
  testMatch: "catalog-demo.spec.ts",
  outputDir: testOutput,
  workers: 1,
  retries: 0,
  timeout: 600000,
  expect: { timeout: 30000 },
  reporter: [["./capture/catalog-demo-reporter.ts"]],
  use: {
    ...devices["Desktop Chrome"], baseURL,
    viewport: { width: 1440, height: 1000 }, locale: "en-US", timezoneId: "UTC",
    trace: "off", screenshot: "off", video: "off", serviceWorkers: "block",
  },
});
