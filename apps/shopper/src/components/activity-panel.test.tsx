import { OpenCommerceApiError, type ActivityOverview, type ActivityRule } from "@open-commerce/sdk-typescript";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { isSessionExpired, ShopperSessionErrors } from "@/lib/session-errors";
import { expect, it, vi } from "vitest";
import { ActivityPanel } from "./activity-panel";

const overview: ActivityOverview = {
    scope: "my_activity",
    observed_counts: { search: 1 },
    available_kinds: ["search"], available_fields: ["kind", "status", "result_count"],
    checked_at: "2026-09-10T12:00:00Z",
    events: [{ id: "event-1", kind: "search", status: "ok", duration_ms: 15, result_count: 0, occurred_at: "2026-09-10T12:00:00Z" }],
    rules: [{
      id: "rule-1", definition: { name: "Empty searches", query: { kind: "search" }, metric: "empty_result_rate", threshold: 25, enabled: true },
      check: { checked_at: "2026-09-10T12:00:00Z", state: "insufficient_data", sample_count: 1 },
    }],
};

it.each(["read", "monitor"])("stops requests after handled %s expiry", async (operation) => {
  vi.useFakeTimers();
  try {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    const client = {
      shopperActivity: vi.fn<() => Promise<ActivityOverview>>().mockResolvedValue(overview),
      configureShopperActivity: vi.fn().mockRejectedValue(failure),
    };
    if (operation === "read") client.shopperActivity.mockRejectedValueOnce(failure);
    const view = render(<ShopperSessionErrors.Provider value={handle}><ActivityPanel client={client} /></ShopperSessionErrors.Provider>);
    await act(async () => undefined);
    if (operation === "monitor") {
      fireEvent.click(screen.getByText("Empty searches"));
      fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
      await act(async () => undefined);
    }
    expect(handle).toHaveBeenCalledExactlyOnceWith(failure);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => vi.advanceTimersByTimeAsync(30000));
    fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
    await act(async () => undefined);
    expect(client.shopperActivity).toHaveBeenCalledTimes(1);
    expect(client.configureShopperActivity).toHaveBeenCalledTimes(operation === "read" ? 0 : 1);
    view.unmount();
  } finally { vi.useRealTimers(); }
});

it.each([403, 500])("keeps ordinary read and monitor %s errors local", async (status) => {
  const failure = new OpenCommerceApiError(status, null);
  const handle = vi.fn(isSessionExpired);
  const client = {
    shopperActivity: vi.fn<() => Promise<ActivityOverview>>().mockRejectedValueOnce(failure).mockResolvedValue(overview),
    configureShopperActivity: vi.fn().mockRejectedValue(failure),
  };
  render(<ShopperSessionErrors.Provider value={handle}><ActivityPanel client={client} /></ShopperSessionErrors.Provider>);
  expect(await screen.findByRole("alert")).toHaveTextContent("Activity is unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  await screen.findByText("Empty searches");
  fireEvent.click(screen.getByText("Empty searches"));
  fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The monitor could not be updated");
  expect(handle).toHaveBeenCalledTimes(2);
  expect(client.shopperActivity).toHaveBeenCalledTimes(2);
  expect(client.configureShopperActivity).toHaveBeenCalledOnce();
});

it.each(["read", "monitor"])("ignores an old provider's delayed %s expiry", async (operation) => {
  let reject!: (reason: Error) => void;
  const oldHandle = vi.fn(isSessionExpired);
  const nextHandle = vi.fn(isSessionExpired);
  const client = {
    shopperActivity: vi.fn<() => Promise<ActivityOverview>>().mockResolvedValue(overview),
    configureShopperActivity: vi.fn<() => Promise<ActivityRule>>(),
  };
  if (operation === "read") client.shopperActivity.mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; }));
  else client.configureShopperActivity.mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; }));
  const view = render(<ShopperSessionErrors.Provider value={oldHandle}><ActivityPanel client={client} /></ShopperSessionErrors.Provider>);
  if (operation === "monitor") {
    fireEvent.click(await screen.findByText("Empty searches"));
    fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
  }
  view.rerender(<ShopperSessionErrors.Provider value={nextHandle}><ActivityPanel client={client} /></ShopperSessionErrors.Provider>);
  await act(async () => reject(new OpenCommerceApiError(401, null)));
  expect(oldHandle).not.toHaveBeenCalled();
  expect(nextHandle).not.toHaveBeenCalled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(client.shopperActivity).toHaveBeenCalledTimes(2);
});

it("does not refresh after a monitor response arrives after unmount", async () => {
  let finish!: (result: ActivityRule) => void;
  const handle = vi.fn(isSessionExpired);
  const client = {
    shopperActivity: vi.fn(async () => overview),
    configureShopperActivity: vi.fn(() => new Promise<ActivityRule>((resolve) => { finish = resolve; })),
  };
  const view = render(<ShopperSessionErrors.Provider value={handle}><ActivityPanel client={client} /></ShopperSessionErrors.Provider>);
  fireEvent.click(await screen.findByText("Empty searches"));
  fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
  view.unmount();
  await act(async () => finish(overview.rules[0]));
  expect(handle).not.toHaveBeenCalled();
  expect(client.shopperActivity).toHaveBeenCalledTimes(1);
  expect(client.configureShopperActivity).toHaveBeenCalledOnce();
});

it("shows real observations, filters a view, pauses monitoring, and retains failures", async () => {
  const client = {
    shopperActivity: vi.fn(async () => overview),
    configureShopperActivity: vi.fn(async () => overview.rules[0]),
  };
  render(<ActivityPanel client={client} />);
  expect(await screen.findByText("insufficient data")).toBeVisible();
  fireEvent.click(screen.getByText("Empty searches"));
  expect(screen.getByText("15 ms · 0 results")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "View events" }));
  await waitFor(() => expect(client.shopperActivity).toHaveBeenCalledWith({ kind: "search" }));
  fireEvent.click(screen.getByRole("button", { name: "Pause Empty searches" }));
  await waitFor(() => expect(client.configureShopperActivity).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Empty searches", enabled: false }), expect.any(String)));
  client.shopperActivity.mockResolvedValueOnce({ ...overview, rules: [{
    ...overview.rules[0], check: { ...overview.rules[0].check, state: "ok" },
    next_check_at: new Date(Date.now() - 120000).toISOString(),
  }] });
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  expect(await screen.findByText("check overdue")).toBeVisible();
  client.shopperActivity.mockRejectedValueOnce(new Error("unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Activity is unavailable");
});
