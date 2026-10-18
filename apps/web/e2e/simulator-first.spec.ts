import { expect, test } from "@playwright/test";

let previousTestFinishedAt = 0;

test.beforeEach(async () => {
  // Independent browser workflows share the production demo's 60-second quota.
  const remaining = 60_000 - (Date.now() - previousTestFinishedAt);
  if (remaining > 0) {
    const testInfo = test.info();
    testInfo.setTimeout(testInfo.timeout + remaining);
    await new Promise((resolve) => setTimeout(resolve, remaining));
  }
});

test.afterEach(() => {
  previousTestFinishedAt = Date.now();
});

for (const [scenario, metric, label] of [
  ["excess_inventory_v1", "units_sold", "Units sold (whole store)"],
  [
    "search_conversion_v1",
    "search_attributed_purchases",
    "Search-attributed purchases",
  ],
] as const) {
  test(`${scenario} loads persisted metric observations with accurate labels`, async ({
    page,
    request,
  }, testInfo) => {
    const created = await request.post("/api/runtime/v1/goals", {
      data: {
        name: `${scenario} measurements`,
        scenario_id: scenario,
        seed: 42,
      },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    expect(created.status()).toBe(201);
    const goal = await created.json();
    try {
      const advanced = await request.post(
        `/api/runtime/v1/simulator/instances/${goal.simulator_instance_id}/advance`,
        {
          data: { hours: 48 },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      );
      expect(advanced.ok()).toBe(true);
      const metricResponse = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname.endsWith("/v1/metrics/series") &&
          url.searchParams.get("metric") === metric
        );
      });
      await page.goto(`/lab?goal=${goal.spec.id}`);
      const response = await metricResponse;
      expect(response.status()).toBe(200);
      const series = await response.json();
      expect(series.items).toHaveLength(2);
      const chart = page.getByRole("list", { name: `${label} by day (UTC)` });
      await expect(chart.getByRole("listitem")).toHaveCount(2);
      for (const point of series.items) {
        await expect(
          chart.getByRole("listitem", {
            name: `${point.timestamp.slice(0, 10)}: ${label}: ${Number(point.value).toLocaleString("en-US")}`,
          }),
        ).toBeVisible();
      }
      await expect(page.getByLabel("Outcomes")).toContainText("2 days");
      for (const width of [1440, 390]) {
        await page.setViewportSize({ width, height: 1000 });
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        ).toBe(true);
        await page.screenshot({
          path: testInfo.outputPath(`metrics-${width}.png`),
          fullPage: true,
        });
      }
      await page.reload();
      await expect(chart.getByRole("listitem")).toHaveCount(2);
    } finally {
      const archived = await request.post(
        `/api/runtime/v1/goals/${goal.spec.id}/archive`,
        {
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      );
      expect(archived.ok()).toBe(true);
    }
  });
}

