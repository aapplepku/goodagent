import { expect, type Page, type Request, type TestInfo } from "@playwright/test";
import type { StoreReadiness } from "@open-commerce/sdk-typescript";
import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { promisify } from "node:util";

async function capture(page: Page, info: TestInfo, name: string) {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}x${viewport.height}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

export async function verifyStoreWelcomeImages(page: Page, info: TestInfo, store: StoreReadiness) {
  const python = process.env.OPEN_COMMERCE_E2E_PYTHON;
  expect(python).toBeTruthy();
  expect(store.indexing.catalog_id).toBeTruthy();
  const result = await promisify(execFile)(python!, [
    "-m", "tests.integration.shopper_image_fixture", "--tenant", store.store.id,
    "--catalog", store.indexing.catalog_id!,
  ], { cwd: resolve(process.cwd(), "../.."), timeout: 30_000, maxBuffer: 65536 });
  const fixture: { assets: string[] } = JSON.parse(result.stdout);
  expect(fixture.assets).toHaveLength(2);
  for (const asset of fixture.assets) {
    const response = await page.request.get(new URL(asset, page.url()).href);
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toBe("no-store");
    expect(response.headers()["content-type"]).toBe("image/png");
  }
  async function reopen() {
    await page.reload();
    await expect(page.getByRole("heading", { name: "Browse the store", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Start something new", exact: true }).click();
    await expect(page.getByLabel("Conversation mode", { exact: true })).toHaveText("Basic mode: AI chat is not connected.");
  }
  await reopen();
  await expect(page.locator(".catalog-artwork")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Amazon.com / ABO" })).toHaveCount(0);
  const thumbnail = page.locator(".prompt-row img");
  await expect(thumbnail).toHaveCount(1);
  await expect.poll(() => thumbnail.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
  const asset = new URL((await thumbnail.getAttribute("src"))!, page.url()).href;
  expect(fixture.assets.map((value) => new URL(value, page.url()).href)).toContain(asset);
  await expect(thumbnail).toHaveAttribute("referrerpolicy", "no-referrer");
  expect(await thumbnail.getAttribute("srcset")).toBeNull();
  await page.waitForLoadState("networkidle");
  let repeatRequests = 0;
  const observeImage = (request: Request) => { if (request.url() === asset) repeatRequests += 1; };
  page.on("request", observeImage);
  try {
    const composer = page.getByRole("textbox");
    await composer.pressSequentially("mug");
    await expect(composer).toHaveValue("mug");
    await composer.fill("");
    await page.waitForLoadState("networkidle");
    expect(repeatRequests).toBe(0);
    await expect.poll(() => thumbnail.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
  } finally {
    page.off("request", observeImage);
  }
  await capture(page, info, "store-welcome-synthetic-image");

  // Real asset access above; one deliberately failed response below tests presentation only.
  const target = asset;
  let failures = 0;
  await page.route(target, (route) => {
    failures += 1;
    return route.fulfill({ status: 404, json: {}, headers: { "cache-control": "no-store" } });
  });
  try {
    await reopen();
    await expect.poll(() => failures).toBeGreaterThan(0);
    await expect(page.locator(".prompt-row img")).toHaveCount(0);
    const starter = page.locator(".prompt-row button").first();
    await expect(starter).toBeEnabled();
    const failuresBefore = failures;
    await capture(page, info, "store-welcome-image-unavailable");
    expect(failures).toBe(failuresBefore);
    await expect(starter).toHaveText(/Explore Catalog/);
  } finally {
    await page.unroute(target);
  }
  await reopen();
  await expect.poll(() => page.locator(".prompt-row img").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
  return fixture.assets;
}
