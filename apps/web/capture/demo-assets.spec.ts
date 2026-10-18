import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test, type Locator } from "@playwright/test";

test("six launch assets from a fresh seeded simulator", async ({
  page,
  request,
  browser,
}, testInfo) => {
  const started = Date.now();
  const root = path.resolve(process.cwd(), "../..");
  const output = path.join(root, "docs/assets/demo");
  const assets: {
    file: string;
    sha256: string;
    caption: string;
    viewport: { width: number; height: number } | null;
  }[] = [];
  const write = async (route: string, data: unknown = {}) => {
    const response = await request.post(`/api/runtime${route}`, {
      data,
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    expect(response.ok(), `${route}: ${await response.text()}`).toBe(true);
    return response;
  };
  const initial = await request.get("/api/runtime/v1/goals?limit=1");
  expect(initial.ok()).toBe(true);
  expect(
    (await initial.json()).items,
    "Use a fresh dedicated capture project; never reset an existing demo",
  ).toEqual([]);
  await mkdir(output, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const capture = async (file: string, caption: string, locator?: Locator) => {
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const target = path.join(output, file);
    if (locator)
      await locator.screenshot({ path: target, animations: "disabled" });
    else await page.screenshot({ path: target, animations: "disabled" });
    assets.push({
      file,
      caption,
      viewport: page.viewportSize(),
      sha256: createHash("sha256")
        .update(await readFile(target))
        .digest("hex"),
    });
  };
  await page.goto("/");
  await expect(
    page.getByText("Local runtime is connected.", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Natural-language draft")
    .fill("Acquire 200 new customers in 30 days with a $10000 budget.");
  await page.getByRole("button", { name: "Draft", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Activate and run", exact: true }),
  ).toBeEnabled();
  const wizard = page.getByLabel("Goal wizard");
  await wizard.getByText("New goal review", { exact: true }).click();
  await capture(
    "goal-configuration.png",
    "Finite-parser draft for 200 customers, 30 days, $10,000; seed 42. Fixed constraints are reviewed before activation.",
    wizard,
  );
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/v1/goals") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Activate and run", exact: true })
    .click();
  const goal = await (await created).json();
  await expect(page.getByLabel("Run trace")).toContainText("build snapshot");
  await expect(
    page.getByRole("button", { name: "Approve hash", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Approve hash", exact: true }).click();
  await expect(page.getByLabel("Action details")).toContainText(
    "Simulator execution: succeeded",
  );
  await expect(page.getByLabel("Action details")).toContainText(
    "Reconciliation: reconciled",
  );
  await capture(
    "agent-trace.png",
    "Persisted controller trace. Deterministic planning and estimates are distinct from permission, execution and measurement.",
    page.getByLabel("Run trace"),
  );
  const runIds = new Set<string>();
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
    const progress = await (
      await request.get(`/api/runtime/v1/goals/${goal.spec.id}/progress`)
    ).json();
    if (progress.latest_run_id) runIds.add(progress.latest_run_id);
  }
  await expect
    .poll(async () => {
      const runs = await (
        await request.get(
          `/api/runtime/v1/runs?goal_id=${goal.spec.id}&limit=30`,
        )
      ).json();
      return runs.items.length;
    })
    .toBeGreaterThan(1);
  await page.reload();
  await expect(page.getByLabel("Outcomes")).toContainText("7 days");
  await page.evaluate(() => scrollTo(0, 0));
  await capture(
    "dashboard.png",
    "Seed 42 acquisition goal after seven virtual days. Values are actual cumulative observations, not a forecast or causal lift.",
  );
  await capture(
    "kpi-observations.png",
    "Seven days of observed outcomes and matched synthetic baseline delta. The capture does not require positive improvement.",
    page.getByLabel("Outcomes"),
  );
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByText("Search trace updated.", { exact: true }),
  ).toBeVisible();
  const search = page.getByLabel("Search playground");
  await search.getByText("Debug trace", { exact: true }).click();
  await capture(
    "hybrid-search-trace.png",
    "Actual live-Qdrant hybrid query, hard filters and score components. No result or score is mocked.",
    search,
  );
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => scrollTo(0, 0));
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`review-${viewport.width}.png`),
      fullPage: true,
    });
    await page.screenshot({
      path: testInfo.outputPath(`review-viewport-${viewport.width}.png`),
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Wait out the demo quota before the separate denial fixture; no rate-limit bypass.
  await new Promise((resolve) => setTimeout(resolve, 60_000));
  await write(`/v1/goals/${goal.spec.id}/pause`);
  const oldPolicy = await (await request.get("/api/runtime/v1/policy")).json();
  const patchPolicy = async (discount: string) => {
    const response = await request.put("/api/runtime/v1/policy", {
      data: { discount_max_percentage: discount },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    expect(response.ok(), await response.text()).toBe(true);
  };
  try {
    await patchPolicy("0.05");
    const denied = await (
      await write("/v1/goals", {
        name: "Policy fixture: 10% proposal / 5% maximum",
        scenario_id: "acquisition_v1",
        seed: 42,
        target_value: "9000",
      })
    ).json();
    await write(`/v1/goals/${denied.spec.id}/activate`);
    await write(`/v1/goals/${denied.spec.id}/run`);
    await page.goto(`/?goal=${denied.spec.id}`);
    const actions = page.getByLabel("Action details");
    await expect(actions).toContainText("denied");
    await actions
      .getByRole("button")
      .filter({ hasText: "create discount" })
      .click();
    await actions
      .getByText("Deterministic rule checks", { exact: true })
      .click();
    await expect(actions).toContainText("FAIL");
    await expect(
      actions.getByRole("button", { name: "Approve hash", exact: true }),
    ).toBeDisabled();
    await capture(
      "rejected-policy-action.png",
      "Separate policy fixture: a real 10% discount proposal is denied under a tightened 5% maximum. This is not the default 15% policy.",
      actions,
    );
    await write(`/v1/goals/${denied.spec.id}/pause`);
  } finally {
    await patchPolicy(oldPolicy.discount_max_percentage);
  }
  expect(errors).toEqual([]);
  const observations = await (
    await request.get(`/api/runtime/v1/goals/${goal.spec.id}/progress`)
  ).json();
  await writeFile(
    path.join(output, "manifest.json"),
    JSON.stringify(
      {
        fixture: "private-prelaunch-v1",
        seed: 42,
        virtualDays: 7,
        browser: browser.version(),
        viewport: { width: 1440, height: 1000 },
        timezone: "UTC",
        locale: "en-US",
        walkthroughSeconds: (Date.now() - started) / 1000,
        observation: {
          current: observations.current_value,
          target: observations.target_value,
          assessment: observations.assessment?.trajectory,
        },
        sampledRunCount: runIds.size,
        limitations: [
          "Browser timing/UUIDs may vary; images are not byte-identical benchmarks.",
          "Synthetic observations, not causal merchant lift.",
          "Includes a 60-second quota wait and a separate tightened-policy fixture; excludes stack startup.",
        ],
        assets,
      },
      null,
      2,
    ) + "\n",
  );
});
