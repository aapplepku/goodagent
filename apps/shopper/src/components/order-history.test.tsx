import { OpenCommerceApiError, type ShopperOrderList } from "@open-commerce/sdk-typescript";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { isSessionExpired, ShopperSessionErrors } from "@/lib/session-errors";
import { describe, expect, it, vi } from "vitest";
import { OrderHistory } from "./order-history";

const page: ShopperOrderList = {
  items: [{ id: "order-1", order_number: "DEMO-1", status: "paid",
    created_at: "2026-09-13T12:00:00Z", total: { amount_minor: 3800, currency: "USD" },
    lines: [{ product_id: "mug", variant_id: "large", title: "Travel mug", quantity: 2,
      unit_price: { amount_minor: 1900, currency: "USD" }, line_total: { amount_minor: 3800, currency: "USD" } }],
  }], next_offset: 20, payment_mode: "local_test",
};

describe("demo order history", () => {
  it.each([401, 403, 500])("delegates %s and preserves only unhandled local errors", async (status) => {
    const failure = new OpenCommerceApiError(status, null);
    const handle = vi.fn(isSessionExpired);
    const client = { shopperOrders: vi.fn().mockRejectedValue(failure) };
    render(<ShopperSessionErrors.Provider value={handle}>
      <OrderHistory client={client} guest={false} onClose={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    await waitFor(() => expect(handle).toHaveBeenCalledExactlyOnceWith(failure));
    if (status === 401) expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    else expect(screen.getByRole("alert")).toHaveTextContent("Could not load demo orders");
    expect(screen.queryByText("No demo orders yet.")).not.toBeInTheDocument();
    expect(client.shopperOrders).toHaveBeenCalledTimes(1);
  });

  it.each(["replace provider", "unmount"])("ignores old expiry after %s", async (boundary) => {
    let reject!: (reason: Error) => void;
    const oldHandle = vi.fn(isSessionExpired);
    const nextHandle = vi.fn(isSessionExpired);
    const client = { shopperOrders: vi.fn<() => Promise<ShopperOrderList>>().mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; })).mockResolvedValue(page) };
    const props = { client, guest: false, onClose: vi.fn() };
    const view = render(<ShopperSessionErrors.Provider value={oldHandle}><OrderHistory {...props} /></ShopperSessionErrors.Provider>);
    if (boundary === "unmount") view.unmount();
    else view.rerender(<ShopperSessionErrors.Provider value={nextHandle}><OrderHistory {...props} /></ShopperSessionErrors.Provider>);
    await act(async () => reject(new OpenCommerceApiError(401, null)));
    expect(oldHandle).not.toHaveBeenCalled();
    expect(nextHandle).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("loads durable orders on every open and supports older pages without duplicate rows", async () => {
    const client = { shopperOrders: vi.fn(async (): Promise<ShopperOrderList> => page) };
    const first = render(<OrderHistory client={client} guest={false} onClose={vi.fn()} />);
    expect(await screen.findByText("DEMO-1")).toBeVisible();
    expect(screen.getByText(/No money charged/)).toBeVisible();
    fireEvent.click(screen.getByText("DEMO-1"));
    expect(screen.getByText("Travel mug")).toBeVisible();
    client.shopperOrders.mockResolvedValueOnce({ ...page, next_offset: null });
    fireEvent.click(screen.getByText("Show older orders"));
    await act(async () => undefined);
    expect(client.shopperOrders).toHaveBeenLastCalledWith({ limit: 20, offset: 20 });
    expect(screen.getAllByText("DEMO-1")).toHaveLength(1);
    first.unmount();
    render(<OrderHistory client={client} guest onClose={vi.fn()} />);
    expect(await screen.findByText("DEMO-1")).toBeVisible();
    expect(client.shopperOrders).toHaveBeenLastCalledWith({ limit: 20, offset: 0 });
    expect(screen.getByText(/guest visit only/)).toBeVisible();
  });

  it("distinguishes unavailable history from no orders and can retry", async () => {
    const client = { shopperOrders: vi.fn<() => Promise<ShopperOrderList>>() };
    client.shopperOrders.mockRejectedValueOnce(new Error("offline"));
    client.shopperOrders.mockResolvedValue({ items: [], next_offset: null, payment_mode: "local_test" });
    render(<OrderHistory client={client} guest={false} onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load");
    expect(screen.queryByText("No demo orders yet.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Retry orders"));
    expect(await screen.findByText("No demo orders yet.")).toBeVisible();
  });

  it("ignores a prior account response after unmount", async () => {
    let finish!: (value: ShopperOrderList) => void;
    const first = render(<OrderHistory client={{ shopperOrders: () => new Promise((resolve) => { finish = resolve; }) }} guest={false} onClose={vi.fn()} />);
    first.unmount();
    render(<OrderHistory client={{ shopperOrders: async () => ({ items: [] }) }} guest={false} onClose={vi.fn()} />);
    await act(async () => finish(page));
    expect(await screen.findByText("No demo orders yet.")).toBeVisible();
    expect(screen.queryByText("DEMO-1")).not.toBeInTheDocument();
  });
});
