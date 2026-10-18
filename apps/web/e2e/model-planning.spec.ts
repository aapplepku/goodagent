import { expect, test } from "@playwright/test";

test("reviewed revision preserves changed values and model unavailability never falls back", async ({
  page,
  request,
}, testInfo) => {
  const created = await request.post("/api/runtime/v1/goals", {
    data: { name: "Reviewed revision browser test", seed: 117 },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
  expect(created.status()).toBe(201);
  const original = await created.json();
  const id: string = original.spec.id;
  try {
    await page.goto(`/lab?goal=${id}`);
    await expect(page.getByLabel("Saved goal")).toHaveValue(id);
    const revise = page.getByRole("button", {
      name: "Apply and activate revision 2",
      exact: true,
    });
    await expect(revise).toBeDisabled();
    await page
      .getByLabel("Natural-language draft")
      .fill(
        "Acquire 7000 new customers in 20 days with a $8000 budget. No discounts.",
      );
    await page.getByRole("button", { name: "Draft", exact: true }).click();
    await expect(revise).toBeEnabled();
    await page.getByText("New goal review", { exact: true }).click();
    await expect(
      page
        .locator("#goal-config details")
        .filter({ hasText: "New goal review" }),
    ).toContainText('"7000"');
    await revise.click();
    await expect(
      page.getByText(
        "Reviewed revision activated; stale proposals and pending approvals invalidated.",
        { exact: true },
      ),
    ).toBeVisible();
    const updated = await (
      await request.get(`/api/runtime/v1/goals/${id}`)
    ).json();
    expect(updated.revision).toBe(2);
    expect(updated.spec.objective.target).toBe("7000");
    expect(updated.spec.allowed_action_types).not.toContain("create_discount");
    expect(
      Date.parse(updated.spec.horizon.end_at) -
        Date.parse(updated.spec.horizon.start_at),
    ).toBe(20 * 86400000);
    await page.reload();
    await expect(
      page.getByRole("button", {
        name: "Apply and activate revision 3",
        exact: true,
      }),
    ).toBeDisabled();
    await page.getByLabel("Planning mode").selectOption("model_backed");
    const unavailable = page.waitForResponse(
      (response) =>
        response.url().endsWith("/v1/goals/draft") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Draft", exact: true }).click();
    expect((await unavailable).status()).toBe(503);
    await expect(
      page.getByRole("button", { name: "Activate and run", exact: true }),
    ).toBeDisabled();
    await expect(page.getByLabel("Planning mode")).toHaveValue("model_backed");
    expect(
      (await (await request.get(`/api/runtime/v1/goals/${id}`)).json())
        .planning_mode,
    ).toBe("deterministic");
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: testInfo.outputPath(`model-review-${width}.png`),
        fullPage: true,
      });
    }
  } finally {
    await request.post(`/api/runtime/v1/goals/${id}/archive`, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  }
});
