import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

interface ManagerChannel {
  id: string;
  channel_kind: string;
}

interface ManagerWorkspace {
  channels: ManagerChannel[];
  catalog_index: { status: string };
}

interface CommerceOverview {
  orders: unknown[];
  payments: Array<{ status: string }>;
}

const apiBase =
  process.env.OPEN_COMMERCE_E2E_API_BASE_URL ??
  `http://127.0.0.1:${process.env.API_PORT ?? "8000"}`;

test("shopper signs in and runs a catalog-grounded conversation", async ({
  page,
  request,
}, testInfo) => {
  const bootstrap = await request.post(`${apiBase}/v1/manager/workspace/bootstrap`, {
    headers: { "Idempotency-Key": `shopper-e2e-bootstrap-${Date.now()}` },
  });
  expect(bootstrap.ok()).toBe(true);
  const workspace = (await bootstrap.json()) as ManagerWorkspace;
  const onboarding = workspace.channels.find(
    (channel) => channel.channel_kind === "onboarding",
  );
  expect(onboarding).toBeDefined();

  if (workspace.catalog_index.status !== "ready") {
    const csv = await readFile(
      resolve(process.cwd(), "../web/public/sample-catalog.csv"),
      "utf8",
    );
    const upload = await request.post(
      `${apiBase}/v1/manager/threads/${onboarding!.id}/datasets/profile`,
      {
        headers: { "Idempotency-Key": `shopper-e2e-catalog-${Date.now()}` },
        data: {
          dataset_kind: "catalog",
          filename: "sample-catalog.csv",
          csv_text: csv,
        },
      },
    );
    expect(upload.ok()).toBe(true);
  }
  await expect
    .poll(
      async () => {
        const response = await request.get(`${apiBase}/v1/manager/workspace`);
        const state = (await response.json()) as ManagerWorkspace;
        return state.catalog_index.status;
      },
      { timeout: 90_000 },
    )
    .toBe("ready");

  await page.goto("/");
  await expect(page.getByText("Your store, in conversation.")).toBeVisible();
  const username = `shopper${Date.now()}`;
  await page.getByLabel("Display name").fill("Alex");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill("local-demo-password");
  await page.locator("form").getByRole("button", { name: "Create account" }).last().click();

  await expect(page.getByText("What are we shopping for?")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Shopping request" })
    .fill("Find a quiet coffee setup under $150 for a small apartment");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.locator(".product-card").first()).toBeVisible();
  await expect(page.getByText("How I searched").first()).toBeVisible();

  await page.locator(".product-card").first().getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("Your cart")).toBeVisible();
  await page.getByRole("button", { name: "Review checkout" }).click();
  await expect(page.getByText("Demo payment")).toBeVisible();
  await page.getByRole("button", { name: "Test decline" }).click();
  await expect(page.getByText(/declined/i)).toBeVisible();
  await page.getByRole("button", { name: "Approve test payment" }).click();
  await expect(page.getByText("Order confirmed")).toBeVisible();

  const commerce = await request.get(`${apiBase}/v1/manager/commerce/overview`);
  expect(commerce.ok()).toBe(true);
  const overview = (await commerce.json()) as CommerceOverview;
  expect(overview.orders.length).toBeGreaterThan(0);
  expect(overview.payments.some((payment) => payment.status === "succeeded")).toBe(true);

  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("shopper-1440x1000.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Open conversations" }).click();
  await expect(page.getByText("Conversations")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("shopper-390x844.png"),
    fullPage: true,
  });
});
