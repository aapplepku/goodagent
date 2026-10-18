import type { CatalogBrowseResponse } from "@open-commerce/sdk-typescript";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ManagerCatalog } from "@/components/manager-catalog";
import { StoreNavigationContext } from "@/components/store-navigation";

const published: CatalogBrowseResponse = {
  catalog: {
    id: "catalog-a",
    filename: "amazon.csv",
    source_version: "sha256:abc",
    product_count: 48,
    published_at: "2026-09-09T12:00:00Z",
  },
  indexing: { status: "ready" },
  categories: ["Grocery", "Lighting"],
  total: 48,
  offset: 0,
  limit: 24,
  items: [
    {
      product_id: "lamp",
      title: "Amazon Reading Lamp",
      description: "A reading light",
      brand: "AmazonBasics",
      category: "Lighting",
      image_url: "/abo-images/lamp.jpg",
      variant_id: "lamp-1",
      price: { amount_minor: 4900, currency: "USD" },
      availability: "available",
      provenance: "Test source",
    },
  ],
};

describe("ManagerCatalog", () => {
  it("clears private catalog data and stops polling after session expiration", async () => {
    vi.useFakeTimers();
    try {
      const expired = vi.fn();
      const client = { managerCatalog: vi.fn<() => Promise<CatalogBrowseResponse>>().mockResolvedValueOnce(published)
        .mockRejectedValue(new OpenCommerceApiError(401, null)) };
      render(<StoreNavigationContext.Provider value={{ openProducts: vi.fn(), onSessionExpired: expired }}>
        <ManagerCatalog client={client} />
      </StoreNavigationContext.Provider>);
      await act(async () => {});
      expect(screen.getByRole("heading", { name: "Amazon Reading Lamp" })).toBeVisible();
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(screen.queryByRole("heading", { name: "Amazon Reading Lamp" })).not.toBeInTheDocument();
      expect(expired).toHaveBeenCalledOnce();
      await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
      expect(client.managerCatalog).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
  it("automatically refreshes publication and handles unsafe image URLs", async () => {
    vi.useFakeTimers();
    try {
      const client = {
        managerCatalog: vi
          .fn<() => Promise<CatalogBrowseResponse>>()
          .mockResolvedValue({
            ...published,
            catalog: null,
            items: [],
            indexing: { status: "queued" },
          }),
      };
      render(<ManagerCatalog client={client} />);
      await act(async () => {});
      expect(screen.getByText("No indexed products yet")).toBeVisible();
      client.managerCatalog.mockResolvedValue({
        ...published,
        items: [{ ...published.items[0], image_url: "javascript:alert(1)" }],
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(
        screen.getByRole("heading", { name: "Amazon Reading Lamp" }),
      ).toBeVisible();
      expect(screen.getByText("Image unavailable")).toBeVisible();
      expect(client.managerCatalog).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
  it("shows source, product images and details; filters and pages server-side", async () => {
    const client = { managerCatalog: vi.fn(async () => published) };
    render(<ManagerCatalog client={client} />);
    expect(
      await screen.findByText("48 products in the indexed catalog"),
    ).toBeVisible();
    expect(screen.getByText("GoodAgent", { exact: false })).toHaveTextContent("GoodAgent / Catalog");
    expect(
      screen.getByRole("img", { name: "Amazon Reading Lamp" }),
    ).toHaveAttribute("src", expect.stringContaining("/abo-images/lamp.jpg"));
    fireEvent.click(screen.getByText("Source and indexing details"));
    expect(screen.getByText("sha256:abc")).toBeVisible();
    fireEvent.click(screen.getByText("Product details"));
    expect(screen.getByText("A reading light")).toBeVisible();
    client.managerCatalog.mockResolvedValue({ ...published, offset: 24 });
    fireEvent.click(screen.getByLabelText("Next page"));
    await waitFor(() =>
      expect(client.managerCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 24 }),
      ),
    );
    client.managerCatalog.mockResolvedValue({
      ...published,
      offset: 0,
      total: 1,
    });
    fireEvent.change(screen.getByLabelText("Category"), {
      target: { value: "Lighting" },
    });
    await waitFor(() =>
      expect(client.managerCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: "Lighting", offset: 0 }),
      ),
    );
    fireEvent.change(screen.getByLabelText("Find catalog products"), {
      target: { value: "lamp" },
    });
    fireEvent.click(screen.getByLabelText("Find products"));
    await waitFor(() =>
      expect(client.managerCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "lamp" }),
      ),
    );
  });

  it("keeps old products during indexing and replaces them when published", async () => {
    const client = {
      managerCatalog: vi
        .fn<() => Promise<CatalogBrowseResponse>>()
        .mockResolvedValue({
          ...published,
          indexing: {
            status: "running" as const,
            filename: "new.csv",
            product_count: 2,
            indexed_product_count: 0,
          },
        }),
    };
    render(<ManagerCatalog client={client} />);
    expect(
      await screen.findByRole("heading", { name: "Amazon Reading Lamp" }),
    ).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
    expect(screen.getByText(/Current catalog remains available/)).toBeVisible();
    client.managerCatalog.mockResolvedValue({
      ...published,
      catalog: {
        ...published.catalog!,
        id: "catalog-b",
        filename: "new.csv",
        product_count: 1,
      },
      items: [
        { ...published.items[0], product_id: "coffee", title: "New Coffee" },
      ],
      total: 1,
      indexing: {
        status: "ready",
        filename: "new.csv",
        product_count: 1,
        indexed_product_count: 1,
      },
    });
    fireEvent.click(screen.getByLabelText("Refresh catalog"));
    expect(
      await screen.findByRole("heading", { name: "New Coffee" }),
    ).toBeVisible();
    expect(
      screen.getByText("1 products in the indexed catalog"),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Amazon Reading Lamp" }),
    ).not.toBeInTheDocument();
  });

  it("shows an unavailable API and permits retry without claiming an empty catalog", async () => {
    const client = {
      managerCatalog: vi
        .fn<() => Promise<CatalogBrowseResponse>>()
        .mockRejectedValueOnce(new Error("API unavailable"))
        .mockResolvedValue(published),
    };
    render(<ManagerCatalog client={client} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "API unavailable",
    );
    expect(screen.queryByText("No indexed products yet")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Refresh catalog"));
    expect(
      await screen.findByRole("heading", { name: "Amazon Reading Lamp" }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
