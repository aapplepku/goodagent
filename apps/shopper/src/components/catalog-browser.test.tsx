import { OpenCommerceApiError, type CatalogBrowseResponse } from "@open-commerce/sdk-typescript";
import { isSessionExpired, ShopperSessionErrors } from "@/lib/session-errors";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CatalogBrowser } from "./catalog-browser";

const published: CatalogBrowseResponse = {
  catalog: {
    id: "catalog-a",
    filename: "amazon.csv",
    source_version: "sha256:abc",
    product_count: 1,
    published_at: "2026-09-09T12:00:00Z",
  },
  indexing: { status: "ready" },
  categories: ["Grocery"],
  total: 1,
  offset: 0,
  limit: 24,
  items: [
    {
      product_id: "coffee",
      title: "Amazon Coffee",
      description: "Roasted coffee",
      brand: "AmazonFresh",
      category: "Grocery",
      image_url: "/abo-images/coffee.jpg",
      variant_id: "coffee-1",
      price: { amount_minor: 1299, currency: "USD" },
      availability: "available",
      provenance: null,
    },
  ],
};

describe("CatalogBrowser", () => {
  it.each([0, 1, 2])("uses the matching product noun for %s catalog entries", async (count) => {
    const data = { ...published, catalog: { ...published.catalog!, product_count: count }, total: count };
    const client = { shopperCatalog: vi.fn(async () => data) };
    render(<CatalogBrowser client={client} pendingProduct={null} onAdd={vi.fn()} onAsk={vi.fn()} storeName="Test store" />);
    const noun = count === 1 ? "product" : "products";
    expect(await screen.findByText(`${count} ${noun} at Test store`)).toBeVisible();
    expect(screen.getByText(`${count} ${noun}`, { exact: true })).toBeVisible();
  });

  it("does not describe old results as matches for a pending or failed filter", async () => {
    let reject!: (cause: Error) => void;
    const client = { shopperCatalog: vi.fn<() => Promise<CatalogBrowseResponse>>()
      .mockResolvedValueOnce(published)
      .mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; }))
      .mockResolvedValue({ ...published, total: 0, items: [] }) };
    render(<CatalogBrowser client={client} pendingProduct={null} onAdd={vi.fn()} onAsk={vi.fn()} />);
    await screen.findByRole("heading", { name: "Amazon Coffee" });
    fireEvent.change(screen.getByLabelText("Find catalog products"), { target: { value: "tea" } });
    fireEvent.click(screen.getByLabelText("Find products"));
    expect(await screen.findByText("Updating results...")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Amazon Coffee" })).toBeVisible();
    expect(screen.getByLabelText("Add Amazon Coffee to cart")).toBeDisabled();
    expect(screen.queryByText(/matching filters/)).not.toBeInTheDocument();
    await act(async () => reject(new Error("Temporary catalog failure")));
    expect(await screen.findByText("Previous results")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Showing last loaded data.");
    expect(screen.queryByText(/matching filters/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Refresh catalog"));
    expect(await screen.findByText("0 products matching filters")).toBeVisible();
    expect(screen.queryByText("Previous results")).not.toBeInTheDocument();
  });

  it.each([401, 403, 500])("delegates %s and stops polling only for handled expiry", async (status) => {
    vi.useFakeTimers();
    try {
      const failure = new OpenCommerceApiError(status, null);
      const handle = vi.fn(isSessionExpired);
      const client = { shopperCatalog: vi.fn().mockRejectedValue(failure) };
      const onAdd = vi.fn();
      const view = render(<ShopperSessionErrors.Provider value={handle}>
        <CatalogBrowser client={client} pendingProduct={null} onAdd={onAdd} onAsk={vi.fn()} />
      </ShopperSessionErrors.Provider>);
      await act(async () => undefined);
      expect(handle).toHaveBeenCalledExactlyOnceWith(failure);
      if (status === 401) expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      else expect(screen.getByRole("alert")).toHaveTextContent(failure.message);
      await act(async () => vi.advanceTimersByTimeAsync(30000));
      expect(client.shopperCatalog).toHaveBeenCalledTimes(status === 401 ? 1 : 7);
      expect(onAdd).not.toHaveBeenCalled();
      view.unmount();
    } finally { vi.useRealTimers(); }
  });

  it("keeps an unhandled 401 local", async () => {
    const handle = vi.fn(() => false);
    const failure = new OpenCommerceApiError(401, null);
    render(<ShopperSessionErrors.Provider value={handle}>
      <CatalogBrowser client={{ shopperCatalog: vi.fn().mockRejectedValue(failure) }} pendingProduct={null} onAdd={vi.fn()} onAsk={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    expect(await screen.findByRole("alert")).toHaveTextContent(failure.message);
    expect(handle).toHaveBeenCalledExactlyOnceWith(failure);
  });

  it("ignores a prior provider's delayed expiry", async () => {
    let reject!: (reason: Error) => void;
    const oldHandle = vi.fn(isSessionExpired);
    const nextHandle = vi.fn(isSessionExpired);
    const client = { shopperCatalog: vi.fn<() => Promise<CatalogBrowseResponse>>().mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; })).mockResolvedValue(published) };
    const props = { client, pendingProduct: null, onAdd: vi.fn(), onAsk: vi.fn() };
    const view = render(<ShopperSessionErrors.Provider value={oldHandle}><CatalogBrowser {...props} /></ShopperSessionErrors.Provider>);
    view.rerender(<ShopperSessionErrors.Provider value={nextHandle}><CatalogBrowser {...props} /></ShopperSessionErrors.Provider>);
    expect(await screen.findByText("1 product from amazon.csv")).toBeVisible();
    await act(async () => reject(new OpenCommerceApiError(401, null)));
    expect(oldHandle).not.toHaveBeenCalled();
    expect(nextHandle).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(client.shopperCatalog).toHaveBeenCalledTimes(2);
  });

  it("shows GoodAgent branding alongside the unchanged merchant store name", async () => {
    const client = { shopperCatalog: vi.fn(async () => published) };
    render(<CatalogBrowser client={client} pendingProduct={null} onAdd={vi.fn()} onAsk={vi.fn()} storeName="Open Commerce Shop" />);
    expect(await screen.findByText("1 product at Open Commerce Shop")).toBeVisible();
    expect(screen.getByText("GoodAgent Shop")).toBeVisible();
  });

  it.each([false, true])(
    "clears an empty stock filter with other filters enabled: %s",
    async (withOtherFilters) => {
      const client = {
        shopperCatalog: vi.fn(async (input: { in_stock?: boolean } = {}) =>
          input.in_stock ? { ...published, total: 0, items: [] } : published,
        ),
      };
      render(
        <CatalogBrowser
          client={client}
          pendingProduct={null}
          onAdd={vi.fn()}
          onAsk={vi.fn()}
        />,
      );
      await screen.findByRole("heading", { name: "Amazon Coffee" });
      if (withOtherFilters) {
        fireEvent.change(screen.getByLabelText("Find catalog products"), {
          target: { value: "coffee" },
        });
        fireEvent.click(screen.getByLabelText("Find products"));
        fireEvent.change(screen.getByLabelText("Category"), {
          target: { value: "Grocery" },
        });
        fireEvent.change(screen.getByLabelText("Sort products"), {
          target: { value: "price_desc" },
        });
      }
      fireEvent.click(screen.getByLabelText("In stock"));
      expect(await screen.findByText("No matching products")).toBeVisible();
      expect(screen.getByText("0 products matching filters")).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
      expect(screen.getByLabelText("In stock")).not.toBeChecked();
      expect(screen.getByLabelText("Find catalog products")).toHaveValue("");
      expect(screen.getByLabelText("Category")).toHaveValue("");
      expect(screen.getByLabelText("Sort products")).toHaveValue(
        withOtherFilters ? "price_desc" : "title",
      );
      await waitFor(() =>
        expect(client.shopperCatalog).toHaveBeenLastCalledWith(
          expect.objectContaining({
            q: "", category: "", in_stock: false, offset: 0,
            sort: withOtherFilters ? "price_desc" : "title",
          }),
        ),
      );
      expect(await screen.findByRole("heading", { name: "Amazon Coffee" })).toBeVisible();
      expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument();
    },
  );
  it("polls ready catalogs slowly without disabling cart actions during background work", async () => {
    vi.useFakeTimers();
    try {
      const client = { shopperCatalog: vi.fn(async () => published) };
      const onAdd = vi.fn();
      const rendered = render(<CatalogBrowser client={client} pendingProduct={null} onAdd={onAdd} onAsk={vi.fn()} />);
      await act(async () => undefined);
      await act(async () => vi.advanceTimersByTimeAsync(5000));
      expect(client.shopperCatalog).toHaveBeenCalledTimes(1);
      let finish!: (value: CatalogBrowseResponse) => void;
      client.shopperCatalog.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
      await act(async () => vi.advanceTimersByTimeAsync(25000));
      expect(client.shopperCatalog).toHaveBeenCalledTimes(2);
      expect(screen.getByLabelText("Add Amazon Coffee to cart")).toBeEnabled();
      fireEvent.click(screen.getByLabelText("Add Amazon Coffee to cart"));
      expect(onAdd).toHaveBeenCalledWith({ product_id: "coffee" });
      await act(async () => finish(published));
      rendered.unmount();
    } finally { vi.useRealTimers(); }
  });
  it("shows products, filters and requires explicit cart or assistant actions", async () => {
    const client = { shopperCatalog: vi.fn(async () => published) };
    const onAdd = vi.fn(async () => undefined);
    const onAsk = vi.fn();
    render(
      <CatalogBrowser
        client={client}
        pendingProduct={null}
        onAdd={onAdd}
        onAsk={onAsk}
      />,
    );
    expect(await screen.findByText("1 product from amazon.csv")).toBeVisible();
    expect(screen.getByRole("img", { name: "Amazon Coffee" })).toBeVisible();
    expect(onAdd).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Add Amazon Coffee to cart"));
    // The display variant must not count as an explicit shopper selection.
    expect(onAdd).toHaveBeenCalledWith({ product_id: "coffee" });
    fireEvent.click(screen.getByText("Details"));
    fireEvent.click(screen.getByText("Ask the assistant"));
    expect(onAsk).toHaveBeenCalledWith(
      expect.stringContaining("product coffee"),
    );
    fireEvent.change(screen.getByLabelText("Category"), {
      target: { value: "Grocery" },
    });
    await waitFor(() =>
      expect(client.shopperCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: "Grocery", offset: 0 }),
      ),
    );
  });

  it("keeps the published catalog during a failed update, disables unavailable products", async () => {
    const client = {
      shopperCatalog: vi.fn(async () => ({
        ...published,
        indexing: { status: "failed" as const },
        items: published.items.map((item) => ({
          ...item,
          availability: "unknown" as const,
        })),
      })),
    };
    render(
      <CatalogBrowser
        client={client}
        pendingProduct={null}
        onAdd={vi.fn()}
        onAsk={vi.fn()}
      />,
    );
    expect(
      await screen.findByText(/previous catalog is still available/),
    ).toBeVisible();
    expect(screen.getByLabelText("Add Amazon Coffee to cart")).toBeDisabled();
    expect(screen.getByText("Availability unconfirmed")).toBeVisible();
  });

  it("does not invent products while the first upload is indexing", async () => {
    const client = {
      shopperCatalog: vi.fn(async () => ({
        ...published,
        catalog: null,
        items: [],
        total: 0,
        indexing: { status: "queued" as const, product_count: 48 },
      })),
    };
    render(
      <CatalogBrowser
        client={client}
        pendingProduct={null}
        onAdd={vi.fn()}
        onAsk={vi.fn()}
      />,
    );
    expect(
      await screen.findByText("The shelves are not ready yet"),
    ).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "48");
    expect(
      screen.queryByLabelText("Add Amazon Coffee to cart"),
    ).not.toBeInTheDocument();
  });
});
