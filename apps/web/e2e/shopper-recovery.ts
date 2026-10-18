import { expect, type Browser, type Page, type TestInfo } from "@playwright/test";
import type { Cart, ShopperAuthResponse } from "@open-commerce/sdk-typescript";

/** A separate synthetic account proves voluntary recovery does not lose its receipt. */
export async function verifyGuestPanelRecovery(browser: Browser, url: string, slug: string, info: TestInfo) {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto(url);
    await expect(page.getByRole("button", { name: "Save your progress", exact: true })).toBeVisible();
    // The published link can redirect from the owner app to the shopper origin.
    const origin = new URL(page.url()).origin;
    const endpoint = (path: string) => `${origin}/api/runtime/v1/shopper/${path}`;
    const headers = { origin, "x-store-slug": slug };
    const initialResponse = await page.request.get(endpoint("me"), { headers });
    expect(initialResponse.status()).toBe(200);
    const initial: ShopperAuthResponse = await initialResponse.json();
    expect(initial.account.is_guest).toBe(true);
    const registered = await page.request.post(endpoint("auth/register"), {
      headers: { ...headers, "x-shopper-account-id": initial.account.id },
      data: { username: "fixture-panel-recovery", display_name: "Recovery fixture", password: "synthetic-panel-password" },
    });
    expect(registered.status()).toBe(201);
    const identity: ShopperAuthResponse = await registered.json();
    expect(identity.recovery_code).toBeTruthy();
    expect((await page.request.post(endpoint("auth/logout"), { headers })).status()).toBe(204);
    await page.reload();
    await expect(page.getByRole("button", { name: "Save your progress", exact: true })).toBeVisible();
    const guest: ShopperAuthResponse = await (await page.request.get(endpoint("me"), { headers })).json();
    expect(guest.account.is_guest).toBe(true);
    expect(guest.account.id).not.toBe(identity.account.id);
    const recoveryRequests: string[] = [];
    page.on("request", request => {
      if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/auth/recover"))
        recoveryRequests.push(request.url());
    });
    await page.getByRole("button", { name: "Save your progress", exact: true }).click();
    await page.getByRole("button", { name: "Recover", exact: true }).click();
    const title = page.getByRole("heading", { name: "Recover your shopping account", exact: true });
    await expect(title).toBeVisible();
    await expect(title).toBeFocused();
    await expect(page.getByRole("button", { name: "Back to sign in", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Start a new guest visit", exact: true })).toHaveCount(0);
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`shopper-requested-recovery-${viewport.width}x${viewport.height}.png`) });
    }
    expect(recoveryRequests).toHaveLength(0);
    await page.getByLabel("Username", { exact: true }).fill(identity.account.username);
    await page.getByLabel("Recovery code", { exact: true }).fill(identity.recovery_code!);
    await page.getByLabel("New password", { exact: true }).fill("synthetic-panel-new-password");
    const recoveredResponse = page.waitForResponse(response =>
      new URL(response.url()).pathname.endsWith("/auth/recover") && response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Recover account", exact: true }).click();
    const response = await recoveredResponse;
    expect(response.status()).toBe(200);
    const recovered: ShopperAuthResponse = await response.json();
    expect(recovered.account.id).toBe(identity.account.id);
    expect(recovered.recovery_code).toBeTruthy();
    expect(recovered.recovery_code).not.toBe(identity.recovery_code);
    const code = page.getByLabel("Replacement recovery code", { exact: true });
    await expect(code).toHaveText(recovered.recovery_code!);
    await expect(page.locator(".shop-shell")).toHaveCount(0);
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`shopper-requested-receipt-${viewport.width}x${viewport.height}.png`), mask: [code] });
    }
    const storage = await page.evaluate(() => [...Object.values(localStorage), ...Object.values(sessionStorage)]);
    expect(storage.join("\n")).not.toContain(recovered.recovery_code!);
    expect(storage.join("\n")).not.toContain(identity.recovery_code!);
    await page.getByRole("button", { name: "I stored it privately; continue", exact: true }).click();
    await expect(page.getByRole("button", { name: "Account", exact: true })).toBeVisible();
    await expect(code).toHaveCount(0);
    const current: ShopperAuthResponse = await (await page.request.get(endpoint("me"), { headers })).json();
    expect(current.account.id).toBe(identity.account.id);
    expect(recoveryRequests).toHaveLength(1);
  } finally {
    await context.close();
  }
}

