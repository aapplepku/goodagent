import { expect, type Page, type TestInfo } from "@playwright/test";
import type { ShopperChatResponse, ShopperMemory } from "@open-commerce/sdk-typescript";

/** Exercise management while recall is off and a real committed DELETE response is lost. */
export async function verifyShopperMemoryControls(page: Page, info: TestInfo, slug: string, accountId: string) {
  const preference = "I prefer reusable cotton bags";
  const origin = new URL(page.url()).origin;
  const endpoint = (suffix: string) => `${origin}/api/runtime/v1/shopper/${suffix}`;
  const headers = { origin, "x-store-slug": slug, "x-shopper-account-id": accountId };
  const cartBefore = await (await page.request.get(endpoint("cart"), { headers })).json();
  async function capture(name: string) {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const control = page.getByRole("button", { name: name.includes("uncertain") ? `Retry removing ${preference}` : `Forget ${preference}`, exact: true });
      const box = await control.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(44);
      expect(box!.width).toBeGreaterThanOrEqual(44);
      await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}x${viewport.height}.png`) });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  await page.getByRole("button", { name: "Close account", exact: true }).click();
  await page.getByRole("button", { name: "Start something new", exact: true }).click();
  await page.getByLabel("Shopping request", { exact: true }).fill(preference);
  const saved = page.waitForResponse(response => new URL(response.url()).pathname === "/api/runtime/v1/shopper/chat" && response.request().method() === "POST");
  await page.getByRole("button", { name: "Send request", exact: true }).click();
  const savedResponse = await saved;
  expect(savedResponse.status()).toBe(200);
  const chat: ShopperChatResponse = await savedResponse.json();
  const memory = chat.memories_saved?.find(item => item.content === preference);
  expect(memory).toBeTruthy();
  await expect(page.locator(".memory-saved")).toHaveText("Saved to shopping memory");
  await page.getByRole("button", { name: "Account", exact: true }).click();
  const memoryToggle = page.getByLabel("Remember shopping preferences", { exact: true });
  await expect(memoryToggle).toBeChecked();
  await memoryToggle.click();
  await expect(memoryToggle).not.toBeChecked();
  await expect(page.getByLabel("Remember shopping preferences", { exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Close account", exact: true }).click();
  await page.getByRole("button", { name: /Shopping memory/ }).click();
  await expect(page.getByText(/Shopping memory is off/)).toBeVisible();
  await expect(page.getByRole("button", { name: `Forget ${preference}`, exact: true })).toBeVisible();
  const listed = await page.request.get(endpoint("memories"), { headers });
  expect(listed.status()).toBe(200);
  expect((await listed.json()).items.some((item: ShopperMemory) => item.id === memory!.id)).toBe(true);
  await capture("shopper-memory-off-retained");
  const removals: string[] = [];
  const routePath = `**/v1/shopper/memories/${memory!.id}`;
  await page.route(routePath, async route => {
    expect(route.request().method()).toBe("DELETE");
    expect(route.request().headers()["x-shopper-account-id"]).toBe(accountId);
    const key = route.request().headers()["idempotency-key"];
    expect(key).toBeTruthy();
    removals.push(key);
    if (removals.length === 1) {
      const committed = await route.fetch({ maxRetries: 0, maxRedirects: 0 });
      expect(committed.status()).toBe(200);
      expect(await committed.json()).toMatchObject({ memory_id: memory!.id, deleted: true });
      await route.abort("failed");
    } else {
      expect(key).toBe(removals[0]);
      await route.continue();
    }
  });
  try {
    await page.getByRole("button", { name: `Forget ${preference}`, exact: true }).click();
    await expect(page.getByRole("button", { name: `Retry removing ${preference}`, exact: true })).toBeVisible();
    await capture("shopper-memory-removal-uncertain");
    expect(removals).toHaveLength(1);
    await page.getByRole("button", { name: "Close memory", exact: true }).click();
    await page.getByRole("button", { name: /Shopping memory/ }).click();
    await expect(page.getByRole("button", { name: `Forget ${preference}`, exact: true })).toHaveCount(0);
    const retry = page.getByRole("button", { name: "Retry removing preference", exact: true });
    await expect(retry).toBeVisible();
    await retry.focus();
    await expect(retry).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: /Retry removing/ })).toHaveCount(0);
    expect(removals).toHaveLength(2);
    const after = await page.request.get(endpoint("memories"), { headers });
    expect(after.status()).toBe(200);
    expect((await after.json()).items).toEqual([]);
    expect((await (await page.request.get(endpoint("me"), { headers })).json()).account.memory_enabled).toBe(false);
    expect(await (await page.request.get(endpoint("cart"), { headers })).json()).toEqual(cartBefore);
  } finally {
    await page.unroute(routePath);
  }
  await page.reload();
  await expect(page.getByText("Alex", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Shopping memory/ }).click();
  await expect(page.getByText("No saved preferences yet.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Shopping memory is off/)).toBeVisible();
  await page.getByRole("button", { name: "Close memory", exact: true }).click();
  await page.getByRole("button", { name: "Account", exact: true }).click();
  await expect(memoryToggle).not.toBeChecked();
  await memoryToggle.click();
  await expect(page.getByLabel("Remember shopping preferences", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("Remember shopping preferences", { exact: true })).toBeChecked();
}
