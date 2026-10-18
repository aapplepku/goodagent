import { expect, test, type Page } from "@playwright/test";
import { resolve } from "node:path";

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test.beforeEach(async ({ page }) => {
  const isolatedApi = process.env.OPEN_COMMERCE_E2E_API_URL;
  if (!isolatedApi) return;
  const origin = new URL(isolatedApi);
  if (origin.protocol !== "http:" || origin.hostname !== "127.0.0.1")
    throw new Error("The isolated test API must be loopback-only");
  await page.route("**/api/runtime/**", async (route) => {
    const source = new URL(route.request().url());
    const headers: Record<string, string> = {};
    for (const key of ["content-type", "idempotency-key", "x-request-id"])
      if (route.request().headers()[key]) headers[key] = route.request().headers()[key];
    const response = await route.fetch({
      url: `${origin.origin}${source.pathname.replace("/api/runtime", "")}${source.search}`,
      headers,
    });
    await route.fulfill({ response });
  });
});

async function answerText(page: Page, answer: string, nextQuestion: string) {
  const input = page.getByRole("textbox", { name: "Your onboarding answer" });
  await input.fill(answer);
  await page.getByRole("button", { name: "Send answer" }).click();
  await expect(page.getByText(nextQuestion).first()).toBeVisible();
}

async function choose(
  page: Page,
  answer: string | RegExp,
  nextQuestion: string,
) {
  await page.getByRole("button", { name: answer }).click();
  await expect(page.getByText(nextQuestion).first()).toBeVisible();
}

async function chooseMany(
  page: Page,
  answers: (string | RegExp)[],
  nextQuestion: string,
) {
  for (const answer of answers)
    await page.getByRole("button", { name: answer }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(nextQuestion).first()).toBeVisible();
}

test("operator completes onboarding and collaborates across agents", async ({
  page,
}, testInfo) => {
  await page.goto("/manager");
  await expect(
    page.getByRole("heading", { name: "Set up your operator workspace" }),
  ).toBeVisible();

  await answerText(
    page,
    "Northstar Goods",
    "In a sentence or two, what do you sell and who shops with you?",
  );
  await answerText(
    page,
    "Outdoor goods for weekend explorers",
    "What is the most important shopper or business outcome you want to improve?",
  );
  await answerText(
    page,
    "Improve product discovery",
    "Which agents should I set up first? Choose one or more.",
  );
  await chooseMany(
    page,
    ["Status", "Search", "Recommendations", "Buy it again"],
    "How should we handle the product catalog for now?",
  );
  await choose(
    page,
    /No data yet/,
    "Do you want to provide pseudonymous engagement events now?",
  );
  await choose(
    page,
    "Skip for now",
    "How should the agent handle proposed changes?",
  );
  await choose(
    page,
    /Draft only/,
    "Review the setup summary. Is it ready to use?",
  );
  await expect(page.getByText("Review your workspace")).toBeVisible();
  await page.getByRole("button", { name: "Open workspace" }).click();

  await expect(page.getByText("Good to see you.")).toBeVisible();
  await expect(page.getByText("Limited exploration mode")).toBeVisible();
  for (const channel of [
    "#onboarding",
    "#search",
    "#recommendations",
    "#buy-it-again",
  ])
    await expect(page.getByRole("button", { name: channel })).toBeVisible();

  await page.getByRole("button", { name: "Create agent" }).first().click();
  await page.getByLabel("Agent name").fill("Seasonal launch");
  await page.getByLabel("Purpose").fill("Plan spring discovery");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create agent" })
    .click();
  await expect(
    page.getByRole("button", { name: "#seasonal-launch" }),
  ).toBeVisible();

  let messageRequests = 0;
  await page.route(
    "**/api/runtime/v1/manager/threads/*/runs",
    async (route) => {
      messageRequests += 1;
      if (messageRequests === 1)
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 1200));
      await route.fallback();
    },
  );

  await page.getByRole("button", { name: "#search" }).click();
  const composer = page.getByRole("textbox", {
    name: "Message the commerce agent",
  });
  await composer.fill("Enable semantic search and rank products by popularity");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Sending")).toBeVisible();
  await expect(page.getByText("Search agent is working")).toBeVisible();
  await page.getByRole("button", { name: "#recommendations" }).click();
  await page
    .getByRole("textbox", { name: "Message the commerce agent" })
    .fill("Draft a product-page recommendations objective");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText(/prioritize similar products/i).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "#search" }).click();
  await expect(
    page.getByText(/hybrid hash-baseline configuration/i).first(),
  ).toBeVisible();
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach catalog CSV" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(
    resolve(process.cwd(), "public/sample-catalog.csv"),
  );
  await expect(
    page.getByText("sample-catalog.csv", { exact: true }).first(),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Reply to assistant message" })
    .first()
    .click();
  await expect(page.getByText("Original message")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Reply to thread" })
    .fill("Keep relevance first");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(
    page.getByText("Keep relevance first", { exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("manager-1440x1000.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Close thread" }).click();
  await page.getByRole("button", { name: "#seasonal-launch" }).click();
  await page.getByRole("button", { name: "Agent actions" }).click();
  await page.getByRole("menuitem", { name: "Clear agent history" }).click();
  await page.getByRole("button", { name: "Clear history" }).click();
  await expect(page.getByText(/History cleared/).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open agent navigation" }).click();
  await expect(
    page.getByRole("button", { name: "#buy-it-again" }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("manager-390x844.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "#status" }).click();
  await expect(page.getByRole("button", { name: "Toggle service details" })).toBeVisible();
  await page.getByRole("button", { name: "Toggle service details" }).click();
  await expect(page.getByText("PostgreSQL", { exact: true })).toBeVisible();
  await expect(page.getByText("Loading conversation...", { exact: true })).toBeHidden();
  await expect(page.getByText(/This channel tracks live runtime and shopper-surface health/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("manager-status-390x844.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: testInfo.outputPath("manager-status-1440x1000.png"), fullPage: true });
  await page.getByRole("button", { name: "Open details panel" }).click();
  await page.getByRole("tab", { name: "Model", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Search ranking", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Build candidate" })).toBeDisabled();
  await page.screenshot({ path: testInfo.outputPath("ranking-1440x1000.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Build candidate" })).toBeVisible();
  expect(await page.getByRole("tabpanel").evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("ranking-390x844.png") });
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Shopify", exact: true })).toBeVisible();
  const api = process.env.OPEN_COMMERCE_E2E_API_URL;
  if (api) {
    const createdRule = await page.request.post(`${api}/v1/manager/activity/rules`, {
      headers: { "Idempotency-Key": "manager-browser-monitor" },
      data: { name: "Chat errors", query: { kind: "chat" }, metric: "error_rate", threshold: 10, minimum_samples: 5, interval_minutes: 5 },
    });
    expect(createdRule.ok()).toBe(true);
    await page.getByRole("tab", { name: "Activity", exact: true }).click();
    const activity = page.getByRole("region", { name: "Store activity" });
    await expect(activity.getByText("Chat errors", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("manager-activity-390x844.png") });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await activity.getByText("Chat errors", { exact: true }).click();
    await activity.getByRole("button", { name: "Pause Chat errors" }).click();
    await expect(activity.getByText("paused", { exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("manager-activity-1440x1000.png") });
  }
});
