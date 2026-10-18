import type { ActivityOverview } from "@open-commerce/sdk-typescript";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ActivityPanel } from "./activity-panel";

it("shows real observations, filters a view, pauses monitoring, and retains failures", async () => {
  const overview: ActivityOverview = {
    scope: "store_activity",
    observed_counts: { search: 1 },
    available_kinds: ["search"], available_fields: ["kind", "status", "result_count"],
    checked_at: "2026-09-10T12:00:00Z",
    events: [{ id: "event-1", kind: "search", status: "ok", duration_ms: 15, result_count: 0, occurred_at: "2026-09-10T12:00:00Z" }],
    rules: [{
      id: "rule-1", definition: { name: "Empty searches", query: { kind: "search" }, metric: "empty_result_rate", threshold: 25, enabled: true },
      check: { checked_at: "2026-09-10T12:00:00Z", state: "insufficient_data", sample_count: 1 },
    }],
  };
  const client = {
    managerActivity: vi.fn(async () => overview),
    configureManagerActivity: vi.fn(async () => overview.rules[0]),
  };
  render(<ActivityPanel client={client} />);
  expect(await screen.findByText("insufficient data")).toBeVisible();
  fireEvent.click(screen.getByText("Empty searches"));
  expect(screen.getByText("15 ms · 0 results")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "View events" }));
  await waitFor(() => expect(client.managerActivity).toHaveBeenCalledWith({ kind: "search" }));
  fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
  await waitFor(() => expect(client.configureManagerActivity).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Empty searches", enabled: false }), expect.any(String)));
  client.managerActivity.mockResolvedValueOnce({ ...overview, rules: [{
    ...overview.rules[0], check: { ...overview.rules[0].check, state: "ok" },
    next_check_at: new Date(Date.now() - 120000).toISOString(),
  }] });
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  expect(await screen.findByText("check overdue")).toBeVisible();
  client.managerActivity.mockRejectedValueOnce(new Error("unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Activity is unavailable");
});
