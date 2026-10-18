import { expect, test, type Page } from "@playwright/test";

const slug = process.env.OPEN_COMMERCE_RECOVERY_STORE_SLUG;
const shopperUrl = process.env.SHOPPER_PLAYWRIGHT_BASE_URL;
test.skip(!slug || !shopperUrl, "Explicit restored synthetic fixture required");

test("restored owner and shopper retain catalog, account memory and cart", async ({
  page,
  browser,
}, testInfo) => {
  const ownerUrl = process.env.PLAYWRIGHT_BASE_URL!;
  for (const value of [ownerUrl, shopperUrl!]) {
    const url = new URL(value);
    expect(url.protocol).toBe("http:");
    expect(url.hostname).toBe("127.0.0.1");
  }
  async function capture(target: Page, name: string) {
    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ]) {
      await target.setViewportSize(viewport);
      await expect.poll(() => target.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      )).toBe(true);
      await target.screenshot({ path: testInfo.outputPath(
        `${name}-${viewport.width}x${viewport.height}.png`,
      ) });
    }
    await target.setViewportSize({ width: 1440, height: 1000 });
  }
  await page.goto("/manager");
  await page.getByLabel("Username", { exact: true }).fill("recovery-fixture-owner");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-owner-recovery-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Browse catalog", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Catalog", exact: true })).toBeVisible();
  await expect(page.locator("img").first()).toBeVisible();
  await capture(page, "recovered-owner-catalog");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Catalog", exact: true })).toBeVisible();

  const context = await browser.newContext();
  const shopper = await context.newPage();
  try {
    await shopper.goto(`${shopperUrl}/s/${slug}`);
    await expect(shopper.getByRole("heading", { name: "Browse the store" })).toBeVisible();
    await shopper.getByRole("button", { name: "Save your progress", exact: true }).click();
    await shopper.getByRole("button", { name: "Sign in", exact: true }).click();
    await shopper.getByLabel("Username", { exact: true }).fill("recovery-fixture-shopper");
    await shopper.getByLabel("Password", { exact: true }).fill("synthetic-shopper-recovery-password");
    await shopper.getByLabel("Password", { exact: true }).press("Enter");
    await expect(shopper.getByRole("button", { name: "Account", exact: true })).toBeVisible();
    await expect(shopper.getByText("Recovery tester", { exact: true })).toBeVisible();
    await expect(shopper.getByRole("button", { name: "Open cart with 2 items" })).toBeVisible();
    await expect.poll(() => shopper.locator("img").evaluateAll(
      (images) => images.some((node) => node instanceof HTMLImageElement && node.complete && node.naturalWidth > 0),
    )).toBe(true);
    await capture(shopper, "recovered-shopper-catalog");
    await shopper.getByRole("button", { name: /Shopping memory/ }).click();
    await expect(shopper.getByText(/prefer organic/).last()).toBeVisible();
    await capture(shopper, "recovered-shopper-memory");
    await shopper.reload();
    await expect(shopper.getByRole("button", { name: "Open cart with 2 items" })).toBeVisible();
  } finally {
    await context.close();
  }
});