test("reset retains the new goal when the kill switch refuses planning", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/runtime/v1/goals", {
    data: { name: "Partial reset recovery", seed: 98 },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
  expect(created.ok()).toBe(true);
  const oldId: string = (await created.json()).spec.id;
  let newId: string | null = null;
  try {
    const enabled = await request.post("/api/runtime/v1/kill-switch/enable", {
      data: {},
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    expect(enabled.ok()).toBe(true);
    await page.goto(`/lab?goal=${oldId}`);
    await expect(page.getByLabel("Saved goal")).toHaveValue(oldId);
    await expect(
      page.getByRole("button", { name: "Kill switch on", exact: true }),
    ).toBeEnabled();
    await page.getByLabel("Seed", { exact: true }).fill("99");
    const refused = page.waitForResponse(
      (response) =>
        response.url().endsWith("/run") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Reset seed", exact: true }).click();
    const failure = await refused;
    expect(failure.status()).toBe(409);
    newId = failure.url().split("/").at(-2)!;
    expect(newId).not.toBe(oldId);
    await expect(page.getByLabel("Saved goal")).toHaveValue(newId);
    expect(new URL(page.url()).searchParams.get("goal")).toBe(newId);
    await expect(
      page.getByRole("button", { name: "Run controller", exact: true }),
    ).toBeDisabled();
    expect(
      (await (await request.get(`/api/runtime/v1/goals/${oldId}`)).json()).spec
        .status,
    ).toBe("archived");
    await page.reload();
    await expect(page.getByLabel("Saved goal")).toHaveValue(newId);
    await expect(page.getByLabel("Seed", { exact: true })).toHaveValue("99");
    await page
      .getByRole("button", { name: "Kill switch on", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Run controller", exact: true }),
    ).toBeEnabled();
    await page
      .getByRole("button", { name: "Run controller", exact: true })
      .click();
    await expect(page.getByLabel("Run trace")).toContainText("build snapshot");
    expect(new URL(page.url()).searchParams.get("goal")).toBe(newId);
  } finally {
    await request.post("/api/runtime/v1/kill-switch/disable", {
      data: {},
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    if (newId) {
      await request.post(`/api/runtime/v1/goals/${newId}/archive`, {
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
    }
  }
});

test("production page is local-only, nonblank and usable on desktop and mobile", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await page.goto("/lab");
  expect(response?.ok()).toBe(true);
  expect(response?.headers()["content-security-policy"]).toContain(
    "'strict-dynamic'",
  );
  expect(response?.headers()["content-security-policy"]).not.toContain(
    "'unsafe-eval'",
  );
  expect(response?.headers()["set-cookie"]).toBeUndefined();
  await expect(
    page.getByRole("heading", { name: "GoodAgent", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("note")).toContainText(
    "Demo identity is not production authentication",
  );
  await expect(
    page.getByRole("button", { name: "Run scenario", exact: true }).first(),
  ).toBeEnabled();
  const ready = await request.get("/api/runtime/health/ready");
  expect(ready.status()).toBe(200);
  const crossSite = await request.post("/api/runtime/v1/goals", {
    headers: { origin: "https://attacker.example" },
    data: {},
  });
  expect(crossSite.status()).toBe(403);
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`workspace-${viewport.width}.png`),
      fullPage: true,
    });
    await page.screenshot({
      path: testInfo.outputPath(`workspace-viewport-${viewport.width}.png`),
      fullPage: false,
    });
  }
  expect(errors).toEqual([]);
  const activate = page.getByRole("button", {
    name: "Activate and run",
    exact: true,
  });
  const draftText = page.getByLabel("Natural-language draft");
  await expect(activate).toBeDisabled();
  await draftText.fill(
    "Acquire 9000 new customers in 30 days with a $10000 budget.",
  );
  await page.getByRole("button", { name: "Draft", exact: true }).click();
  await expect(activate).toBeEnabled();
  await draftText.fill(
    "Acquire 8000 new customers in 30 days with a $10000 budget.",
  );
  await expect(activate).toBeDisabled();
  await page.getByRole("button", { name: "Draft", exact: true }).click();
  await expect(activate).toBeEnabled();
  await page
    .getByRole("button", { name: "Review", exact: true })
    .first()
    .click();
  await expect(activate).toBeDisabled();
});

test("saved goal, approval, worker execution, measurement, search and reset use durable state", async ({
  page,
  request,
}, testInfo) => {
  // Seven virtual days plus a cold 1,000-product learned index on the local CPU.
  testInfo.setTimeout(testInfo.timeout + 180_000);
  await page.goto("/lab");
  await expect(
    page.getByText("Local runtime is connected.", { exact: true }),
  ).toBeVisible();
  const killOff = page.getByRole("button", {
    name: "Kill switch on",
    exact: true,
  });
  if (await killOff.isVisible()) {
    await killOff.click();
    await expect(
      page.getByRole("button", { name: "Kill switch off", exact: true }),
    ).toBeEnabled();
  }
  await page.getByLabel("Seed", { exact: true }).fill("42");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/v1/goals") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Run scenario", exact: true })
    .first()
    .click();
  // This regression intentionally retains the legacy acquisition profile.
  await page
    .getByLabel("Natural-language draft")
    .fill("Acquire 200 new customers in 30 days with a $10000 budget.");
  await expect(
    page.getByRole("button", { name: "Activate and run", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Draft", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Activate and run", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Activate and run", exact: true })
    .click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const goalId: string = (await created.json()).spec.id;
  await expect(page.getByLabel("Saved goal")).toHaveValue(goalId);
  await expect(page.getByLabel("Run trace")).toContainText("build snapshot");
  await expect(
    page.getByRole("button", { name: "Approve hash", exact: true }),
  ).toBeEnabled();
  expect(new URL(page.url()).searchParams.get("goal")).toBe(goalId);
  const progressBefore = await request.get(
    `/api/runtime/v1/goals/${goalId}/progress`,
  );
  expect(progressBefore.ok()).toBe(true);
  const before = await progressBefore.json();

  await page.reload();
  await expect(page.getByLabel("Saved goal")).toHaveValue(goalId!);
  await expect(
    page.getByRole("button", { name: "Approve hash", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Approve hash", exact: true }).click();
  await expect(page.getByLabel("Action details")).toContainText("succeeded");
  const progressAfter = await request.get(
    `/api/runtime/v1/goals/${goalId}/progress`,
  );
  expect((await progressAfter.json()).latest_run_id).toBe(before.latest_run_id);

  await page.getByRole("button", { name: "Pause goal", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Resume goal", exact: true }),
  ).toBeEnabled();
  for (let day = 1; day <= 7; day++) {
    await page
      .getByRole("button", { name: "Advance one day", exact: true })
      .click();
    await expect(page.getByLabel("Simulator state")).toContainText(
      `Day ${day},`,
    );
    await expect(
      page.getByRole("button", { name: "Advance one day", exact: true }),
    ).toBeEnabled();
  }
  await expect(page.getByLabel("Action details")).toContainText(
    "Observed Outcome",
  );
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByLabel("Search playground")).toContainText("results");
  await expect(
    page.getByText("Search trace updated.", { exact: true }),
  ).toBeVisible({ timeout: 130_000 });
  await page.screenshot({
    path: testInfo.outputPath("durable-goal.png"),
    fullPage: true,
  });

  let releaseRead!: () => void;
  let sawRead!: () => void;
  const release = new Promise<void>((resolve) => {
    releaseRead = resolve;
  });
  const captured = new Promise<void>((resolve) => {
    sawRead = resolve;
  });
  let holdNextRead = true;
  await page.route("**/v1/kill-switch", async (route) => {
    if (!holdNextRead) return route.continue();
    holdNextRead = false;
    const response = await route.fetch();
    sawRead();
    await release;
    await route.fulfill({ response });
  });
  await captured;
  let releasePolicy!: () => void;
  let sawPolicy!: () => void;
  const policyRelease = new Promise<void>((resolve) => {
    releasePolicy = resolve;
  });
  const policyCaptured = new Promise<void>((resolve) => {
    sawPolicy = resolve;
  });
  await page.route("**/v1/policy", async (route) => {
    const response = await route.fetch();
    sawPolicy();
    await policyRelease;
    await route.fulfill({ response });
  });
  await page
    .getByRole("button", { name: "Kill switch off", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Kill switch on", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run controller", exact: true }),
  ).toBeDisabled();
  await policyCaptured;
  const staleDelivered = page.waitForResponse((response) =>
    response.url().endsWith("/v1/kill-switch"),
  );
  releaseRead();
  await staleDelivered;
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  await expect(
    page.getByRole("button", { name: "Kill switch on", exact: true }),
  ).toBeVisible();
  releasePolicy();
  await expect(
    page.getByRole("button", { name: "Kill switch on", exact: true }),
  ).toBeEnabled();
  await page.unrouteAll({ behavior: "wait" });
  await page
    .getByRole("button", { name: "Kill switch on", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Kill switch off", exact: true }),
  ).toBeEnabled();
  expect(
    (await (await request.get("/api/runtime/v1/kill-switch")).json()).enabled,
  ).toBe(false);
  await page.getByLabel("Seed", { exact: true }).fill("84");
  await page.getByRole("button", { name: "Reset seed", exact: true }).click();
  await expect(
    page.getByText("Fresh seeded goal created; previous history retained.", {
      exact: true,
    }),
  ).toBeVisible();
  const newGoalId = new URL(page.url()).searchParams.get("goal");
  expect(newGoalId).not.toBe(goalId);
  const oldGoal = await request.get(`/api/runtime/v1/goals/${goalId}`);
  expect((await oldGoal.json()).spec.status).toBe("archived");
  const newGoal = await request.get(`/api/runtime/v1/goals/${newGoalId}`);
  expect((await newGoal.json()).seed).toBe(84);
  await page.reload();
  await expect(page.getByLabel("Saved goal")).toHaveValue(newGoalId!);
  await expect(page.getByLabel("Seed", { exact: true })).toHaveValue("84");
  await expect(
    page.getByText("Local runtime is connected.", { exact: true }),
  ).toBeVisible();
});
