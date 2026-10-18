import { expect, test } from "@playwright/test";
import type { RunListResponse } from "@open-commerce/sdk-typescript";

test("reviewed no-ad goal consumes real PDP serving and recorded economics", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(240_000);
  await page.goto("/lab");
  await expect(
    page.getByRole("heading", {
      name: "Improve contribution profit",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByLabel("Natural-language draft")
    .fill(
      "Merchandising: maximize contribution profit in 14 days; promotion cap $50; minimum unit margin 25%",
    );
  await page.getByRole("button", { name: "Draft", exact: true }).click();
  const activate = page.getByRole("button", {
    name: "Activate and run",
    exact: true,
  });
  await expect(activate).toBeEnabled();
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/v1/goals") &&
      response.request().method() === "POST",
  );
  await activate.click();
  const created = await (await createdResponse).json();
  const goalId: string = created.spec.id;
  try {
    expect(created.spec.budgets[0].amount.amount_minor).toBe(0);
    expect(created.spec.allowed_action_types).not.toContain(
      "set_campaign_budget",
    );
    await expect(page.getByLabel("Run trace")).toContainText("is completed");
    const runsResponse = await request.get(
      `/api/runtime/v1/runs?goal_id=${goalId}`,
    );
    expect(runsResponse.ok()).toBe(true);
    const runs: RunListResponse = await runsResponse.json();
    expect(runs.items).toHaveLength(1);
    expect(runs.items[0].summary.merchandising_decision).toMatchObject({
      planner_version: "merchandising-deterministic-v2",
      kind: "wait",
      selected_key: "unchanged",
      reason: "No supported candidate passed compilation and policy",
    });
    await expect(page.getByLabel("Current goal")).toContainText(
      "Advertising prohibited",
    );
    await page
      .getByRole("button", { name: "Inspect PDP", exact: true })
      .click();
    const panel = page.getByLabel("Product detail recommendations", {
      exact: true,
    });
    await expect(panel).toContainText("alternatives / Active");
    await expect(panel.locator(".search-result")).not.toHaveCount(0);
    await page.getByRole("button", { name: "Pause goal", exact: true }).click();
    await page
      .getByRole("button", { name: "Advance one day", exact: true })
      .click();
    await expect(page.getByLabel("Simulator state")).toContainText("Day 1,", {
      timeout: 150_000,
    });
    await expect(page.getByLabel("Outcomes")).toContainText(
      "Profit / Incoming session",
    );
    const evidence = await request.get(
      `/api/runtime/v1/goals/${goalId}/merchandising/outcomes`,
    );
    expect(evidence.status()).toBe(200);
    const body = await evidence.json();
    expect(JSON.stringify(body)).not.toContain("price_sensitivity");
    await expect(
      page.getByRole("button", { name: "Advance one day", exact: true }),
    ).toBeEnabled();
    await page.getByRole("button", { name: "Inspect PDP", exact: true }).click();
    await expect(panel).toContainText("alternatives / Active");
    await expect(panel.locator(".search-result")).not.toHaveCount(0);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: testInfo.outputPath(`merchandising-${width}.png`),
        fullPage: true,
      });
    }
    await page.reload();
    await expect(page.getByLabel("Saved goal")).toHaveValue(goalId);
    await expect(page.getByLabel("Simulator state")).toContainText("Day 1,");
  } finally {
    await request.post(`/api/runtime/v1/goals/${goalId}/archive`, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  }
});
