import { expect, type Page, type Request, type Route, type TestInfo } from "@playwright/test";
import type { CatalogBrowseResponse, StoreReadiness } from "@open-commerce/sdk-typescript";
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
    await expect(page.getByRole("heading", { name: "What are we shopping for?", exact: true })).toBeVisible();
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

export async function verifyCatalogImageContinuity(page: Page, info: TestInfo, assets: string[]) {
  const catalog = page.getByRole("region", { name: "Browse store catalog" });
  const photos = catalog.getByRole("img");
  await expect(photos).toHaveCount(2);
  for (const photo of await photos.all()) {
    await expect.poll(() => photo.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
  }
  const target = new URL((await photos.first().getAttribute("src"))!, page.url()).href;
  const title = (await photos.first().getAttribute("alt"))!;
  const allowed = new Set(assets.map((value) => new URL(value, page.url()).href));
  expect(allowed.has(target)).toBe(true);
  const replacement = assets.find((value) => new URL(value, page.url()).href !== target)!;
  expect(replacement).toBeTruthy();
  await page.waitForLoadState("networkidle");
  let repeated = 0;
  const observe = (request: Request) => { if (allowed.has(request.url())) repeated += 1; };
  page.on("request", observe);
  try {
    const filter = catalog.getByRole("textbox", { name: "Find catalog products" });
    await filter.pressSequentially("mug");
    await filter.fill("");
    await page.waitForLoadState("networkidle");
    expect(repeated).toBe(0);
    await capture(page, info, "catalog-thumbnails-stable");
  } finally { page.off("request", observe); }

  // Only these browser responses change; persisted catalog data stays untouched.
  const pattern = "**/api/runtime/v1/shopper/catalog?*";
  let replaced = 0;
  const replaceCatalog = async (route: Route) => {
    const response = await route.fetch();
    const data: CatalogBrowseResponse = await response.json();
    for (const product of data.items) {
      if (product.image_url && new URL(product.image_url, page.url()).href === target) {
        product.image_url = replacement;
        replaced += 1;
      }
    }
    await route.fulfill({ response, json: data });
  };
  let failures = 0;
  await page.route(target, (route) => {
    failures += 1;
    return route.fulfill({ status: 404, json: {}, headers: { "cache-control": "no-store" } });
  });
  try {
    await page.reload();
    await expect(page.getByRole("heading", { name: "Browse the store", exact: true })).toBeVisible();
    await expect.poll(() => failures).toBeGreaterThan(0);
    await expect(catalog.getByRole("img", { name: title, exact: true })).toHaveCount(0);
    await expect(catalog.getByText("Image unavailable", { exact: true })).toBeVisible();
    await page.route(pattern, replaceCatalog);
    await catalog.getByRole("button", { name: "Refresh catalog", exact: true }).click();
    await expect.poll(() => replaced).toBeGreaterThan(0);
    const recovered = catalog.getByRole("img", { name: title, exact: true });
    await expect.poll(() => recovered.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
    expect(await recovered.evaluate((image: HTMLImageElement) => image.currentSrc)).toBe(new URL(replacement, page.url()).href);
    await capture(page, info, "catalog-thumbnail-recovered");
  } finally {
    await page.unroute(pattern, replaceCatalog);
    await page.unroute(target);
  }
  await catalog.getByRole("button", { name: "Refresh catalog", exact: true }).click();
  await expect.poll(() => catalog.getByRole("img", { name: title, exact: true }).evaluate((image: HTMLImageElement) => image.currentSrc)).toBe(target);
  await expect.poll(() => catalog.getByRole("img", { name: title, exact: true }).evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
}
