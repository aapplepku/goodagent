import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";
import type { Cart, CheckoutConfirmation, OwnerAuthResponse, PreviewResponse, ShopperAuthResponse, StoreReadiness } from "@open-commerce/sdk-typescript";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";
import { continuityCatalog, verifyCatalogContinuity, verifyChannelSaveRecovery, verifyOwnerKeyboard, verifyReviewedImportConfirmation, verifyStoreIdentity, verifyWorkspaceResetRecovery } from "./owner-continuity";
import { verifyGuestPanelRecovery, verifyShopperRecoveryCode } from "./shopper-recovery";
import { verifyCatalogImageContinuity, verifyStoreWelcomeImages } from "./store-welcome";
import { verifyShopperMemoryControls } from "./shopper-memory";

test.skip(
  !process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN,
  "Isolated setup fixture required",
);

async function captureArtwork(page: Page, info: TestInfo, name: string) {
  const artwork = page.locator(".catalog-artwork");
  await expect(artwork.getByRole("img")).toHaveCount(3);
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const photo of await artwork.getByRole("img").all()) {
      await expect(photo).toBeVisible();
      await expect.poll(() => photo.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
      const imageUrl = await photo.evaluate((image: HTMLImageElement) => image.currentSrc);
      expect(new URL(imageUrl).searchParams.get("url")).toMatch(/^\/_next\/static\/media\/B[A-Z0-9]+\.[a-zA-Z0-9_-]+\.jpg$/);
    }
    for (const credit of await artwork.getByRole("link").all()) {
      await expect(credit).toBeVisible();
      await credit.click({ trial: true });
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}x${viewport.height}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

test("owner reviews products, previews privately, shares; guest keeps progress", async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(300_000);
  const started = Date.now();
  async function captures(target: Page, prefix: string, mask: Locator[] = []) {
    await target.evaluate(() => window.scrollTo(0, 0));
    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ]) {
      await target.setViewportSize(viewport);
      await expect
        .poll(() =>
          target.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        )
        .toBe(true);
      await target.screenshot({
        path: testInfo.outputPath(
          `${prefix}-${viewport.width}x${viewport.height}.png`,
        ),
        fullPage: false,
        mask,
      });
    }
    await target.setViewportSize({ width: 1440, height: 1000 });
  }
  await page.goto("/manager");
  const optimizerParams = new URLSearchParams({
    url: "/api/runtime/v1/shopper/assets/00000000-0000-0000-0000-000000000001?store=fixture",
    w: "640", q: "75",
  });
  const operatorOptimizer = await page.request.get(`/_next/image?${optimizerParams}`);
  expect(operatorOptimizer.status()).toBe(404);
  await page.getByLabel("Store name", { exact: true }).fill("Trail & Table");
  await page
    .getByLabel("Instance setup token")
    .fill(process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN!);
  await page.getByLabel("Username", { exact: true }).fill("fixture-owner");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-owner-password");
  await page.getByRole("button", { name: "Create my store" }).click();
  await expect(
    page.getByRole("heading", { name: "Bring your products" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "I have stored it privately" })
    .click();
  await captures(page, "owner-products");
  await page.getByLabel("Upload catalog CSV").setInputFiles({
    name: "test-products.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(continuityCatalog),
  });
  await expect(
    page.getByRole("button", { name: "Confirm products" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Open workspace", exact: true }).click();
  await page.getByRole("button", { name: "Connect data", exact: true }).click();
  await expect(page.getByRole("button", { name: "I have stored it privately" })).toHaveCount(0);
  await expect(page.getByText("test-products.csv", { exact: true })).toBeVisible();
  await expect(page.getByText(/products ready to import. Awaiting your confirmation/)).toBeVisible();
  await expect(page.getByText("Store details and catalog source")).toBeVisible();
  await expect(page.getByText("Store details and catalog source").locator("..")).not.toHaveAttribute("open");
  await captures(page, "catalog-review-resumed");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByText("Edit field mapping and currency", { exact: true }).click();
  await expect(page.getByRole("combobox", { name: "product id", exact: true })).toBeVisible();
  await page.getByText("Edit field mapping and currency", { exact: true }).click();
  await page.getByRole("button", { name: "Confirm products" }).focus();
  await expect(page.getByRole("button", { name: "Confirm products" })).toBeFocused();
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("test-products.csv");
    await dialog.dismiss();
  });
  await page.getByRole("button", { name: "Cancel import", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm products" })).toBeEnabled();
  await page.getByRole("button", { name: "Confirm products" }).click();
  await expect(
    page.getByRole("button", { name: "Open shopper preview" }),
  ).toBeEnabled({ timeout: 90_000 });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Try your store privately" })).toBeVisible();
  await page.getByRole("button", { name: "Review sharing" }).click();
  await page.getByLabel("I reviewed the products and image issues.").check();
  await page.getByLabel("Checkout is a demo. No real payments are taken.").check();
  await expect(page.getByRole("button", { name: "Enable store link" })).toBeDisabled();
  await page.getByRole("button", { name: "2 Preview", exact: true }).click();
  const popup = page.context().waitForEvent("page");
  await page.getByRole("button", { name: "Open shopper preview" }).click();
  const preview = await popup;
  await expect(
    preview.getByRole("heading", { name: "What are we shopping for?" }),
  ).toBeVisible();
  await expect(preview.getByText("2 products at Trail & Table", { exact: true })).toBeVisible();
  const previewMs = Date.now() - started;
  await expect(preview.getByText("Basic mode: AI chat is not connected.", { exact: true })).toBeVisible();
  await expect(preview.getByLabel("Shopping request", { exact: true })).toHaveAttribute("placeholder", "Search for a product or category...");
  await expect(preview.locator(".shop-message")).toHaveCount(0);
  await expect(preview.locator(".catalog-artwork")).toHaveCount(0);
  await expect(preview.locator(".prompt-row img")).toHaveCount(0);
  await captures(preview, "shopper-welcome");
  const ownerOrigin = new URL(page.url()).origin;
  const readinessResponse = await page.request.get(`${ownerOrigin}/api/runtime/v1/merchant/store`);
  expect(readinessResponse.status()).toBe(200);
  const readiness: StoreReadiness = await readinessResponse.json();
  expect(readiness.checklist.search_tested).toBe(false);
  expect(readiness.store.sharing_enabled).toBe(false);
  await preview.getByRole("button", { name: "Browse catalog", exact: true }).click();
  await expect(
    preview.getByText("Private preview", { exact: false }).first(),
  ).toBeVisible();
  await preview
    .locator("details")
    .first()
    .getByText("Details", { exact: true })
    .click();
  await preview
    .getByRole("button", { name: "Ask the assistant" })
    .first()
    .click();
  await expect(preview.locator(".product-card").first()).toBeVisible({
    timeout: 90_000,
  });
  await expect(preview.locator(".shop-message").getByText("Basic mode: AI chat is not connected.", { exact: true })).toBeVisible();
  await expect(preview.locator(".product-card img")).toHaveCount(0);
  await captures(preview, "private-preview");
  // Keep presentation frames separate from synthetic image-delivery markers.
  const fixtureAssets = await verifyStoreWelcomeImages(preview, testInfo, readiness);
  async function assertImageAccessWithoutSession(status: number) {
    const visitor = await browser.newContext();
    try {
      expect(await visitor.cookies()).toEqual([]);
      for (const asset of fixtureAssets) {
        const image = await visitor.request.get(new URL(asset, process.env.SHOPPER_PLAYWRIGHT_BASE_URL).href);
        expect(image.status()).toBe(status);
        expect(image.headers()["cache-control"]).toBe("no-store");
      }
    } finally {
      await visitor.close();
    }
  }
  await assertImageAccessWithoutSession(404);
  // A replacement grant must work in the already-open document, including after failure.
  const previewPath = new URL(preview.url()).pathname;
  const previewStore = previewPath.split("/").at(-1)!;
  expect(readiness.indexing.catalog_id).toBeTruthy();
  const previewExchanges: string[] = [];
  preview.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === `/api/runtime/v1/stores/${previewStore}/preview`)
      previewExchanges.push(request.method());
  });
  async function replacePreview(valid: boolean) {
    let token = "synthetic-invalid-preview-grant";
    if (valid) {
      const grantResponse = await page.request.post(`${ownerOrigin}/api/runtime/v1/merchant/store/preview`, {
        headers: { origin: ownerOrigin, "Idempotency-Key": `replacement-preview-${previewExchanges.length}` },
        data: { catalog_id: readiness.indexing.catalog_id },
      });
      expect(grantResponse.status()).toBe(200);
      const grant: PreviewResponse = await grantResponse.json();
      token = grant.token;
    }
    const before = previewExchanges.length;
    const exchanged = preview.waitForResponse((response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === `/api/runtime/v1/stores/${previewStore}/preview`,
    );
    await preview.evaluate((grant) => { location.hash = `preview=${encodeURIComponent(grant)}`; }, token);
    expect((await exchanged).status()).toBe(valid ? 200 : 401);
    await expect(preview).toHaveURL(new URL(previewPath, process.env.SHOPPER_PLAYWRIGHT_BASE_URL).href);
    if (valid) {
      await expect(preview.getByRole("heading", { name: "What are we shopping for?" })).toBeVisible();
      await expect(preview.getByText("Private preview", { exact: false }).first()).toBeVisible();
    } else {
      await expect(preview.getByRole("heading", { name: "This store is unavailable" })).toBeVisible();
      await expect(preview.getByRole("heading", { name: "Travel mug", exact: true })).toHaveCount(0);
    }
    expect(previewExchanges).toHaveLength(before + 1);
  }
  await replacePreview(true);
  await replacePreview(false);
  await replacePreview(true);
  await preview.close();
  await page.getByRole("button", { name: "Review sharing" }).click();
  await page.getByLabel("I reviewed the products and image issues.").check();
  await page
    .getByLabel("Checkout is a demo. No real payments are taken.")
    .check();
  await page.getByRole("button", { name: "Enable store link" }).click();
  await expect(page.getByRole("heading", { name: "Your store link is enabled" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Store link enabled", exact: true })).toBeDisabled();
  const storeLink = await page
    .getByRole("link", { name: "Open shared store" })
    .getAttribute("href");
  expect(storeLink).toBeTruthy();
  const sharedUrl = new URL(storeLink!, page.url());
  const slug = sharedUrl.searchParams.get("store");
  expect(slug).toBeTruthy();
  expect(sharedUrl.hash).toBe("");
  optimizerParams.set("url", `/api/runtime/v1/shopper/assets/00000000-0000-0000-0000-000000000001?store=${slug}`);
  const shopperOptimizer = new URL(`/_next/image?${optimizerParams}`, process.env.SHOPPER_PLAYWRIGHT_BASE_URL).href;
  expect((await page.request.get(shopperOptimizer)).status()).toBe(400);
  await assertImageAccessWithoutSession(200);
  await page.getByLabel("Failed imports", { exact: true }).click();
  await expect(
    page.getByLabel("Failed imports", { exact: true }),
  ).toBeChecked();
  await expect(page.getByText("No failed indexing job.")).toBeVisible();
  await captures(page, "owner-ready");

  const guestContext = await browser.newContext();
  const shopper = await guestContext.newPage();
  const guestStarted = Date.now();
  // Follow the published link, including the operator-to-shopper redirect.
  await shopper.goto(sharedUrl.href);
  await expect(shopper).toHaveURL(
    new URL(`/s/${slug}`, process.env.SHOPPER_PLAYWRIGHT_BASE_URL).href,
  );
  await expect(
    shopper.getByRole("heading", { name: "Travel mug", exact: true }),
  ).toBeVisible();
  const firstResultMs = Date.now() - guestStarted;
  await shopper.getByRole("button", { name: "Start something new", exact: true }).click();
  await expect(shopper.getByLabel("Conversation mode", { exact: true })).toHaveText("Basic mode: AI chat is not connected.");
  await expect(shopper.getByLabel("Shopping request", { exact: true })).toHaveAttribute("placeholder", "Search for a product or category...");
  await expect(shopper.locator(".shop-message")).toHaveCount(0);
  await expect(shopper.locator(".catalog-artwork")).toHaveCount(0);
  await expect.poll(() => shopper.locator(".prompt-row img").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(16);
  await captures(shopper, "public-shopper-basic-welcome");
  await shopper.getByRole("button", { name: "Browse catalog", exact: true }).click();
  await verifyCatalogImageContinuity(shopper, testInfo, fixtureAssets);
  await shopper.setViewportSize({ width: 390, height: 844 });
  await shopper.getByLabel("In stock", { exact: true }).check();
  await expect(shopper.getByText("2 products matching filters", { exact: true })).toBeVisible();
  let releaseFilter!: () => void;
  const heldFilter = new Promise<void>((resolve) => { releaseFilter = resolve; });
  const delayedCatalog = (url: URL) => url.pathname === "/api/runtime/v1/shopper/catalog" && url.searchParams.get("q") === "not-a-fixture-product";
  await shopper.route(delayedCatalog, async (route) => {
    await heldFilter;
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic catalog outage" }) });
  });
  try {
    await shopper.getByLabel("Find catalog products").fill("not-a-fixture-product");
    await shopper.getByRole("button", { name: "Find products", exact: true }).click();
    await expect(shopper.getByText("Updating results...", { exact: true })).toBeVisible();
    await expect(shopper.getByText(/products? matching filters/)).toHaveCount(0);
    await expect(shopper.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
    await expect(shopper.getByRole("button", { name: "Add Travel mug to cart" })).toBeDisabled();
    await captures(shopper, "catalog-filter-updating");
    releaseFilter();
    await expect(shopper.getByText("Previous results", { exact: true })).toBeVisible();
    await expect(shopper.getByRole("region", { name: "Browse store catalog" }).getByRole("alert")).toContainText("Showing last loaded data.");
    await captures(shopper, "catalog-filter-failed");
  } finally {
    releaseFilter();
    await shopper.unroute(delayedCatalog);
  }
  await shopper.getByRole("button", { name: "Refresh catalog", exact: true }).click();
  await expect(shopper.getByRole("heading", { name: "No matching products" })).toBeVisible();
  await captures(shopper, "empty-filter-recovery");
  await shopper.getByRole("button", { name: "Clear filters", exact: true }).click();
  await expect(shopper.getByLabel("In stock", { exact: true })).not.toBeChecked();
  await expect(shopper.getByLabel("Find catalog products")).toHaveValue("");
  await expect(shopper.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
  await shopper.getByLabel("Find catalog products").fill("Travel mug");
  await shopper.getByRole("button", { name: "Find products", exact: true }).click();
  await expect(shopper.getByText("1 product matching filters", { exact: true })).toBeVisible();
  await shopper.getByLabel("Find catalog products").fill("");
  await shopper.getByRole("button", { name: "Find products", exact: true }).click();
  await expect(shopper.getByText("2 products", { exact: true })).toBeVisible();
  await shopper.setViewportSize({ width: 390, height: 844 });
  await shopper.getByRole("button", { name: "Add Travel mug to cart" }).click();
  await expect(shopper.getByLabel("Choose a variant")).toBeVisible();
  await shopper.getByLabel("Choose a variant").selectOption("large");
  await shopper
    .getByRole("button", { name: "Add to cart", exact: true })
    .click();
  await expect(shopper.getByText("Your cart", { exact: true })).toBeVisible();
  await shopper.getByRole("button", { name: "Close cart" }).click();
  await shopper.setViewportSize({ width: 1440, height: 1000 });
  await shopper
    .getByRole("button", { name: "Save your progress", exact: true })
    .click();
  await expect(shopper.getByRole("button", { name: "Close account" })).toBeFocused();
  await shopper.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    shopper.getByText(/activity logs and personal monitoring rules are temporary/),
  ).toBeVisible();
  await captures(shopper, "sign-in-disclosure");
  await shopper.getByRole("button", { name: "Create account", exact: true }).click();
  await shopper.getByLabel("Display name").fill("Alex");
  await shopper.getByLabel("Username", { exact: true }).fill("fixture-shopper");
  await shopper
    .getByLabel("Password", { exact: true })
    .fill("synthetic-shopper-password");
  const registered = shopper.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/runtime/v1/shopper/auth/register" && response.request().method() === "POST",
  );
  await shopper
    .getByRole("button", { name: "Save my progress", exact: true })
    .click();
  await expect(
    shopper.getByText("One-time recovery code", { exact: true }),
  ).toBeVisible();
  const registration: ShopperAuthResponse = await (await registered).json();
  expect(registration.recovery_code).toBeTruthy();
  let currentRecoveryCode = registration.recovery_code!;
  await shopper
    .getByRole("button", { name: "I have stored it", exact: true })
    .click();
  await verifyShopperMemoryControls(shopper, testInfo, slug!, registration.account.id);
  let memoryRequests = 0;
  let memoryRequestKey: string | undefined;
  await shopper.route("**/v1/shopper/preferences", async (route) => {
    memoryRequests += 1;
    const key = route.request().headers()["idempotency-key"];
    if (memoryRequests > 1) {
      expect(key).toBe(memoryRequestKey);
      return route.continue();
    }
    memoryRequestKey = key;
    expect(key).toBeTruthy();
    const committed = await route.fetch({ maxRetries: 0 });
    expect(committed.ok()).toBe(true);
    expect((await committed.json()).account.memory_enabled).toBe(false);
    await route.abort("failed");
  });
  await shopper.getByLabel("Remember shopping preferences").focus();
  await shopper.keyboard.press("Space");
  await expect(shopper.getByText(/Memory setting is unverified/)).toBeVisible();
  await captures(shopper, "memory-unverified");
  await shopper.reload();
  await expect(shopper.getByText(/Memory setting is unverified/)).toBeVisible();
  await shopper.getByRole("button", { name: "Retry memory change", exact: true }).click();
  await expect(shopper.getByText(/Memory setting is unverified/)).toHaveCount(0);
  expect(memoryRequests).toBe(2);
  await shopper.getByRole("button", { name: "Account", exact: true }).click();
  await expect(
    shopper.getByLabel("Remember shopping preferences"),
  ).not.toBeChecked();
  await shopper.getByRole("button", { name: "View active sessions", exact: true }).click();
  await expect(shopper.getByText(/This device/)).toBeVisible();
  await shopper.getByRole("button", { name: "Delete shopping data", exact: true }).click();
  await expect(shopper.getByRole("button", { name: "Confirm deletion", exact: true })).toBeVisible();
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await shopper.setViewportSize(viewport);
    for (const name of ["View active sessions", "Sign out everywhere", "Delete shopping data", "Confirm deletion"]) {
      const box = await shopper.getByRole("button", { name, exact: true }).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    const memory = shopper.getByLabel("Remember shopping preferences");
    const label = await memory.locator("..").boundingBox();
    const checkbox = await memory.boundingBox();
    expect(label).not.toBeNull();
    expect(checkbox).not.toBeNull();
    expect(checkbox!.x - label!.x).toBeLessThan(24);
  }
  await captures(shopper, "account-controls");
  // Review the destructive action without executing it or changing the retained cart.
  await shopper.getByRole("button", { name: "Delete shopping data", exact: true }).click();
  await expect(shopper.getByRole("button", { name: "Confirm deletion", exact: true })).toHaveCount(0);
  await shopper.getByRole("button", { name: "Close account" }).click();
  await shopper.reload();
  await expect(
    shopper.getByRole("heading", { name: "Browse the store" }),
  ).toBeVisible();
  await expect(
    shopper.getByRole("heading", { name: "Travel mug", exact: true }),
  ).toBeVisible();
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await shopper.setViewportSize(viewport);
    const opener = shopper.getByRole("button", { name: "Account", exact: true });
    await opener.focus();
    await shopper.keyboard.press("Enter");
    await expect(shopper.getByRole("button", { name: "Close account" })).toBeFocused();
    await expect(shopper.getByLabel("Remember shopping preferences")).not.toBeChecked();
    await shopper.getByLabel("Remember shopping preferences").focus();
    await shopper.keyboard.press("Escape");
    await expect(shopper.getByLabel("Shopping account", { exact: true })).toHaveCount(0);
    await expect(opener).toBeFocused();
  }
  await captures(shopper, "shopper-browse");
  await shopper.getByRole("button", { name: /Open cart with/ }).click();
  await expect(
    shopper.getByText("Travel mug", { exact: true }).last(),
  ).toBeVisible();
  await shopper.getByRole("button", { name: "Review checkout" }).click();
  const holdDeadline = shopper.locator(".checkout-heading time");
  await expect(holdDeadline).toBeVisible();
  expect(Number.isFinite(Date.parse((await holdDeadline.getAttribute("datetime"))!))).toBe(true);
  await expect(shopper.getByText("Inventory is held for 15 minutes.", { exact: true })).toHaveCount(0);
  await captures(shopper, "checkout-hold-deadline");
  // Drop the response only after the real server has processed the explicit payment.
  let dropped = false;
  let confirmationRequests = 0;
  let committedOrderNumber: string | null = null;
  await shopper.route("**/v1/shopper/checkout/confirm", async (route) => {
    confirmationRequests += 1;
    if (dropped) return route.continue();
    dropped = true;
    const response = await route.fetch({ maxRetries: 0 });
    expect(response.ok()).toBe(true);
    const confirmation: CheckoutConfirmation = await response.json();
    expect(confirmation.status).toBe("succeeded");
    expect(confirmation.order).not.toBeNull();
    committedOrderNumber = confirmation.order!.order_number;
    expect(committedOrderNumber).toBeTruthy();
    await route.abort("failed");
  });
  await shopper.getByRole("button", { name: "Approve test payment" }).click();
  await expect(shopper.getByText("Order confirmed")).toBeVisible();
  expect(dropped).toBe(true);
  expect(confirmationRequests).toBe(1);
  const orderNumber = await shopper.locator(".order-confirmation dd").first().textContent();
  expect(orderNumber).toBe(committedOrderNumber);
  await shopper.reload();
  await shopper.getByRole("button", { name: "Demo orders", exact: true }).click();
  await expect(shopper.getByLabel("Demo orders").getByText(orderNumber!, { exact: true })).toBeVisible();
  await expect(shopper.locator(".order-history-item")).toHaveCount(1);
  expect(confirmationRequests).toBe(1);
  await shopper.locator(".order-history-item summary").first().click();
  await expect(shopper.getByLabel("Demo orders").getByText("Travel mug", { exact: true })).toBeVisible();
  await captures(shopper, "demo-orders");
  await shopper.getByRole("button", { name: "Close orders" }).focus();
  await shopper.keyboard.press("Escape");
  await expect(shopper.getByLabel("Demo orders")).toHaveCount(0);
  await expect(shopper.getByRole("button", { name: "Demo orders", exact: true })).toBeFocused();
  // Returning customer: review two real carts before discarding either one.
  await shopper.getByRole("button", { name: "Add Travel mug to cart" }).click();
  await shopper.getByLabel("Choose a variant").selectOption("large");
  await shopper.getByRole("button", { name: "Add to cart", exact: true }).click();
  await shopper.getByRole("button", { name: "Close cart" }).click();
  await shopper.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(shopper.getByRole("button", { name: "Save your progress", exact: true })).toBeVisible();
  await shopper.getByRole("button", { name: "Add Soft cotton throw to cart" }).click();
  await shopper.getByRole("button", { name: "Close cart" }).click();
  await shopper.getByRole("button", { name: "Save your progress", exact: true }).click();
  await shopper.getByRole("button", { name: "Sign in", exact: true }).click();
  await shopper.getByLabel("Username", { exact: true }).fill("fixture-shopper");
  await shopper.getByLabel("Password", { exact: true }).fill("synthetic-shopper-password");
  await shopper.getByLabel("Password", { exact: true }).press("Enter");
  await expect(shopper.getByRole("heading", { name: "Which cart should we keep?" })).toBeVisible();
  await expect(shopper.locator(".account-controls li").filter({ hasText: "Travel mug" })).toBeVisible();
  await expect(shopper.locator(".account-controls li").filter({ hasText: "Soft cotton throw" })).toBeVisible();
  const keepVisit = shopper.getByRole("button", { name: "Keep this visit's cart (1 product)", exact: true });
  const keepAccount = shopper.getByRole("button", { name: "Keep account cart (1 product)", exact: true });
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await shopper.setViewportSize(viewport);
    for (const button of [keepVisit, keepAccount, shopper.getByRole("button", { name: "Back to sign in", exact: true })]) {
      const box = await button.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
  }
  await captures(shopper, "cart-choice");
  const recoveryOrigin = new URL(shopper.url()).origin;
  const recoveryHeaders = { origin: recoveryOrigin, "x-store-slug": slug! };
  const guestBeforeReset: ShopperAuthResponse = await (await shopper.request.get(
    `${recoveryOrigin}/api/runtime/v1/shopper/me`, { headers: recoveryHeaders },
  )).json();
  expect(guestBeforeReset.account.is_guest).toBe(true);
  const recoveryContext = await browser.newContext();
  try {
    // Reset the synthetic target in a separate cookie jar while the guest reviews its old grant.
    const recovered = await recoveryContext.request.post(`${recoveryOrigin}/api/runtime/v1/shopper/auth/recover`, {
      headers: recoveryHeaders,
      data: { username: "fixture-shopper", code: registration.recovery_code, password: "synthetic-shopper-password" },
    });
    expect(recovered.status()).toBe(200);
    const resetAccount: ShopperAuthResponse = await recovered.json();
    expect(resetAccount.recovery_code).toBeTruthy();
    currentRecoveryCode = resetAccount.recovery_code!;
    const rejected = shopper.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/shopper/auth/merge" && response.request().method() === "POST",
    );
    await keepAccount.click();
    expect((await rejected).status()).toBe(401);
    await expect(shopper.getByLabel("Shopping account").getByRole("alert")).toContainText("Sign in again to review cart changes.");
    await expect(shopper.getByRole("heading", { name: "Your shopping session expired", exact: true })).toHaveCount(0);
    const guestAfterReset: ShopperAuthResponse = await (await shopper.request.get(
      `${recoveryOrigin}/api/runtime/v1/shopper/me`, { headers: recoveryHeaders },
    )).json();
    expect(guestAfterReset.account.id).toBe(guestBeforeReset.account.id);
    const guestCart: Cart = await (await shopper.request.get(`${recoveryOrigin}/api/runtime/v1/shopper/cart`, { headers: recoveryHeaders })).json();
    const accountCart: Cart = await (await recoveryContext.request.get(`${recoveryOrigin}/api/runtime/v1/shopper/cart`, { headers: recoveryHeaders })).json();
    expect(guestCart.lines?.map((line) => line.product_id)).toEqual(["throw"]);
    expect(accountCart.lines?.map((line) => line.product_id)).toEqual(["mug"]);
    await captures(shopper, "cart-permission-recovery");
  } finally {
    await recoveryContext.close();
  }
  await shopper.getByRole("button", { name: "Back to sign in", exact: true }).click();
  await shopper.getByLabel("Username", { exact: true }).fill("fixture-shopper");
  await shopper.getByLabel("Password", { exact: true }).fill("synthetic-shopper-password");
  await shopper.getByLabel("Password", { exact: true }).press("Enter");
  await expect(shopper.getByRole("heading", { name: "Which cart should we keep?" })).toBeVisible();
  await keepVisit.focus();
  await shopper.keyboard.press("Tab");
  await expect(keepAccount).toBeFocused();
  await shopper.keyboard.press("Enter");
  await expect(shopper.getByRole("button", { name: "Account", exact: true })).toBeVisible();
  await shopper.getByRole("button", { name: /Open cart with/ }).click();
  await expect(shopper.locator(".cart-scroll").getByText("Travel mug", { exact: true })).toBeVisible();
  await expect(shopper.locator(".cart-scroll").getByText("Soft cotton throw", { exact: true })).toHaveCount(0);

  async function currentCart(): Promise<Cart> {
    const response = await shopper.request.get(
      new URL("/api/runtime/v1/shopper/cart", shopper.url()).href,
      { headers: { "x-store-slug": slug! } },
    );
    expect(response.ok()).toBe(true);
    return response.json();
  }
  const savedCart = await currentCart();
  expect(savedCart.id).toBeTruthy();
  expect(savedCart.lines).toHaveLength(1);
  expect(savedCart.lines![0]).toMatchObject({
    product_id: "mug", variant_id: "large", quantity: 1,
    unit_price: { amount_minor: 1900, currency: "USD" },
  });
  expect(savedCart.total).toEqual({ amount_minor: 1900, currency: "USD" });
  await shopper.getByRole("button", { name: "Close cart", exact: true }).click();
  await shopper.getByRole("button", { name: "Browse catalog", exact: true }).click();
  await expect(shopper.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
  // Hold a real refresh until revocation is committed, independent of poll timing.
  let releaseCatalogRead!: () => void;
  const heldCatalogRead = new Promise<void>((resolve) => { releaseCatalogRead = resolve; });
  const catalogRequests = "**/api/runtime/v1/shopper/catalog**";
  await shopper.route(catalogRequests, async (route) => {
    await heldCatalogRead;
    await route.continue();
  });
  try {
    await shopper.getByRole("button", { name: "Refresh catalog", exact: true }).click();
    await page.getByRole("button", { name: "Disable sharing", exact: true }).click();
    await expect(page.getByRole("link", { name: "Open shared store" })).toHaveCount(0);
    // Revoke access for the already-issued session, not only a brand-new visitor.
    const revoked = await shopper.request.get(
      new URL("/api/runtime/v1/shopper/store", shopper.url()).href,
      { headers: { "x-store-slug": slug! } },
    );
    expect(revoked.status()).toBe(404);
    expect((await revoked.json()).error.code).toBe("STORE_UNAVAILABLE");
    expect((await shopper.request.get(shopperOptimizer)).status()).toBe(400);
    for (const asset of fixtureAssets) {
      expect((await shopper.request.get(new URL(asset, shopper.url()).href)).status()).toBe(404);
    }
    await assertImageAccessWithoutSession(404);
    releaseCatalogRead();
    // A mounted catalog must close on denial, without a document reload.
    await expect(shopper.getByRole("heading", { name: "This store is unavailable" })).toBeVisible();
  } finally {
    releaseCatalogRead();
    await shopper.unroute(catalogRequests);
  }
  await expect(shopper.getByRole("heading", { name: "Travel mug", exact: true })).toHaveCount(0);
  const retryStore = shopper.getByRole("button", { name: "Try again", exact: true });
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await shopper.setViewportSize(viewport);
    const box = await retryStore.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
    await retryStore.focus();
    // Establish keyboard modality; programmatic focus after a click need not be focus-visible.
    await shopper.keyboard.press("Shift+Tab");
    await shopper.keyboard.press("Tab");
    await expect(retryStore).toBeFocused();
    await expect(retryStore).toHaveCSS("outline-style", "solid");
    await expect(retryStore).toHaveCSS("outline-width", "3px");
  }
  await captures(shopper, "sharing-disabled");

  const newVisitor = await browser.newContext();
  try {
    const closedStore = await newVisitor.newPage();
    const storefrontResponse = closedStore.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/shopper/store",
    );
    await closedStore.goto(sharedUrl.href);
    expect((await storefrontResponse).status()).toBe(404);
    await expect(closedStore.getByRole("heading", { name: "This store is unavailable" })).toBeVisible();
  } finally {
    await newVisitor.close();
  }

  await page.getByRole("button", { name: "Enable store link", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open shared store" })).toBeVisible();
  await retryStore.focus();
  await shopper.keyboard.press("Enter");
  await expect(shopper.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
  await expect(shopper.getByRole("button", { name: "Account", exact: true })).toBeVisible();
  await shopper.getByRole("button", { name: /Open cart with/ }).click();
  await expect(shopper.locator(".cart-scroll").getByText("Travel mug", { exact: true })).toBeVisible();
  const restoredCart = await currentCart();
  expect(restoredCart.id).toBe(savedCart.id);
  expect(restoredCart.lines).toEqual(savedCart.lines);
  expect(restoredCart.item_count).toBe(savedCart.item_count);
  expect(restoredCart.total).toEqual(savedCart.total);
  expect(restoredCart.status).toBe("open");

  // Keep the existing journey evidence intact; inject faults only after its final cart check.
  await shopper.getByRole("button", { name: "Close cart" }).click();
  const accountResponse = await shopper.request.get(
    new URL("/api/runtime/v1/shopper/me", shopper.url()).href,
    { headers: { "x-store-slug": slug! } },
  );
  expect(accountResponse.status()).toBe(200);
  const originalIdentity: ShopperAuthResponse = await accountResponse.json();
  expect(originalIdentity.account.id).toBeTruthy();
  expect(originalIdentity.account.is_guest).toBe(false);
  expect(originalIdentity.account.username).toBe("fixture-shopper");
  await shopper.getByRole("button", { name: "Start something new", exact: true }).click();
  const composer = shopper.getByLabel("Shopping request", { exact: true });
  const submitted = "Find a travel mug for a weekend trip";
  const newerDraft = "Compare the small and large mugs before I choose";
  const chatRequests: { key: string | undefined; payload: string | null }[] = [];
  const unexpectedMutations: string[] = [];
  let orderReads = 0;
  let sessionChecks = 0;
  let releaseChatFailure!: () => void;
  const chatFailure = new Promise<void>((resolve) => { releaseChatFailure = resolve; });
  let releaseSessionCheck!: () => void;
  const sessionCheck = new Promise<void>((resolve) => { releaseSessionCheck = resolve; });
  const shopperApi = "**/api/runtime/v1/shopper/**";
  await shopper.route(shopperApi, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path.endsWith("/shopper/chat")) {
      chatRequests.push({
        key: request.headers()["idempotency-key"],
        payload: request.postData(),
      });
      // No chat attempt reaches the server or a model, including an unexpected replay.
      if (chatRequests.length === 1) {
        await chatFailure;
        return route.abort("failed");
      }
      return route.fulfill({
        status: 503,
        json: { error: { code: "UNAVAILABLE", message: "Synthetic chat interruption", request_id: "draft-fixture" } },
      });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      unexpectedMutations.push(`${request.method()} ${path}`);
      return route.abort("failed");
    }
    if (path.endsWith("/shopper/orders")) {
      orderReads += 1;
      return route.fulfill({
        status: 401,
        json: { error: { code: "UNAUTHORIZED", message: "Synthetic session expiry", request_id: "session-fixture" } },
      });
    }
    if (path.endsWith("/shopper/me")) {
      sessionChecks += 1;
      await sessionCheck;
    }
    return route.continue();
  });
  try {
    await composer.fill(submitted);
    await shopper.getByRole("button", { name: "Send request", exact: true }).click();
    await expect.poll(() => chatRequests.length).toBe(1);
    await expect(composer).toHaveValue("");
    await composer.fill(newerDraft);
    await expect(composer).toHaveValue(newerDraft);
    releaseChatFailure();
    const retryChat = shopper.getByRole("button", { name: "Retry same request", exact: true });
    await expect(retryChat).toBeEnabled();
    await expect(composer).toHaveValue(newerDraft);
    await expect(shopper.getByText(submitted, { exact: true })).toBeVisible();
    await expect(shopper.getByRole("button", { name: "Send request", exact: true })).toBeDisabled();
    expect(chatRequests).toHaveLength(1);
    expect(chatRequests[0].key).toBeTruthy();
    expect(JSON.parse(chatRequests[0].payload!)).toEqual({ content: submitted, conversation_id: null, expected_account_id: originalIdentity.account.id });

    await retryChat.click();
    await expect(shopper.getByText("Synthetic chat interruption", { exact: true })).toBeVisible();
    await expect(retryChat).toBeEnabled();
    await expect(composer).toHaveValue(newerDraft);
    expect(chatRequests).toHaveLength(2);
    expect(chatRequests[1]).toEqual(chatRequests[0]);
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await shopper.setViewportSize(viewport);
      const banner = await shopper.locator(".failed-request").boundingBox();
      const retryBox = await retryChat.boundingBox();
      const dismissBox = await shopper.getByRole("button", { name: "Dismiss failed request", exact: true }).boundingBox();
      expect(banner).not.toBeNull();
      for (const box of [retryBox, dismissBox]) {
        expect(box).not.toBeNull();
        expect(box!.height).toBeGreaterThanOrEqual(44);
        expect(box!.x).toBeGreaterThanOrEqual(banner!.x + 12);
        expect(box!.x + box!.width).toBeLessThanOrEqual(banner!.x + banner!.width - 12);
      }
    }
    await captures(shopper, "shopper-chat-retry");

    // A protected read expires the UI while the same registered account's cookie stays valid.
    await shopper.getByRole("button", { name: "Demo orders", exact: true }).click();
    const recoveryHeading = shopper.getByRole("heading", { name: "Your shopping session expired", exact: true });
    await expect(recoveryHeading).toBeVisible();
    await expect(recoveryHeading).toBeFocused();
    await expect(shopper.locator(".shop-shell")).toHaveCount(0);
    await expect(composer).toHaveCount(0);
    await expect(shopper.getByText(originalIdentity.account.display_name, { exact: true })).toHaveCount(0);
    await expect(shopper.getByText(submitted, { exact: true })).toHaveCount(0);
    await expect(shopper.getByText(newerDraft, { exact: true })).toHaveCount(0);
    await expect(shopper.getByRole("button", { name: /Open cart/ })).toHaveCount(0);
    await expect(shopper.getByLabel("Demo orders", { exact: true })).toHaveCount(0);
    // Next's development Strict Mode can issue both initial read effects.
    const expiredOrderReads = orderReads;
    expect(expiredOrderReads).toBeGreaterThanOrEqual(1);
    expect(expiredOrderReads).toBeLessThanOrEqual(2);
    await captures(shopper, "shopper-session-recovery", [
      shopper.getByLabel("Username", { exact: true }),
      shopper.getByLabel("Password", { exact: true }),
    ]);
    expect(orderReads).toBe(expiredOrderReads);
    expect(sessionChecks).toBe(0);
    expect(chatRequests).toHaveLength(2);
    expect(unexpectedMutations).toEqual([]);

    const verifiedSession = shopper.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/shopper/me" &&
      response.request().method() === "GET",
    );
    await shopper.getByRole("button", { name: "Check session", exact: true }).click();
    await expect.poll(() => sessionChecks).toBe(1);
    await expect(recoveryHeading).toBeVisible();
    await expect(shopper.locator(".shop-shell")).toHaveCount(0);
    await expect(composer).toHaveCount(0);
    releaseSessionCheck();
    const verifiedResponse = await verifiedSession;
    expect(verifiedResponse.status()).toBe(200);
    expect(verifiedResponse.request().headers()["x-store-slug"]).toBe(slug);
    const verifiedIdentity: ShopperAuthResponse = await verifiedResponse.json();
    expect(verifiedIdentity.account.id).toBe(originalIdentity.account.id);
    expect(verifiedIdentity.account.is_guest).toBe(false);
    await expect(recoveryHeading).toHaveCount(0);
    await expect(shopper.getByRole("button", { name: "Account", exact: true })).toBeVisible();
    await expect(shopper.locator(".shop-account")).toContainText(originalIdentity.account.display_name);
    await expect(composer).toHaveValue(newerDraft);
    await expect(shopper.getByText(submitted, { exact: true })).toBeVisible();
    await expect(retryChat).toBeEnabled();
    await expect(shopper.getByRole("button", { name: "Send request", exact: true })).toBeDisabled();
    await expect(shopper.getByRole("button", { name: "Open cart with 1 items", exact: true })).toBeVisible();
    const recoveredCart = await currentCart();
    expect(recoveredCart.id).toBe(restoredCart.id);
    expect(recoveredCart.version).toBe(restoredCart.version);
    expect(recoveredCart.lines).toEqual(restoredCart.lines);
    expect(recoveredCart.total).toEqual(restoredCart.total);
    expect(sessionChecks).toBe(1);
    expect(orderReads).toBe(expiredOrderReads);
    expect(chatRequests).toHaveLength(2);
    expect(unexpectedMutations).toEqual([]);
  } finally {
    releaseChatFailure();
    releaseSessionCheck();
    await shopper.unroute(shopperApi);
  }
  await verifyShopperRecoveryCode(shopper, testInfo, {
    slug: slug!, identity: originalIdentity, code: currentRecoveryCode,
    draft: newerDraft, failedMessage: submitted,
  });
  await verifyGuestPanelRecovery(browser, sharedUrl.href, slug!, testInfo);
  // Keep four real A-labelled views mounted while another tab changes the cookie.
  const staleViews: { page: Page; action: string; path: string; method: string }[] = [];
  for (const action of ["Confirm deletion", "Sign out everywhere", "Remember shopping preferences", "Add to cart"]) {
    const stale = await guestContext.newPage();
    await stale.goto(sharedUrl.href);
    await expect(stale.locator(".shop-account")).toContainText(originalIdentity.account.display_name);
    if (action.startsWith("Add ")) {
      const product = stale.getByRole("article").filter({ has: stale.getByRole("heading", { name: "Soft cotton throw", exact: true }) });
      const selection = stale.waitForResponse((response) =>
        new URL(response.url()).pathname === "/api/runtime/v1/shopper/product-selections",
      );
      await product.getByRole("button", { name: "View product", exact: true }).click();
      expect((await selection).status()).toBe(204);
      await stale.getByLabel("Choose a variant").selectOption("default");
      await expect(stale.getByRole("button", { name: action, exact: true })).toBeEnabled();
    } else {
      await stale.getByRole("button", { name: "Account", exact: true }).click();
      await expect(stale.getByText(`Signed in as ${originalIdentity.account.display_name}`, { exact: true })).toBeVisible();
      if (action === "Confirm deletion") {
        await stale.getByRole("button", { name: "Delete shopping data", exact: true }).click();
      }
    }
    // Hold the periodic read out of this race so the explicit action, rather
    // than a timer, is what first discovers the changed shared cookie.
    await stale.route("**/v1/shopper/discovery", (route) => route.abort("failed"));
    const operation = action === "Confirm deletion" ? ["shopping-data", "DELETE"]
      : action === "Sign out everywhere" ? ["auth/sessions", "DELETE"]
      : action === "Remember shopping preferences" ? ["preferences", "PATCH"]
      : ["cart/items", "POST"];
    staleViews.push({ page: stale, action, path: operation[0], method: operation[1] });
  }
  await shopper.route("**/v1/shopper/discovery", (route) => route.abort("failed"));
  // Change the real shared cookie from a second tab, without notifying the first UI.
  const otherTab = await guestContext.newPage();
  try {
    const shopperOrigin = new URL(shopper.url()).origin;
    const headers = { "x-store-slug": slug!, origin: shopperOrigin };
    const endpoint = (path: string) => new URL(`/api/runtime/v1/shopper/${path}`, shopperOrigin).href;
    expect((await otherTab.request.post(endpoint("auth/logout"), { headers })).status()).toBe(204);
    const replacement = await otherTab.request.post(endpoint("auth/guest"), { headers });
    expect(replacement.status()).toBe(200);
    const otherIdentity: ShopperAuthResponse = await replacement.json();
    expect(otherIdentity.account.id).not.toBe(originalIdentity.account.id);
    expect(otherIdentity.account.is_guest).toBe(true);
    const boundB = { ...headers, "x-shopper-account-id": otherIdentity.account.id };
    const seededCart = await otherTab.request.post(endpoint("cart/items"), {
      headers: { ...boundB, "idempotency-key": "account-switch-b-cart" },
      data: { product_id: "throw", quantity: 2 },
    });
    expect(seededCart.status()).toBe(200);
    const bCart = await (await otherTab.request.get(endpoint("cart"), { headers: boundB })).json();
    expect((await otherTab.request.patch(endpoint("preferences"), {
      headers: { ...boundB, "idempotency-key": "account-switch-b-memory" },
      data: { enabled: false },
    })).status()).toBe(200);
    const bSessions = await (await otherTab.request.get(endpoint("auth/sessions"), { headers: boundB })).json();
    for (const stale of staleViews) {
      await expect(stale.page.locator(".shop-account")).toContainText(originalIdentity.account.display_name);
      const rejection = stale.page.waitForResponse((response) =>
        new URL(response.url()).pathname === `/api/runtime/v1/shopper/${stale.path}` &&
        response.request().method() === stale.method,
      );
      if (stale.action === "Remember shopping preferences") {
        await expect(stale.page.getByLabel(stale.action)).not.toBeChecked();
        await stale.page.getByLabel(stale.action).click();
      } else {
        await stale.page.getByRole("button", { name: stale.action, exact: true }).click();
      }
      const response = await rejection;
      expect(response.request().headers()["x-shopper-account-id"]).toBe(originalIdentity.account.id);
      expect(response.status()).toBe(401);
      expect(response.headers()["set-cookie"]).toBeUndefined();
      await expect(stale.page.getByRole("heading", { name: "Your shopping session expired", exact: true })).toBeVisible();
      await expect(stale.page.locator(".shop-shell")).toHaveCount(0);
      await expect(stale.page.getByText("Shopping data deleted.", { exact: false })).toHaveCount(0);
      if (stale.action === "Confirm deletion") await captures(stale.page, "stale-account-deletion-blocked");
    }
    const survivingB = await otherTab.request.get(endpoint("me"), { headers: boundB });
    expect(survivingB.status()).toBe(200);
    expect((await survivingB.json()).account.memory_enabled).toBe(false);
    expect(await (await otherTab.request.get(endpoint("cart"), { headers: boundB })).json()).toEqual(bCart);
    expect(await (await otherTab.request.get(endpoint("auth/sessions"), { headers: boundB })).json()).toEqual(bSessions);
    await expect(shopper.locator(".shop-account")).toContainText(originalIdentity.account.display_name);
    const rejectedRetry = shopper.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/shopper/chat",
    );
    await shopper.getByRole("button", { name: "Retry same request", exact: true }).click();
    const rejected = await rejectedRetry;
    expect(rejected.status()).toBe(401);
    expect(rejected.request().postData()).toBe(chatRequests[0].payload);
    expect(rejected.request().headers()["idempotency-key"]).toBe(chatRequests[0].key);
    await expect(shopper.getByRole("heading", { name: "Your shopping session expired" })).toBeVisible();
    await expect(shopper.getByText(submitted, { exact: true })).toHaveCount(0);
    const otherHistory = await otherTab.request.get(endpoint("conversations"), { headers });
    expect(otherHistory.status()).toBe(200);
    expect((await otherHistory.json()).items).toEqual([]);
    await shopper.getByRole("button", { name: "Check session", exact: true }).click();
    await expect(shopper.getByRole("button", { name: "Save your progress", exact: true })).toBeVisible();
    await expect(composer).toHaveValue("");
    await expect(shopper.getByText(submitted, { exact: true })).toHaveCount(0);
    await expect(shopper.getByRole("button", { name: "Retry same request", exact: true })).toHaveCount(0);

    // A real expired identity check is delayed while another tab creates C.
    // Fresh-start recovery must not mistake C's reused session for a new visit.
    await shopper.getByRole("button", { name: "Browse catalog", exact: true }).click();
    await expect(shopper.getByRole("heading", { name: "Soft cotton throw", exact: true })).toBeVisible();
    expect((await otherTab.request.post(endpoint("auth/logout"), { headers: boundB })).status()).toBe(204);
    await shopper.getByRole("button", { name: "Refresh catalog", exact: true }).click();
    const recoveryHeading = shopper.getByRole("heading", { name: "Your shopping session expired", exact: true });
    await expect(recoveryHeading).toBeVisible();
    let replacementGuestId: string | undefined;
    let guestPreflightChecks = 0;
    let unexpectedLogout = 0;
    shopper.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/runtime/v1/shopper/auth/logout") unexpectedLogout += 1;
    });
    await shopper.route("**/v1/shopper/me", async (route) => {
      guestPreflightChecks += 1;
      const expired = await route.fetch({ maxRetries: 0 });
      expect(expired.status()).toBe(401);
      const created = await otherTab.request.post(endpoint("auth/guest"), { headers });
      expect(created.status()).toBe(200);
      const value = await created.json();
      expect(value.created).toBe(true);
      replacementGuestId = value.account.id;
      expect(replacementGuestId).not.toBe(otherIdentity.account.id);
      expect((await otherTab.request.post(endpoint("cart/items"), {
        headers: { ...headers, "x-shopper-account-id": replacementGuestId!, "idempotency-key": "fresh-visit-race-c" },
        data: { product_id: "throw", quantity: 2 },
      })).status()).toBe(200);
      await route.fulfill({ response: expired });
    });
    try {
      const refusedReuse = shopper.waitForResponse((response) =>
        new URL(response.url()).pathname === "/api/runtime/v1/shopper/auth/guest" &&
        response.request().method() === "POST",
      );
      await shopper.getByRole("button", { name: "Start a new guest visit", exact: true }).click();
      const reused = await refusedReuse;
      expect(reused.status()).toBe(200);
      expect((await reused.json()).created).toBe(false);
      expect(reused.headers()["set-cookie"]).toBeUndefined();
      await expect(shopper.getByRole("alert").filter({ hasText: "We couldn't start a new guest visit" })).toBeVisible();
      await expect(shopper.getByRole("alert").filter({ hasText: "We couldn't start a new guest visit" })).toContainText("Choose Check session to continue a visit opened elsewhere.");
      await expect(recoveryHeading).toBeVisible();
      await expect(shopper.locator(".shop-shell")).toHaveCount(0);
      expect(guestPreflightChecks).toBe(1);
      expect(unexpectedLogout).toBe(0);
      await captures(shopper, "fresh-guest-reuse-blocked");
    } finally {
      await shopper.unroute("**/v1/shopper/me");
    }
    const preservedGuest = await otherTab.request.get(endpoint("me"), { headers });
    expect(preservedGuest.status()).toBe(200);
    expect((await preservedGuest.json()).account.id).toBe(replacementGuestId);
    await shopper.getByRole("button", { name: "Check session", exact: true }).click();
    await expect(recoveryHeading).toHaveCount(0);
    await expect(shopper.getByRole("button", { name: "Open cart with 2 items", exact: true })).toBeVisible();
    expect(unexpectedLogout).toBe(0);
  } finally {
    await shopper.unroute("**/v1/shopper/discovery");
    for (const stale of staleViews) await stale.page.close();
    await otherTab.close();
  }
  await guestContext.close();
  // The local fixture issues B's real server session in this disposable database.
  // Replacing the cookie simulates a second-tab login; it is not a live OIDC test.
  const python = process.env.OPEN_COMMERCE_E2E_PYTHON;
  expect(python).toBeTruthy();
  const secondFixture = await promisify(execFile)(
    python!, ["-m", "tests.integration.merchant_browser_fixture"],
    { cwd: resolve(process.cwd(), "../.."), timeout: 30_000, maxBuffer: 65536 },
  );
  const secondOwner: { identity: OwnerAuthResponse; token: string } = JSON.parse(secondFixture.stdout);
  const context = page.context();
  const originalCookie = (await context.cookies(ownerOrigin))
    .find((cookie) => cookie.name === "open_commerce_merchant_session");
  expect(originalCookie).toBeTruthy();
  const originalOwner: OwnerAuthResponse = await (await page.request.get(
    `${ownerOrigin}/api/runtime/v1/merchant/auth/me`,
  )).json();
  const boundSecond = {
    "x-merchant-owner-id": secondOwner.identity.user_id,
    "x-merchant-store-id": secondOwner.identity.store.id,
    origin: ownerOrigin,
  };
  async function chooseOwner(second: boolean) {
    await context.addCookies([{
      ...originalCookie!, value: second ? secondOwner.token : originalCookie!.value,
    }]);
  }
  await chooseOwner(true);
  const storeEndpoint = `${ownerOrigin}/api/runtime/v1/merchant/store`;
  function withoutMonitorClock(value: StoreReadiness): StoreReadiness {
    const copy = structuredClone(value);
    // The real worker remains running; its observational schedule is not an owner mutation.
    if (copy.store.readiness) {
      delete copy.store.readiness.monitor_checked_at;
      delete copy.store.readiness.monitor_next_check;
    }
    return copy;
  }
  const secondBefore = withoutMonitorClock(await (await page.request.get(storeEndpoint, { headers: boundSecond })).json());
  const bootstrapSecond = await page.request.post(`${ownerOrigin}/api/runtime/v1/manager/workspace/bootstrap`, {
    headers: { ...boundSecond, "idempotency-key": "second-owner-workspace" },
  });
  expect(bootstrapSecond.status()).toBe(200);
  const workspaceEndpoint = `${ownerOrigin}/api/runtime/v1/manager/workspace`;
  const secondWorkspaceBefore = await (await page.request.get(workspaceEndpoint, { headers: boundSecond })).json();
  let staleCommands = 0;
  const staleOperations = [
    { name: "reset", method: "POST", path: "/v1/manager/workspace/reset" },
    { name: "profile", method: "PATCH", path: "/v1/merchant/store" },
    { name: "sharing", method: "POST", path: "/v1/merchant/store/sharing" },
    { name: "upload", method: "POST", path: "/v1/merchant/imports/upload" },
    { name: "catalog", method: "GET", path: "/v1/manager/catalog" },
    { name: "logout", method: "POST", path: "/v1/merchant/auth/logout" },
  ];
  try {
    for (const operation of staleOperations) {
      await chooseOwner(false);
      const stale = await context.newPage();
      stale.setDefaultTimeout(15_000);
      let releaseReads = () => {};
      try {
        await stale.goto(operation.name === "catalog" ? "/manager/catalog" : "/manager");
        let trigger: () => Promise<void>;
        if (operation.name === "reset") {
          await stale.getByRole("button", { name: "Workspace settings", exact: true }).click();
          await expect(stale.getByText("This local demo does not use a separate manager login.", { exact: true })).toHaveCount(0);
          await stale.getByRole("button", { name: "Reset and clean up", exact: true }).click();
          trigger = () => stale.getByRole("button", { name: "Reset workspace", exact: true }).click();
        } else if (operation.name === "catalog") {
          await expect(stale.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
          trigger = () => stale.getByRole("button", { name: "Refresh catalog", exact: true }).click();
        } else if (operation.name === "logout") {
          await expect(stale.getByRole("button", { name: "Workspace settings", exact: true })).toBeVisible();
          trigger = () => stale.getByRole("button", { name: "Sign out", exact: true }).click();
        } else {
          await stale.getByRole("button", { name: "Store setup & sharing", exact: true }).click();
          if (operation.name === "sharing") {
            await stale.getByRole("button", { name: "3 Ready to share", exact: true }).click();
            await expect(stale.getByRole("button", { name: "Disable sharing", exact: true })).toBeVisible();
            trigger = () => stale.getByRole("button", { name: "Disable sharing", exact: true }).click();
          } else {
            await stale.getByRole("button", { name: "1 Products", exact: true }).click();
            await expect(stale.getByLabel("Store name", { exact: true })).toBeVisible();
            if (operation.name === "profile") {
              await stale.getByLabel("Store name", { exact: true }).fill("Must not rename the second store");
              trigger = () => stale.getByRole("button", { name: "Save details", exact: false }).click();
            } else {
              trigger = () => stale.getByLabel("Upload catalog CSV").setInputFiles({
                name: "stale-owner.csv", mimeType: "text/csv",
                buffer: Buffer.from("product_id,title,price,currency\nwrong,Must not import,1,USD\n"),
              });
            }
          }
        }
        // Hold only background GET delivery so polling cannot close the old view
        // before its explicitly tested action. Requests still reach the real API.
        const readsMayContinue = new Promise<void>((resolve) => { releaseReads = resolve; });
        await stale.route("**/api/runtime/v1/**", async (route) => {
          if (route.request().method() === "GET") await readsMayContinue;
          await route.continue();
        });
        const rejection = stale.waitForResponse((response) =>
          new URL(response.url()).pathname === `/api/runtime${operation.path}` &&
          response.request().method() === operation.method,
          { timeout: 15_000 },
        );
        stale.on("request", (request) => {
          if (new URL(request.url()).pathname === `/api/runtime${operation.path}` &&
              request.method() === operation.method && operation.method !== "GET") staleCommands += 1;
        });
        await chooseOwner(true);
        await trigger();
        if (operation.method === "GET") releaseReads();
        const rejected = await rejection;
        releaseReads();
        expect(rejected.status()).toBe(401);
        expect(rejected.request().headers()["x-merchant-owner-id"]).toBe(originalOwner.user_id);
        expect(rejected.request().headers()["x-merchant-store-id"]).toBe(originalOwner.store.id);
        expect(rejected.headers()["set-cookie"]).toBeUndefined();
        const expired = stale.getByRole("heading", { name: "Your store session expired", exact: true });
        await expect(expired).toBeVisible();
        await expect(expired).toBeFocused();
        await expect(stale.getByRole("dialog")).toHaveCount(0);
        await expect(stale.getByRole("button", { name: "Workspace settings", exact: true })).toHaveCount(0);
        await expect(stale.getByRole("heading", { name: "Travel mug", exact: true })).toHaveCount(0);
        if (operation.name === "reset") await captures(stale, "merchant-stale-reset-blocked");
        if (operation.name === "profile") {
          const countBeforeRecovery = staleCommands;
          await stale.getByRole("button", { name: "Check session", exact: true }).click();
          await expect(expired).toHaveCount(0);
          await expect(stale.getByLabel("Store name", { exact: true })).toHaveValue("Second Fixture Store");
          expect(staleCommands).toBe(countBeforeRecovery);
          await captures(stale, "merchant-explicit-session-recovery");
        }
      } finally {
        releaseReads();
        await stale.unrouteAll({ behavior: "wait" });
        await stale.close();
      }
    }
    expect(staleCommands).toBe(staleOperations.filter((operation) => operation.method !== "GET").length);
    const surviving = await page.request.get(`${ownerOrigin}/api/runtime/v1/merchant/auth/me`, { headers: boundSecond });
    expect(surviving.status()).toBe(200);
    expect((await surviving.json()).user_id).toBe(secondOwner.identity.user_id);
    expect(withoutMonitorClock(await (await page.request.get(storeEndpoint, { headers: boundSecond })).json())).toEqual(secondBefore);
    expect(await (await page.request.get(workspaceEndpoint, { headers: boundSecond })).json()).toEqual(secondWorkspaceBefore);
  } finally {
    await chooseOwner(false);
  }
  await verifyReviewedImportConfirmation(page, testInfo);
  await verifyCatalogContinuity(page, testInfo, originalOwner);
  await verifyStoreIdentity(page, testInfo, originalOwner);
  await verifyOwnerKeyboard(page, testInfo);
  await verifyChannelSaveRecovery(page, originalOwner);
  await verifyWorkspaceResetRecovery(page, testInfo, originalOwner);
  await testInfo.attach("measured-usability.json", {
    body: JSON.stringify({
      previewMs,
      firstResultMs,
      includesColdPageCompilation: true,
      model: "deterministic fixture",
    }),
    contentType: "application/json",
  });
  console.log(
    JSON.stringify({
      previewMs,
      firstResultMs,
      model: "deterministic fixture",
    }),
  );
  expect(previewMs).toBeLessThan(300_000);
  expect(firstResultMs).toBeLessThan(60_000);
});

test("legacy sign-in keeps sample photo credits visible", async ({ page }, testInfo) => {
  const shopper = process.env.SHOPPER_PLAYWRIGHT_BASE_URL;
  test.skip(!shopper, "Running isolated shopper client required");
  await page.route("**/api/runtime/**", (route) => route.fulfill({
    status: 401,
    json: { error: { code: "UNAUTHORIZED", message: "Sign in", request_id: "artwork-fixture" } },
  }));
  await page.goto(shopper!);
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  await captureArtwork(page, testInfo, "shopper-sign-in");
});
