import type { CatalogIndexStatus, ImportReview, StoreReadiness } from "@open-commerce/sdk-typescript";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StoreAccess } from "@/components/store-setup";
import { deferred, denied, expectBinding, merchantServer, ownerA } from "./merchant-test-server";

type Snapshot = { state: StoreReadiness; review: ImportReview };
function candidate(id = "import-b", catalog = "catalog-b", status: CatalogIndexStatus["status"] = "ready"): Snapshot {
  const indexing: CatalogIndexStatus = {
    catalog_id: catalog, status, product_count: 2, indexed_product_count: status === "ready" ? 2 : 0,
    filename: "historical-original.csv",
  };
  return {
    state: {
      store: { ...ownerA.store, sharing_enabled: true, published_catalog_id: "catalog-a" },
      latest_import_id: id, indexing, image_failures: 0,
      checklist: { catalog_verified: status === "ready", search_tested: true, sharing_enabled: true },
    },
    review: {
      id, catalog_id: catalog, status: "confirmed", filename: `${id}.csv`,
      expires_at: "2099-01-01T00:00:00Z", mapping: { title: "title" }, columns: ["title", "name"],
      currency: "USD", row_count: 2, product_count: 2, indexing: { ...indexing },
    },
  };
}
function setup(initial = candidate()) {
  const model = {
    snapshot: initial,
    intercept: undefined as ((request: Request) => Response | Promise<Response> | undefined) | undefined,
  };
  const server = merchantServer((request) => {
    const intercepted = model.intercept?.(request);
    if (intercepted) return intercepted;
    const path = new URL(request.url).pathname;
    if (path.endsWith("/measurements")) return Response.json({});
    if (path.endsWith("/merchant/store")) return Response.json(model.snapshot.state);
    if (path.includes("/imports/")) return Response.json(model.snapshot.review);
    if (path.endsWith("/preview")) return Response.json({ token: "synthetic-preview", store_slug: ownerA.store.slug });
    if (path.endsWith("/sharing")) return Response.json({});
    return denied(404);
  });
  return { model, server };
}
async function mount(filename: string) {
  const result = render(<StoreAccess><p>Workspace</p></StoreAccess>);
  await screen.findByRole("heading", { name: filename });
  await act(async () => {});
  return result;
}
function previewStep() { fireEvent.click(screen.getByRole("button", { name: "2 Preview" })); }
function sharingStep() { fireEvent.click(screen.getByRole("button", { name: "3 Ready to share" })); }
function acknowledge() {
  fireEvent.click(screen.getByLabelText("I reviewed the products and image issues."));
  fireEvent.click(screen.getByLabelText("Checkout is a demo. No real payments are taken."));
}
function writes(server: ReturnType<typeof merchantServer>) {
  return server.requests.filter((request) => request.method !== "GET");
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("coherent setup catalog intent", () => {
  it.each(["import-id", "catalog-id", "review-index", "pending", "cancelled", "unverified", "partial-count", "different-count", "missing-count"])(
    "blocks preview/publication/retry for %s snapshots while keeping the published link", async (problem) => {
      const input = candidate();
      if (problem === "import-id") input.review.id = "other-import";
      if (problem === "catalog-id") input.review.catalog_id = "catalog-c";
      if (problem === "review-index") input.review.indexing!.catalog_id = "catalog-c";
      if (problem === "pending") input.review.status = "review";
      if (problem === "cancelled") input.review.status = "cancelled";
      if (problem === "unverified") input.state.checklist.catalog_verified = false;
      if (problem === "partial-count") input.state.indexing.indexed_product_count = 1;
      if (problem === "different-count") input.review.indexing = { ...input.review.indexing, product_count: 3, indexed_product_count: 3 };
      if (problem === "missing-count") delete input.state.indexing.indexed_product_count;
      const { server } = setup(input);
      render(<StoreAccess><p>Workspace</p></StoreAccess>);
      await screen.findByRole("heading", { name: input.review.status === "review" ? "Review your products" : "Review your catalog update" });
      previewStep();
      expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeDisabled();
      fireEvent.click(screen.getByRole("button", { name: "Open shopper preview" }));
      expect(screen.queryByRole("button", { name: "Retry indexing" })).not.toBeInTheDocument();
      sharingStep();
      acknowledge();
      expect(screen.getByRole("button", { name: "Publish catalog update" })).toBeDisabled();
      fireEvent.click(screen.getByRole("button", { name: "Publish catalog update" }));
      expect(screen.getByRole("link", { name: "Open shared store" })).toHaveAttribute("href", "/manager/preview?store=store-a");
      expect(writes(server)).toHaveLength(0);
    },
  );

  it("uses the current reimport filename and exact reused catalog for preview and publication", async () => {
    const input = candidate("restore-a", "catalog-a");
    input.state.store.published_catalog_id = "catalog-b";
    const { server } = setup(input);
    vi.spyOn(window, "open").mockReturnValue(null);
    await mount("restore-a.csv");
    previewStep();
    expect(within(screen.getByRole("region", { name: "Selected catalog" })).getByRole("heading")).toHaveTextContent("restore-a.csv");
    expect(screen.getAllByText("restore-a.csv", { exact: true })).toHaveLength(1);
    expect(screen.queryByText("historical-original.csv")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open shopper preview" }));
    await waitFor(() => expect(server.calls("/preview")).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeEnabled());
    sharingStep();
    acknowledge();
    fireEvent.click(screen.getByRole("button", { name: "Publish catalog update" }));
    await waitFor(() => expect(server.calls("/sharing")).toHaveLength(1));
    expect(await server.calls("/preview")[0].json()).toEqual({ catalog_id: "catalog-a" });
    expect(await server.calls("/sharing")[0].json()).toMatchObject({ catalog_id: "catalog-a", enabled: true });
    writes(server).forEach((request) => expectBinding(request, ownerA));
  });

  it("commits readiness with its review and ignores an older deferred pair after a newer refresh", async () => {
    const { model, server } = setup();
    const pending = deferred<Response>();
    vi.spyOn(window, "open").mockReturnValue(null);
    await mount("import-b.csv");
    acknowledge();
    const old = candidate("restore-a", "catalog-a");
    model.snapshot = old;
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/imports/restore-a") ? pending.promise : undefined;
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(server.calls("/imports/restore-a")).toHaveLength(1));
    expect(screen.getByRole("heading", { name: "import-b.csv" })).toBeVisible();
    expect(screen.queryByText("restore-a.csv")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish catalog update" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Open shared store" })).toBeVisible();
    model.snapshot = candidate("new-d", "catalog-d");
    fireEvent(window, new Event("focus"));
    await screen.findByRole("heading", { name: "new-d.csv" });
    expect(screen.getByLabelText("I reviewed the products and image issues.")).not.toBeChecked();
    expect(screen.getByLabelText("Checkout is a demo. No real payments are taken.")).not.toBeChecked();
    await act(async () => { pending.resolve(Response.json(old.review)); });
    expect(screen.queryByText("restore-a.csv")).not.toBeInTheDocument();
    previewStep();
    fireEvent.click(screen.getByRole("button", { name: "Open shopper preview" }));
    await waitFor(() => expect(server.calls("/preview")).toHaveLength(1));
    expect(await server.calls("/preview")[0].json()).toEqual({ catalog_id: "catalog-d" });
  });

  it("does not expose an initial readiness candidate until the corresponding review arrives", async () => {
    const { model, server } = setup();
    const pending = deferred<Response>();
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/imports/import-b") ? pending.promise : undefined;
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    await waitFor(() => expect(server.calls("/imports/import-b")).toHaveLength(1));
    previewStep();
    expect(screen.queryByRole("button", { name: "Open shopper preview" })).not.toBeInTheDocument();
    expect(screen.getByText("Loading setup...")).toBeVisible();
    await act(async () => { pending.resolve(Response.json(model.snapshot.review)); });
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeEnabled();
    expect(writes(server)).toHaveLength(0);
  });

  it("keeps candidate actions blocked after a partial refresh failure until an explicit coherent refresh", async () => {
    const { model, server } = setup();
    await mount("import-b.csv");
    acknowledge();
    model.snapshot = candidate("new-c", "catalog-c");
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/imports/new-c") ? denied(503) : undefined;
    fireEvent(window, new Event("focus"));
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Publish catalog update" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Open shared store" })).toBeVisible();
    previewStep();
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeDisabled();
    model.intercept = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Refresh setup" }));
    await screen.findByRole("heading", { name: "new-c.csv" });
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeEnabled();
    sharingStep();
    expect(screen.getByLabelText("I reviewed the products and image issues.")).not.toBeChecked();
    expect(writes(server)).toHaveLength(0);
  });

  it("resumes failed B after cancelling C and retries B after reopening, without changing published A", async () => {
    const input = candidate("pending-c", "catalog-c");
    input.review.status = "review";
    input.review.catalog_id = null;
    input.review.indexing = null;
    input.state.indexing = { status: "not_configured" };
    input.state.checklist.catalog_verified = false;
    const { model, server } = setup(input);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    model.intercept = (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/pending-c/cancel")) { model.snapshot = candidate("retry-b", "catalog-b", "failed"); return Response.json({}); }
      if (path.endsWith("/retry-b/retry")) { model.snapshot = candidate("retry-b", "catalog-b", "queued"); return Response.json({}); }
    };
    const first = await mount("pending-c.csv");
    fireEvent.click(screen.getByRole("button", { name: "Cancel import" }));
    await screen.findByRole("heading", { name: "retry-b.csv" });
    expect(screen.getByRole("button", { name: "Retry indexing" })).toBeEnabled();
    first.unmount();
    await mount("retry-b.csv");
    expect(screen.getAllByText("retry-b.csv", { exact: true })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry indexing" }));
    await screen.findByText("Catalog queued for indexing");
    expect(server.calls("/retry-b/retry")).toHaveLength(1);
    expect(server.calls("/pending-c/retry")).toHaveLength(0);
    expect(model.snapshot.state.store.published_catalog_id).toBe("catalog-a");
    expect(server.calls("/sharing")).toHaveLength(0);
    writes(server).forEach((request) => expectBinding(request, ownerA));
    sharingStep();
    expect(screen.getByRole("link", { name: "Open shared store" })).toBeVisible();
  });

  it("does not offer a failed catalog retry through a newer unconfirmed or mismatched import", async () => {
    const input = candidate("pending-c", "catalog-b", "failed");
    input.review.status = "review";
    input.review.catalog_id = null;
    const { server } = setup(input);
    await mount("pending-c.csv");
    previewStep();
    expect(screen.queryByRole("button", { name: "Retry indexing" })).not.toBeInTheDocument();
    expect(screen.queryByText("Indexing needs attention")).not.toBeInTheDocument();
    expect(writes(server)).toHaveLength(0);
  });

  it("preserves a verified rename when an older candidate review completes later in the same session", async () => {
    const { model, server } = setup();
    const pending = deferred<Response>();
    await mount("import-b.csv");
    previewStep();
    let hold = true;
    model.intercept = (request) => {
      if (request.method === "PATCH") {
        model.snapshot.state.store = { ...model.snapshot.state.store, name: "Verified renamed store" };
        hold = false;
        return Response.json(model.snapshot.state.store);
      }
      if (new URL(request.url).pathname.endsWith("/imports/import-b") && hold) return pending.promise;
    };
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(server.calls("/imports/import-b")).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: "1 Products" }));
    fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "Draft name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    await waitFor(() => expect(server.calls("/imports/import-b")).toHaveLength(3));
    await act(async () => { pending.resolve(Response.json(model.snapshot.review)); });
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(await screen.findByRole("group", { name: "Current store" })).toHaveTextContent("Verified renamed store/s/store-a");
    expect(server.calls("/auth/me")).toHaveLength(1);
    server.calls("/merchant/store").forEach((request) => expectBinding(request, ownerA));
  });
});