/** Recover a synthetic registered account after actual session revocation. */
export async function verifyShopperRecoveryCode(
  page: Page,
  info: TestInfo,
  input: { slug: string; identity: ShopperAuthResponse; code: string; draft: string; failedMessage: string },
) {
  const origin = new URL(page.url()).origin;
  const endpoint = (path: string) => `${origin}/api/runtime/v1/shopper/${path}`;
  const headers = {
    origin,
    "x-store-slug": input.slug,
    "x-shopper-account-id": input.identity.account.id,
  };
  const before: Cart = await (await page.request.get(endpoint("cart"), { headers })).json();
  expect((await page.request.delete(endpoint("auth/sessions"), { headers })).status()).toBe(204);
  expect((await page.request.get(endpoint("me"), { headers })).status()).toBe(401);
  await page.getByRole("button", { name: "Demo orders", exact: true }).click();
  const expired = page.getByRole("heading", { name: "Your shopping session expired", exact: true });
  await expect(expired).toBeVisible();
  await expect(expired).toBeFocused();
  const mutations: string[] = [];
  const requests = (request: import("@playwright/test").Request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/runtime/v1/") && !["GET", "HEAD"].includes(request.method())) {
      mutations.push(`${request.method()} ${url.pathname}`);
    }
  };
  page.on("request", requests);
  try {
    await page.getByRole("button", { name: "Use a recovery code", exact: true }).click();
    // Capture empty fields; scrolled-page masking must not be the privacy boundary.
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({
        path: info.outputPath(`shopper-code-recovery-form-${viewport.width}x${viewport.height}.png`),
      });
      await page.mouse.move(viewport.width / 2, viewport.height - 40);
      await page.mouse.wheel(0, 1200);
      await expect(page.getByRole("button", { name: "Start a new guest visit", exact: true })).toBeInViewport({ ratio: 1 });
      const bottom = await page.evaluate(() => Math.max(0, document.documentElement.scrollHeight - innerHeight));
      await expect.poll(() => page.evaluate(() => Math.round(scrollY))).toBe(bottom);
      if (viewport.width === 390) {
        await page.screenshot({
          path: info.outputPath("shopper-code-recovery-form-scrolled-390x844.png"),
        });
      }
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    await page.getByLabel("Username", { exact: true }).fill(input.identity.account.username);
    await page.getByLabel("Recovery code", { exact: true }).fill(input.code);
    await page.getByLabel("New password", { exact: true }).fill("synthetic-shopper-password");
    const responsePromise = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/runtime/v1/shopper/auth/recover" && response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Recover account", exact: true }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);
    const recovered: ShopperAuthResponse = await response.json();
    expect(recovered.account.id).toBe(input.identity.account.id);
    expect(recovered.recovery_code).toBeTruthy();
    expect(recovered.recovery_code).not.toBe(input.code);
    const code = page.getByLabel("Replacement recovery code", { exact: true });
    await expect(code).toBeVisible();
    await expect(code).toHaveText(recovered.recovery_code!);
    await expect(page.getByLabel("Shopping request", { exact: true })).toHaveCount(0);
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({
        path: info.outputPath(`shopper-code-recovery-receipt-${viewport.width}x${viewport.height}.png`),
        mask: [code],
      });
    }
    const stored = await page.evaluate(() => ({
      local: Object.values(localStorage), session: Object.values(sessionStorage),
    }));
    for (const value of [...stored.local, ...stored.session]) {
      expect(value).not.toContain(input.code);
      expect(value).not.toContain(recovered.recovery_code!);
      expect(value).not.toContain("synthetic-shopper-password");
    }
    await page.getByRole("button", { name: "I stored it privately; continue", exact: true }).click();
    await expect(expired).toHaveCount(0);
    await expect(code).toHaveCount(0);
    await expect(page.getByLabel("Shopping request", { exact: true })).toHaveValue(input.draft);
    await expect(page.getByText(input.failedMessage, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry same request", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Send request", exact: true })).toBeDisabled();
    const current: ShopperAuthResponse = await (await page.request.get(endpoint("me"), { headers })).json();
    expect(current.account.id).toBe(input.identity.account.id);
    const after: Cart = await (await page.request.get(endpoint("cart"), { headers })).json();
    expect(after).toEqual(before);
    expect(mutations).toEqual(["POST /api/runtime/v1/shopper/auth/recover"]);
  } finally {
    page.off("request", requests);
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
}
