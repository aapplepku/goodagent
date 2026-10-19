import { expect, type Locator, type Page, type TestInfo } from "@playwright/test";
import type { ImportReview, ManagerThreadDetail, ManagerWorkspaceResponse, ManagerWorkspaceResetResponse, OwnerAuthResponse, StoreReadiness } from "@open-commerce/sdk-typescript";
import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { promisify } from "node:util";

export const continuityCatalog =
  "product_id,title,price,currency,inventory_quantity,variant_id,updated_at\n" +
  "mug,Travel mug,15,USD,50,small,2026-10-01T00:00:00Z\n" +
  "mug,Travel mug,19,USD,50,large,2026-10-01T00:00:00Z\n" +
  "throw,Soft cotton throw,35,USD,30,default,2026-10-01T00:00:00Z\n";

async function capture(page: Page, info: TestInfo, prefix: string) {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${prefix}-${viewport.width}x${viewport.height}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

export async function verifyReviewedImportConfirmation(page: Page, info: TestInfo) {
  async function openProducts(tab: Page) {
    await tab.goto("/manager");
    await tab.getByRole("button", { name: "Store setup & sharing", exact: true }).click();
    await tab.getByRole("button", { name: "1 Products", exact: true }).click();
  }
  async function currencyControls(tab: Page) {
    await expect(tab.getByRole("heading", { name: "two-tab-review.csv", exact: true })).toBeVisible();
    await expect(tab.getByRole("button", { name: "Cancel import", exact: true })).toBeEnabled();
    if (!await tab.getByRole("combobox", { name: "Price currency", exact: true }).isVisible())
      await tab.getByText("Edit field mapping and currency", { exact: true }).click();
    await expect(tab.getByRole("combobox", { name: "Price currency", exact: true })).toBeVisible();
  }
  await openProducts(page);
  const uploadResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/runtime/v1/merchant/imports/upload" && response.request().method() === "POST",
  );
  await page.getByLabel("Upload catalog CSV").setInputFiles({
    name: "two-tab-review.csv", mimeType: "text/csv",
    buffer: Buffer.from("product_id,title,price,cost,updated_at\none,Review fixture,100,1,2026-10-01T00:00:00Z\n"),
  });
  const uploaded = await uploadResponse;
  expect(uploaded.status()).toBe(201);
  const upload: ImportReview = await uploaded.json();
  const mappingPath = `/api/runtime/v1/merchant/imports/${upload.id}/mapping`;
  const confirmPath = `/api/runtime/v1/merchant/imports/${upload.id}/confirm`;
  await currencyControls(page);
  await page.getByRole("combobox", { name: "Price currency", exact: true }).selectOption("USD");
  const reviewedA = page.waitForResponse((response) => new URL(response.url()).pathname === mappingPath);
  await page.getByRole("button", { name: "Validate mapping", exact: true }).click();
  expect((await reviewedA).status()).toBe(200);
  await expect(page.getByRole("cell", { name: "USD 100.00", exact: true })).toBeVisible();
  const otherTab = await page.context().newPage();
  const confirmations: import("@playwright/test").Request[] = [];
  const observe = (request: import("@playwright/test").Request) => {
    if (new URL(request.url()).pathname === confirmPath && request.method() === "POST") confirmations.push(request);
  };
  page.on("request", observe);
  try {
    await openProducts(otherTab);
    await currencyControls(otherTab);
    await otherTab.getByRole("combobox", { name: "price", exact: true }).selectOption("cost");
    await otherTab.getByRole("combobox", { name: "Price currency", exact: true }).selectOption("EUR");
    const reviewedB = otherTab.waitForResponse((response) => new URL(response.url()).pathname === mappingPath);
    await otherTab.getByRole("button", { name: "Validate mapping", exact: true }).click();
    expect((await reviewedB).status()).toBe(200);
    await expect(otherTab.getByRole("cell", { name: "EUR 1.00", exact: true })).toBeVisible();
    await page.bringToFront();
    await expect(page.getByRole("cell", { name: "USD 100.00", exact: true })).toBeVisible();
    const stale = page.waitForResponse((response) => new URL(response.url()).pathname === confirmPath);
    await page.getByRole("button", { name: "Confirm products", exact: true }).click();
    expect((await stale).status()).toBe(409);
    await expect(page.getByRole("button", { name: "Review latest mapping", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm products", exact: true })).toBeDisabled();
    const recoveryBox = await page.getByRole("button", { name: "Review latest mapping", exact: true }).boundingBox();
    const warningBox = await page.getByRole("alert").filter({ hasText: "import review changed" }).boundingBox();
    expect(recoveryBox).not.toBeNull();
    expect(warningBox).not.toBeNull();
    expect(Math.abs(recoveryBox!.x - warningBox!.x)).toBeLessThanOrEqual(1);
    await capture(page, info, "stale-import-review");
    expect(confirmations).toHaveLength(1);
    await page.getByRole("button", { name: "Review latest mapping", exact: true }).click();
    await expect(page.getByRole("cell", { name: "EUR 1.00", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm products", exact: true })).toBeEnabled();
    expect(confirmations).toHaveLength(1);
    await capture(page, info, "refreshed-import-review");
    const fresh = page.waitForResponse((response) => new URL(response.url()).pathname === confirmPath);
    await page.getByRole("button", { name: "Confirm products", exact: true }).click();
    const confirmed = await fresh;
    expect(confirmed.status()).toBe(200);
    expect((await confirmed.json()).currency).toBe("EUR");
    expect(confirmations).toHaveLength(2);
    expect(confirmations[0].postDataJSON().expected_review_fingerprint).not.toBe(
      confirmations[1].postDataJSON().expected_review_fingerprint,
    );
    expect(confirmations[0].headers()["idempotency-key"]).not.toBe(confirmations[1].headers()["idempotency-key"]);
    await expect(page.getByRole("button", { name: "Open shopper preview", exact: true })).toBeEnabled({ timeout: 90_000 });
  } finally {
    page.off("request", observe);
    if (!otherTab.isClosed()) await otherTab.close();
  }
}

export async function verifyCatalogContinuity(page: Page, info: TestInfo, owner: OwnerAuthResponse) {
  const origin = new URL(page.url()).origin;
  const endpoint = (path: string) => `${origin}/api/runtime/v1/merchant/${path}`;
  const headers = { origin, "x-merchant-owner-id": owner.user_id, "x-merchant-store-id": owner.store.id };
  async function readiness(): Promise<StoreReadiness> {
    const response = await page.request.get(endpoint("store"), { headers });
    expect(response.status()).toBe(200);
    return response.json();
  }
  const original = await readiness();
  const catalogA = original.store.published_catalog_id;
  expect(catalogA).toBeTruthy();
  expect(original.store.sharing_enabled).toBe(true);
  await page.goto("/manager");
  await page.getByRole("button", { name: "Store setup & sharing", exact: true }).click();

  async function upload(filename: string, csv: string, confirm = true): Promise<ImportReview> {
    await page.getByRole("button", { name: "1 Products", exact: true }).click();
    const uploaded = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/merchant/imports/upload" && response.request().method() === "POST",
    );
    await page.getByLabel("Upload catalog CSV").setInputFiles({ name: filename, mimeType: "text/csv", buffer: Buffer.from(csv) });
    const response = await uploaded;
    expect(response.status()).toBe(201);
    const review: ImportReview = await response.json();
    await expect(page.getByRole("button", { name: "Confirm products", exact: true })).toBeEnabled();
    if (!confirm) return review;
    const confirmed = page.waitForResponse((result) =>
      new URL(result.url()).pathname === `/api/runtime/v1/merchant/imports/${review.id}/confirm` && result.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Confirm products", exact: true }).click();
    expect((await confirmed).status()).toBe(200);
    await expect(page.getByRole("button", { name: "Open shopper preview", exact: true })).toBeEnabled({ timeout: 90_000 });
    const current = await page.request.get(endpoint(`imports/${review.id}`), { headers });
    expect(current.status()).toBe(200);
    return current.json();
  }

  async function previewAndSearch(catalog: string) {
    const response = page.waitForResponse((result) =>
      new URL(result.url()).pathname === "/api/runtime/v1/merchant/store/preview" && result.request().method() === "POST",
    );
    const opened = page.context().waitForEvent("page");
    await page.getByRole("button", { name: "Open shopper preview", exact: true }).click();
    const grant = await response;
    expect(grant.status()).toBe(200);
    expect(grant.request().postDataJSON()).toEqual({ catalog_id: catalog });
    const shopper = await opened;
    try {
      await expect(shopper.getByRole("heading", { name: "What are we shopping for?", exact: true })).toBeVisible();
      expect((await readiness()).checklist.search_tested).toBe(false);
      await shopper.getByRole("button", { name: "Browse catalog", exact: true }).click();
      await expect(shopper.getByRole("heading", { name: "Browse the store", exact: true })).toBeVisible();
      await shopper.locator("details").first().getByText("Details", { exact: true }).click();
      await shopper.getByRole("button", { name: "Ask the assistant", exact: true }).first().click();
      await expect(shopper.locator(".product-card").first()).toBeVisible({ timeout: 30_000 });
    } finally {
      await shopper.close();
    }
  }

  const replacementCsv = continuityCatalog.replace("Soft cotton throw,35", "Replacement cotton throw,45");
  const b = await upload("replacement-b.csv", replacementCsv);
  expect(b.catalog_id).toBeTruthy();
  expect(b.catalog_id).not.toBe(catalogA);
  await previewAndSearch(b.catalog_id!);
  const c = await upload("restore-a.csv", continuityCatalog);
  expect(c.catalog_id).toBe(catalogA);
  const restored = await readiness();
  expect(restored.latest_import_id).toBe(c.id);
  expect(restored.indexing.catalog_id).toBe(catalogA);
  expect(restored.checklist.search_tested).toBe(false);
  await expect(page.getByText("restore-a.csv", { exact: true })).toBeVisible();
  await capture(page, info, "reused-catalog-preview");
  await previewAndSearch(catalogA!);
  await page.getByRole("button", { name: "Review sharing", exact: true }).click();
  await expect(page.getByRole("button", { name: "Store link enabled", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Disable sharing", exact: true }).click();
  await expect(page.getByRole("button", { name: "Enable store link", exact: true })).toBeVisible();
  await page.getByLabel("I reviewed the products and image issues.").check();
  await page.getByLabel("Checkout is a demo. No real payments are taken.").check();
  const published = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/runtime/v1/merchant/store/sharing" && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Enable store link", exact: true }).click();
  const publication = await published;
  expect(publication.status()).toBe(200);
  expect(publication.request().postDataJSON()).toMatchObject({ catalog_id: catalogA, enabled: true });

  const retryCandidate = await upload("retry-b.csv", replacementCsv);
  expect(retryCandidate.catalog_id).toBe(b.catalog_id);
  const python = process.env.OPEN_COMMERCE_E2E_PYTHON;
  expect(python).toBeTruthy();
  const injected = await promisify(execFile)(python!, [
    "-m", "tests.integration.catalog_browser_fixture", "--tenant", owner.store.id, "--catalog", b.catalog_id!,
  ], { cwd: resolve(process.cwd(), "../.."), timeout: 30_000, maxBuffer: 65536 });
  expect(JSON.parse(injected.stdout)).toEqual({ injected: "synthetic_browser_retry_fixture" });
  const cancelled = await upload("cancel-me.csv", continuityCatalog, false);
  const pending = await readiness();
  expect(pending.latest_import_id).toBe(cancelled.id);
  expect(pending.indexing.catalog_id).toBeNull();
  expect(pending.store.published_catalog_id).toBe(catalogA);
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("cancel-me.csv");
    await dialog.accept();
  });
  const closed = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/runtime/v1/merchant/imports/${cancelled.id}/cancel`,
  );
  await page.getByRole("button", { name: "Cancel import", exact: true }).click();
  expect((await closed).status()).toBe(200);
  await page.reload();
  await page.getByRole("button", { name: "Store setup & sharing", exact: true }).click();
  await page.getByRole("button", { name: "2 Preview", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry indexing", exact: true })).toBeVisible();
  await expect(page.getByText("retry-b.csv", { exact: true })).toBeVisible();
  await capture(page, info, "cancelled-upload-retry-recovery");
  const retried = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith("/retry") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Retry indexing", exact: true }).click();
  const retryResponse = await retried;
  expect(new URL(retryResponse.url()).pathname).toBe(`/api/runtime/v1/merchant/imports/${retryCandidate.id}/retry`);
  expect(retryResponse.status()).toBe(200);
  await expect(page.getByRole("button", { name: "Open shopper preview", exact: true })).toBeEnabled({ timeout: 90_000 });
  const final = await readiness();
  expect(final.latest_import_id).toBe(retryCandidate.id);
  expect(final.indexing.catalog_id).toBe(b.catalog_id);
  expect(final.indexing.status).toBe("ready");
  expect(final.store.published_catalog_id).toBe(catalogA);
  expect(final.store.sharing_enabled).toBe(true);
  expect((await (await page.request.get(endpoint(`imports/${cancelled.id}`), { headers })).json()).status).toBe("cancelled");
}

export async function verifyStoreIdentity(page: Page, info: TestInfo, owner: OwnerAuthResponse) {
  await page.goto("/manager");
  const identity = page.getByRole("group", { name: "Current store", exact: true });
  await expect(identity).toContainText(owner.store.name);
  await expect(identity).toContainText(`/s/${owner.store.slug}`);
  async function details() {
    await page.getByRole("button", { name: "Store setup & sharing", exact: true }).click();
    await page.getByRole("button", { name: "1 Products", exact: true }).click();
    const summary = page.getByText("Store details and catalog source", { exact: true });
    await expect(summary).toBeVisible();
    if (!await page.getByLabel("Store name", { exact: true }).isVisible())
      await summary.click();
    await expect(page.getByLabel("Store name", { exact: true })).toBeVisible();
  }
  await details();
  await page.getByLabel("Store name", { exact: true }).fill("Unsaved title is not the store identity");
  await page.getByRole("button", { name: "Open workspace", exact: true }).click();
  await expect(identity).toContainText(owner.store.name);
  await expect(identity).not.toContainText("Unsaved title");
  await details();
  const longName = "Northstar".repeat(15).slice(0, 120);
  await page.getByLabel("Store name", { exact: true }).fill(longName);
  const saved = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/runtime/v1/merchant/store" && response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save details", exact: true }).click();
  expect((await saved).status()).toBe(200);
  await page.getByRole("button", { name: "Open workspace", exact: true }).click();
  await expect(identity).toContainText(longName);
  await expect(identity).toContainText(`/s/${owner.store.slug}`);
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(identity).toBeVisible();
    const label = await identity.boundingBox();
    const settings = await page.getByRole("button", { name: "Workspace settings", exact: true }).boundingBox();
    expect(label).toBeTruthy();
    expect(settings).toBeTruthy();
    expect(settings!.y).toBeGreaterThanOrEqual(label!.y + label!.height);
    for (const name of ["Store setup & sharing", "Sign out"]) {
      const button = page.getByRole("button", { name, exact: true });
      const box = await button.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      expect(box?.width).toBeGreaterThanOrEqual(44);
      await button.focus();
      await expect(button).toBeFocused();
    }
  }
  await capture(page, info, "verified-store-workspace");
  await page.getByRole("button", { name: "Workspace settings", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "Workspace settings", exact: true });
  await expect(settings.getByRole("group", { name: "Store target", exact: true })).toContainText(longName);
  await settings.getByRole("button", { name: "Reset and clean up", exact: true }).click();
  const reset = page.getByRole("dialog", { name: "Reset manager workspace?", exact: true });
  await expect(reset.getByRole("group", { name: "Store target", exact: true })).toContainText(`/s/${owner.store.slug}`);
  await expect(reset).toContainText("Store workspace cleanup");
  await capture(page, info, "verified-store-reset-target");
  await reset.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: /^#/ }).first().click();
  await page.getByRole("button", { name: "Agent actions", exact: true }).click();
  await page.getByRole("menuitem", { name: "Clear agent history", exact: true }).click();
  const history = page.getByRole("dialog", { name: /^Clear .+ history\?$/ });
  await expect(history.getByRole("group", { name: "Store target", exact: true })).toContainText(longName);
  await expect(history.getByRole("group", { name: "Store target", exact: true })).toContainText(`/s/${owner.store.slug}`);
  await capture(page, info, "verified-store-history-target");
  await history.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.goto("/manager/catalog");
  await expect(identity).toContainText(longName);
  await expect(identity).toContainText(`/s/${owner.store.slug}`);
  await expect(page.getByRole("heading", { name: "Travel mug", exact: true })).toBeVisible();
  await capture(page, info, "verified-store-catalog");
}

export async function verifyOwnerKeyboard(page: Page, info: TestInfo) {
  await page.goto("/manager");
  const settingsButton = page.getByRole("button", { name: "Workspace settings", exact: true });
  await expect(settingsButton).toBeVisible();
  const commands: string[] = [];
  const track = (request: import("@playwright/test").Request) => {
    if (request.url().includes("/api/runtime/") && !["GET", "HEAD", "OPTIONS"].includes(request.method()))
      commands.push(`${request.method()} ${new URL(request.url()).pathname}`);
  };
  page.on("request", track);
  async function containsFocus(dialog: Locator) {
    await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement)), { timeout: 1500 }).toBe(true);
  }
  async function keyboardBoundary(dialog: Locator) {
    await containsFocus(dialog);
    await expect(dialog).toHaveJSProperty("open", true);
    expect(await dialog.evaluate((element) => element.matches(":modal"))).toBe(true);
    for (const key of ["Tab", "Shift+Tab", "Shift+Tab", "Tab", "Tab", "Tab", "Tab"]) {
      await page.keyboard.press(key);
      // Native dialogs keep the page inert but allow access to browser chrome.
      await expect.poll(() => dialog.evaluate((element) =>
        element.contains(document.activeElement)
        || (!document.hasFocus() && document.activeElement === document.body),
      )).toBe(true);
    }
    if (!await page.evaluate(() => document.hasFocus())) await page.keyboard.press("Tab");
    await containsFocus(dialog);
    await settingsButton.evaluate((element) => element.focus());
    await containsFocus(dialog);
  }
  try {
    await settingsButton.focus();
    await page.keyboard.press("Enter");
    const settings = page.getByRole("dialog", { name: "Workspace settings", exact: true });
    await expect(settings).toBeVisible();
    await keyboardBoundary(settings);
    await capture(page, info, "owner-settings-keyboard");
    await page.keyboard.press("Escape");
    await expect(settings).toHaveCount(0);
    await expect(settingsButton).toBeFocused();
    await page.keyboard.press("Enter");
    await settings.getByRole("button", { name: "Reset and clean up", exact: true }).click();
    const reset = page.getByRole("dialog", { name: "Reset manager workspace?", exact: true });
    await keyboardBoundary(reset);
    await expect(reset.getByRole("button", { name: "Reset workspace", exact: true })).not.toBeFocused();
    await page.keyboard.press("Escape");
    await expect(reset).toHaveCount(0);
    await expect(settingsButton).toBeFocused();

    await page.getByRole("button", { name: "#search", exact: true }).click();
    const actions = page.getByRole("button", { name: "Agent actions", exact: true });
    await actions.focus();
    await page.keyboard.press("ArrowDown");
    await expect(actions).toHaveAttribute("aria-expanded", "true");
    const rename = page.getByRole("menuitem", { name: "Rename agent", exact: true });
    const clear = page.getByRole("menuitem", { name: "Clear agent history", exact: true });
    await expect(rename).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(clear).toBeFocused();
    await page.keyboard.press("End");
    await expect(page.getByRole("menuitem", { name: "Archive agent", exact: true })).toBeFocused();
    await page.keyboard.press("Home");
    await expect(rename).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(actions).toHaveAttribute("aria-expanded", "false");
    await expect(actions).toBeFocused();
    await page.keyboard.press("ArrowUp");
    await expect(page.getByRole("menuitem", { name: "Archive agent", exact: true })).toBeFocused();
    await page.keyboard.press("Home");
    await page.keyboard.press("Enter");
    const editor = page.getByRole("dialog", { name: "Rename agent", exact: true });
    await keyboardBoundary(editor);
    await expect(page.getByRole("menu")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(editor).toHaveCount(0);
    await expect(actions).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    const history = page.getByRole("dialog", { name: "Clear Search history?", exact: true });
    await keyboardBoundary(history);
    await capture(page, info, "owner-history-keyboard");
    await page.keyboard.press("Escape");
    await expect(history).toHaveCount(0);
    await expect(actions).toBeFocused();

    const create = page.getByRole("button", { name: "Create agent", exact: true }).first();
    await create.focus();
    await page.keyboard.press("Enter");
    const newAgent = page.getByRole("dialog", { name: "Create an agent", exact: true });
    await keyboardBoundary(newAgent);
    await page.keyboard.press("Escape");
    await expect(newAgent).toHaveCount(0);
    await expect(create).toBeFocused();
    expect(commands).toEqual([]);
  } finally {
    page.off("request", track);
  }
}

export async function verifyChannelSaveRecovery(page: Page, owner: OwnerAuthResponse) {
  const routePattern = "**/api/runtime/v1/manager/threads";
  const keys: (string | undefined)[] = [];
  const createdIds: string[] = [];
  const payloads: (string | null)[] = [];
  await page.route(routePattern, async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    keys.push(request.headers()["idempotency-key"]);
    payloads.push(request.postData());
    const response = await route.fetch({ maxRetries: 0 });
    expect(response.status()).toBe(200);
    const result: ManagerThreadDetail = await response.json();
    createdIds.push(result.thread.id);
    if (keys.length === 1) return route.abort("failed");
    return route.fulfill({ response });
  });
  try {
    await page.getByRole("button", { name: "Create agent", exact: true }).first().click();
    const editor = page.getByRole("dialog", { name: "Create an agent", exact: true });
    await editor.getByLabel("Agent name", { exact: true }).fill("Retry fixture");
    await editor.getByLabel("Purpose", { exact: true }).fill("Synthetic channel-save recovery check");
    await editor.getByRole("button", { name: "Create agent", exact: true }).click();
    await expect(editor.getByRole("alert")).toBeVisible();
    await expect(editor.getByLabel("Agent name", { exact: true })).toHaveValue("Retry fixture");
    await editor.getByRole("button", { name: /^(Create agent|Retry save)$/, exact: true }).click();
    await expect(editor).toHaveCount(0);
    const origin = new URL(page.url()).origin;
    const response = await page.request.get(`${origin}/api/runtime/v1/manager/workspace`, {
      headers: { "x-merchant-owner-id": owner.user_id, "x-merchant-store-id": owner.store.id },
    });
    expect(response.status()).toBe(200);
    const workspace: ManagerWorkspaceResponse = await response.json();
    expect(workspace.channels.filter((channel) => channel.title === "Retry fixture")).toHaveLength(1);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
    expect(payloads[1]).toBe(payloads[0]);
    expect(createdIds[1]).toBe(createdIds[0]);
  } finally {
    await page.unroute(routePattern);
  }
}

export async function verifyWorkspaceResetRecovery(page: Page, info: TestInfo, owner: OwnerAuthResponse) {
  const origin = new URL(page.url()).origin;
  const headers = { origin, "x-merchant-owner-id": owner.user_id, "x-merchant-store-id": owner.store.id };
  const resetPattern = "**/api/runtime/v1/manager/workspace/reset";
  const detailPattern = "**/api/runtime/v1/manager/threads/*";
  // Reset finishes in the interview; exercise one destructive flow per fixture.
  {
    let onboardingId: string | null = null;
    let readFailures = 0;
    const keys: (string | undefined)[] = [];
    const onboardingIds: string[] = [];
    await page.route(resetPattern, async (route) => {
      expect(route.request().method()).toBe("POST");
      keys.push(route.request().headers()["idempotency-key"]);
      const response = await route.fetch({ maxRetries: 0 });
      expect(response.status()).toBe(200);
      const result: ManagerWorkspaceResetResponse = await response.json();
      onboardingId = result.workspace.channels.find((channel) => channel.channel_kind === "onboarding")!.id;
      onboardingIds.push(onboardingId);
      return route.fulfill({ response });
    });
    await page.route(detailPattern, async (route) => {
      if (readFailures < 2 && onboardingId
        && route.request().method() === "GET"
        && new URL(route.request().url()).pathname.endsWith(`/threads/${onboardingId}`)) {
        readFailures += 1;
        return route.fulfill({ status: 503, json: {
          error: { code: "SYNTHETIC_READ_FAILURE", message: "Synthetic refresh interruption", request_id: "reset-fixture" },
        } });
      }
      return route.continue();
    });
    try {
      await page.getByRole("button", { name: "Workspace settings", exact: true }).click();
      await page.getByRole("dialog", { name: "Workspace settings", exact: true })
        .getByRole("button", { name: "Reset and clean up", exact: true }).click();
      const dialog = page.getByRole("dialog", { name: /^(Reset manager workspace\?|Workspace reset)$/, exact: true });
      await dialog.getByRole("button", { name: "Reset workspace", exact: true }).click();
      await expect(dialog.getByRole("alert")).toBeVisible();
      expect(keys).toHaveLength(1);

      // Another explicit same-owner action commits while the first result is unresolved.
      const title = "Preserve after confirmed reset";
      const intervening = await page.request.post(`${origin}/api/runtime/v1/manager/threads`, {
        headers: { ...headers, "idempotency-key": "reset-continuity-confirmed" },
        data: { title, description: "Synthetic intervening work that a refresh must preserve" },
      });
      expect(intervening.status()).toBe(200);
      const created: ManagerThreadDetail = await intervening.json();
      await expect(dialog.getByRole("button", { name: "Reset workspace", exact: true })).toHaveCount(0);
      await dialog.getByRole("button", { name: "Refresh workspace", exact: true }).click();
      await expect.poll(() => readFailures).toBe(2);
      await expect(dialog.getByRole("button", { name: "Refresh workspace", exact: true })).toBeEnabled();
      expect(keys).toHaveLength(1);
      await capture(page, info, "owner-confirmed-reset-refresh");
      await dialog.getByRole("button", { name: "Refresh workspace", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      const response = await page.request.get(`${origin}/api/runtime/v1/manager/workspace`, { headers });
      expect(response.status()).toBe(200);
      const workspace: ManagerWorkspaceResponse = await response.json();
      expect(workspace.channels.some((channel) => channel.id === created.thread.id && channel.title === title)).toBe(true);
      expect(workspace.channels.filter((channel) => channel.channel_kind === "onboarding").map((channel) => channel.id))
        .toEqual([onboardingIds[0]]);
      expect(keys).toHaveLength(1);
    } finally {
      if (!page.isClosed()) {
        await page.unroute(resetPattern);
        await page.unroute(detailPattern);
      }
    }
  }
}
