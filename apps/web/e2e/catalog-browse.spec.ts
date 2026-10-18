import { expect, test, type Page } from "@playwright/test";
import type {
  CatalogBrowseResponse,
  ManagerDatasetProfileReply,
  ManagerThreadDetail,
} from "@open-commerce/sdk-typescript";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test("indexed Amazon upload is browsable on both clients", async ({
  page,
  request,
}, testInfo) => {
  const api = process.env.OPEN_COMMERCE_E2E_API_URL;
  const shopper = process.env.OPEN_COMMERCE_SHOPPER_BROWSER_TEST_URL;
  test.skip(
    !api || !shopper,
    "Requires the isolated API harness and a running shopper UI",
  );
  if (!api || !shopper) return;
  test.setTimeout(240000);
  const created = await request.post(`${api}/v1/manager/threads`, {
    headers: { "Idempotency-Key": `browse-thread-${Date.now()}` },
    data: { title: "Catalog browser verification" },
  });
  expect(created.ok()).toBe(true);
  const detail = (await created.json()) as ManagerThreadDetail;
  const upload = await request.post(
    `${api}/v1/manager/threads/${detail.thread.id}/datasets/profile`,
    {
      headers: { "Idempotency-Key": `browse-upload-${Date.now()}` },
      data: {
        dataset_kind: "catalog",
        filename: "abo-catalog.csv",
        csv_text: await readFile(
          resolve(process.cwd(), "public/abo-catalog.csv"),
          "utf8",
        ),
      },
    },
  );
  expect(upload.ok()).toBe(true);
  const profile = (await upload.json()) as ManagerDatasetProfileReply;
  await expect
    .poll(
      async () => {
        const response = await request.get(`${api}/v1/manager/catalog`);
        const result = (await response.json()) as CatalogBrowseResponse;
        return result.catalog?.id;
      },
      { timeout: 90000 },
    )
    .toBe(profile.catalog_index?.catalog_id);

  await page.route("**/api/runtime/**", async (route) => {
    const url = new URL(route.request().url());
    const headers: Record<string, string> = {};
    for (const key of [
      "content-type",
      "idempotency-key",
      "x-request-id",
      "cookie",
    ])
      if (route.request().headers()[key])
        headers[key] = route.request().headers()[key];
    const response = await route.fetch({
      url: `${api}${url.pathname.replace("/api/runtime", "")}${url.search}`,
      headers,
    });
    try {
      await route.fulfill({ response });
    } catch (error) {
      // A page reload can cancel a polling request while its API response is in flight.
      if (
        !(error instanceof Error) ||
        !error.message.includes("Route is already handled")
      )
        throw error;
    }
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/manager/catalog");
  await expect(
    page.getByText("48 products in the indexed catalog"),
  ).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(24);
  await verifyImagesAndOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath("catalog-manager-1440x1000.png"),
  });
  await page.getByLabel("Next page").click();
  await expect(page.getByText("25-48 of 48")).toBeVisible();
  await page.getByLabel("Find catalog products").fill("B07QCR35JF");
  await page.getByLabel("Find products", { exact: true }).click();
  await expect(page.getByRole("article")).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: /Organic Pumpkin Spice Coffee/ }),
  ).toBeVisible();
  await page.getByLabel("Find catalog products").fill("");
  await page.getByLabel("Find products", { exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("article")).toHaveCount(24);
  await verifyImagesAndOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath("catalog-manager-390x844.png"),
  });

  await page.goto(`${shopper}/catalog`);
  await expect(page.getByLabel("Username")).toBeVisible();
  await page.getByLabel("Display name").fill("Catalog Tester");
  await page.getByLabel("Username").fill(`browse${Date.now()}`);
  await page.getByLabel("Password").fill("isolated-catalog-demo-password");
  await page
    .locator("form")
    .getByRole("button", { name: "Create account" })
    .last()
    .click();
  await expect(
    page.getByText("48 products from abo-catalog.csv"),
  ).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(24);
  await verifyImagesAndOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath("catalog-shopper-390x844.png"),
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: testInfo.outputPath("catalog-shopper-1440x1000.png"),
  });
  await page
    .getByLabel("Category", { exact: true })
    .selectOption({ label: "Grocery" });
  await expect(page.getByRole("article").first()).toContainText("Grocery");
  const add = page.getByRole("button", { name: /^Add .* to cart$/ }).first();
  await expect(add).toBeEnabled();
  await add.click();
  await expect(page.getByText("Your cart", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review checkout" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Close cart" }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Browse the store" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open cart with 1 items" }),
  ).toBeVisible();

  await page.goto(shopper);
  await page.getByRole("textbox", { name: "Shopping request" }).fill(
    "i like premium expensive stuff, keep that in mind",
  );
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.locator(".memory-saved")).toHaveText("Saved to shopping memory");
  await page.reload();
  await page.getByRole("button", { name: "Shopping memory" }).click();
  await expect(page.getByText("i like premium expensive stuff", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("shopper-memory-1440x1000.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText("i like premium expensive stuff", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("shopper-memory-390x844.png") });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Shopping activity", exact: true }).click();
  const activity = page.getByRole("region", { name: "Shopping activity", exact: true });
  await expect(activity.getByText("Recent events", { exact: true })).toBeVisible();
  await expect(activity.getByText("memory save", { exact: true }).first()).toBeVisible();
  expect(await activity.textContent()).not.toContain("i like premium expensive stuff");
  const rulePayload = { name: "Chat errors", query: { kind: "chat" }, metric: "error_rate", threshold: 10, minimum_samples: 5, interval_minutes: 1 };
  const ruleResponse = await page.request.post(`${api}/v1/shopper/activity/rules`, {
    headers: { "Idempotency-Key": "browser-personal-monitor" }, data: rulePayload,
  });
  expect(ruleResponse.ok()).toBe(true);
  const beforeCheck = (await ruleResponse.json()).check.checked_at;
  await activity.getByRole("button", { name: "Refresh activity" }).click();
  await expect(activity.getByText("Chat errors", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("shopper-activity-1440x1000.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("shopper-activity-390x844.png") });
  await page.getByRole("button", { name: "Close activity" }).click();
  await expect.poll(async () => {
    const response = await page.request.get(`${api}/v1/shopper/activity`);
    return (await response.json()).rules[0].check.checked_at;
  }, { timeout: 100000 }).not.toBe(beforeCheck);
  expect((await request.post(`${api}/v1/manager/activity/rules`, {
    headers: { "Idempotency-Key": "browser-store-monitor" }, data: rulePayload,
  })).ok()).toBe(true);
  expect(errors).toEqual([]);
});

async function verifyImagesAndOverflow(page: Page) {
  await expect
    .poll(() =>
      page
        .getByRole("article")
        .first()
        .locator("img")
        .evaluate(
          (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
        ),
    )
    .toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page
      .getByLabel("Catalog products", { exact: true })
      .evaluate((element) => element.scrollWidth <= element.clientWidth),
  ).toBe(true);
}
