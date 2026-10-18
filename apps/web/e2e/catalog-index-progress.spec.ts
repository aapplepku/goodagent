import { expect, test } from "@playwright/test";
import type { CatalogIndexStatus, ManagerWorkspaceResponse } from "@open-commerce/sdk-typescript";

test("indexing UI fixture updates Home and Data without a misleading limited-mode warning", async ({ page }, testInfo) => {
  let index: CatalogIndexStatus = {
    status: "queued", filename: "progress-fixture.csv",
    product_count: 48, indexed_product_count: 0,
  };
  const workspace: ManagerWorkspaceResponse = {
    channels: [],
    onboarding: {
      tenant_id: "00000000-0000-0000-0000-000000000099",
      workspace_status: "completed", limited_mode: true,
      workspace_profile: { workspace_name: "Progress test store" },
    },
    capabilities: {
      semantic_backend: "hash", learned_semantics: false,
      conversation_provider: "deterministic", conversation_model: "fixture",
      model_backed: false, supported_surfaces: [], supported_ranking_signals: [],
      complex_tools_simulated: true,
    },
  };
  // These are browser-only status fixtures: no account, import or data mutation.
  await page.route("**/api/runtime/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/status")) {
      await route.fulfill({ json: { profile: "legacy_demo", setup_required: false, login_method: "legacy" } });
    } else if (path.includes("/manager/workspace")) {
      await route.fulfill({ json: { ...workspace, catalog_index: index } });
    } else {
      await route.fulfill({ status: 404, json: { error: { message: "Outside UI fixture" } } });
    }
  });
  await page.goto("/manager");
  await expect(page.getByRole("progressbar")).toBeVisible();
  await expect(page.getByRole("progressbar")).not.toHaveAttribute("value");
  await expect(page.getByText("Limited exploration mode")).toHaveCount(0);
  index = { ...index, status: "running", indexed_product_count: 12 };
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "12");
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`indexing-home-${viewport.width}.png`) });
    await page.getByRole("button", { name: /DATA READINESS/i }).click();
    await expect(page.getByRole("tabpanel").getByRole("progressbar")).toHaveAttribute("value", "12");
    await expect(page.getByRole("tabpanel").getByText("Limited exploration", { exact: true })).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`indexing-data-${viewport.width}.png`) });
    await page.getByRole("button", { name: "Close details", exact: true }).click();
  }
  index = { ...index, status: "ready", indexed_product_count: 48 };
  await expect(page.getByText("48 products ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await expect(page.getByText("Limited exploration mode")).toHaveCount(0);
});
