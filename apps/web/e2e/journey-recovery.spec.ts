import { expect, test, type Page, type TestInfo } from "@playwright/test";

const stamp = "2026-09-11T12:00:00Z";
const owner = { user_id: "fixture-owner", store: {
  id: "fixture-store", slug: "fixture-store", name: "Field Goods", readiness: {}, sharing_enabled: false,
} };
const catalog = {
  catalog: { id: "fixture-catalog", filename: "reviewed-products.csv", product_count: 1, source_version: "fixture", published_at: stamp },
  indexing: { status: "ready" }, categories: ["Grocery"], offset: 0, limit: 24, total: 1,
  items: [{ product_id: "coffee", variant_id: "coffee-default", title: "Organic coffee",
    description: "A fixture product for testing catalog access.", brand: "365 Everyday Value", category: "Grocery",
    image_url: "/abo-images/B07QCR35JF.jpg", price: { amount_minor: 1299, currency: "USD" }, availability: "available" }],
};

async function capture(page: Page, info: TestInfo, name: string) {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}.png`) });
  }
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test("private catalog signs in, labels indexing honestly, and resumes setup", async ({ page }, info) => {
  let signedIn = false;
  let catalogReads = 0;
  const readiness = { store: owner.store, indexing: { status: "ready", catalog_id: "fixture-catalog", product_count: 1, indexed_product_count: 1 },
    latest_import_id: "fixture-import", image_failures: 0, checklist: { catalog_verified: true, search_tested: false, sharing_enabled: false } };
  await page.route("**/api/runtime/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/status")) return route.fulfill({ json: { profile: "self_hosted", login_method: "local", setup_required: false } });
    if (path.endsWith("/auth/login")) { signedIn = true; return route.fulfill({ json: owner }); }
    if (!signedIn) return route.fulfill({ status: 401, json: { error: { code: "UNAUTHORIZED", message: "Sign in", request_id: "fixture" } } });
    if (path.endsWith("/auth/me")) return route.fulfill({ json: owner });
    if (path.endsWith("/manager/catalog")) { catalogReads += 1; return route.fulfill({ json: catalog }); }
    if (path.endsWith("/merchant/store")) return route.fulfill({ json: readiness });
    if (path.endsWith("/measurements")) return route.fulfill({ status: 503, json: { error: { message: "Unavailable" } } });
    if (path.endsWith("/imports/fixture-import")) return route.fulfill({ json: { id: "fixture-import", filename: "reviewed-products.csv", status: "confirmed",
      row_count: 1, product_count: 1, currency: "USD", mapping: {}, columns: [], products: [], errors: [], warnings: [], indexing: readiness.indexing } });
    return route.fulfill({ status: 404, json: { error: { message: "Outside isolated UI fixture" } } });
  });
  await page.goto("/manager/catalog");
  await expect(page.getByLabel("Username")).toBeVisible();
  expect(catalogReads).toBe(0);
  await page.getByLabel("Username").fill("fixture-owner");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-only-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("1 products in the indexed catalog")).toBeVisible();
  await expect(page.getByText("Published", { exact: true })).toHaveCount(0);
  await expect.poll(() => page.locator("article img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await capture(page, info, "catalog-private");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Catalog", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Store setup & sharing" }).click();
  await expect(page.getByRole("heading", { name: "Try your store privately" })).toBeVisible();
  await page.getByRole("button", { name: "Review sharing" }).click();
  await page.getByLabel("I reviewed the products and image issues.").check();
  await page.getByLabel("Checkout is a demo. No real payments are taken.").check();
  await expect(page.getByRole("button", { name: "Enable store link" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Test shopper search" })).toBeEnabled();
  await expect(page.getByRole("alert").filter({ hasText: "Store activity is unavailable" })).toBeVisible();
  await capture(page, info, "setup-prerequisite");
});

test("shopper retries partial loads and sign-out without losing progress", async ({ page }, info) => {
  const shopper = process.env.SHOPPER_PLAYWRIGHT_BASE_URL;
  test.skip(!shopper, "Running shopper client required; all API requests are intercepted");
  let memoryFailed = true;
  let logoutFailed = true;
  let signedIn = true;
  const reads = { cart: 0, memory: 0 };
  await page.route("**/api/runtime/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!signedIn) return route.fulfill({ status: 401, json: { error: { code: "UNAUTHORIZED", message: "Sign in", request_id: "fixture" } } });
    if (path.endsWith("/shopper/me")) return route.fulfill({ json: { account: { id: "fixture-shopper", username: "alex", display_name: "Alex", created_at: stamp } } });
    if (path.endsWith("/conversations")) return route.fulfill({ json: { items: [] } });
    if (path.endsWith("/memories")) {
      reads.memory += 1;
      return memoryFailed ? route.fulfill({ status: 503, json: { error: { message: "Unavailable" } } }) :
        route.fulfill({ json: { items: [{ id: "fixture-memory", content: "I prefer organic groceries", created_at: stamp }] } });
    }
    if (path.endsWith("/discovery")) return route.fulfill({ json: {
      catalog_status: "ready", catalog_name: "fixture.csv", product_count: 1,
      suggestions: [{ label: "Explore groceries", query: "Show organic coffee", category: "Grocery", image_url: "/abo-images/B07QCR35JF.jpg" }],
    } });
    if (path.endsWith("/cart")) { reads.cart += 1; return route.fulfill({ json: {
      id: "fixture-cart", status: "open", item_count: 1, version: 1, updated_at: stamp,
      subtotal: { amount_minor: 1299, currency: "USD" }, total: { amount_minor: 1299, currency: "USD" },
      lines: [{ id: "fixture-line", product_id: "coffee", variant_id: "default", title: "Organic coffee", variant_title: "Default", image_url: null,
        quantity: 1, unit_price: { amount_minor: 1299, currency: "USD" }, line_total: { amount_minor: 1299, currency: "USD" }, available_quantity: 10, sellable_quantity: 10 }],
    } }); }
    if (path.endsWith("/auth/logout")) {
      if (logoutFailed) return route.fulfill({ status: 503, json: { error: { message: "Unavailable" } } });
      signedIn = false;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ status: 404, json: { error: { message: "Outside isolated UI fixture" } } });
  });
  await page.goto(shopper!);
  await expect(page.getByRole("button", { name: "Open cart with 1 items" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Could not load memory" })).toBeVisible();
  await page.getByLabel("Shopping request").fill("Find something for the weekend");
  await page.getByRole("button", { name: "Shopping memory" }).click();
  await capture(page, info, "shopper-memory-recovery");
  memoryFailed = false;
  await page.getByRole("button", { name: "Retry unavailable sections" }).click();
  await expect(page.getByText("I prefer organic groceries")).toBeVisible();
  expect(reads.cart).toBe(1);
  expect(reads.memory).toBe(2);
  await page.getByRole("button", { name: "Close memory" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "may still be active" })).toBeVisible();
  await expect(page.getByLabel("Shopping request")).toHaveValue("Find something for the weekend");
  await page.getByRole("button", { name: "Open cart with 1 items" }).click();
  await capture(page, info, "shopper-signout-recovery");
  logoutFailed = false;
  await page.getByRole("button", { name: "Retry sign-out" }).click();
  await expect(page.getByLabel("Username")).toBeVisible();
});
