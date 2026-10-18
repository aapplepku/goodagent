import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ImportReview,
  OwnerAuthResponse,
  StoreReadiness,
} from "@open-commerce/sdk-typescript";
import { StoreAccess } from "@/components/store-setup";
import { useStoreNavigation } from "@/components/store-navigation";

const owner: OwnerAuthResponse = {
  user_id: "owner",
  store: { id: "store", slug: "test-store", name: "Test store", readiness: {} },
};
const readiness: StoreReadiness = {
  store: owner.store,
  indexing: { status: "not_configured" },
  image_failures: 0,
  latest_import_id: null,
  checklist: {
    catalog_verified: false,
    ai_verified: false,
    sharing_enabled: false,
  },
};
afterEach(() => vi.unstubAllGlobals());

describe("self-service store setup", () => {
  it("puts resumed import review first without discarding editable store details", async () => {
    pendingImport();
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    expect(await screen.findByRole("heading", { name: "Review your products" })).toBeVisible();
    expect(screen.getByText("GoodAgent")).toBeVisible();
    const source = screen.getByText("Store details and catalog source").closest("details")!;
    expect(source).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Confirm products" })).toBeVisible();
    expect(screen.getByText("Edit field mapping and currency").closest("details")).not.toHaveAttribute("open");
    source.open = true;
    expect(screen.getByLabelText("Store name")).toHaveValue("Test store");
  });
  it("distinguishes an enabled catalog from an unpublished replacement", async () => {
    let catalogId = "published";
    let tested = true;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({ profile: "self_hosted", setup_required: false });
      if (input.endsWith("/auth/me")) return Response.json(owner);
      if (input.endsWith("/measurements")) return Response.json({});
      if (input.endsWith("/imports/selected")) return Response.json({
        id: "selected", filename: "selected.csv", status: "confirmed", catalog_id: catalogId,
        mapping: {}, columns: [], row_count: 2, currency: "USD",
        indexing: { status: "ready", catalog_id: catalogId, product_count: 2, indexed_product_count: 2 },
      });
      return Response.json({ ...readiness,
        latest_import_id: "selected",
        store: { ...owner.store, sharing_enabled: true, published_catalog_id: "published" },
        indexing: { status: "ready", catalog_id: catalogId, product_count: 2, indexed_product_count: 2 },
        checklist: { ...readiness.checklist, catalog_verified: true, sharing_enabled: true, search_tested: tested },
      });
    }));
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    fireEvent.click(await screen.findByRole("button", { name: "3 Ready to share" }));
    expect(await screen.findByRole("heading", { name: "Your store link is enabled" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Store link enabled" })).toBeDisabled();
    catalogId = "replacement";
    tested = false;
    fireEvent(window, new Event("focus"));
    expect(await screen.findByRole("heading", { name: "Review your catalog update" })).toBeVisible();
    expect(screen.getByText(/Shoppers still see the previously published catalog/)).toBeVisible();
    const publish = screen.getByRole("button", { name: "Publish catalog update" });
    expect(publish).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I reviewed the products and image issues."));
    fireEvent.click(screen.getByLabelText("Checkout is a demo. No real payments are taken."));
    expect(publish).toBeDisabled();
    tested = true;
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(publish).toBeEnabled());
  });
  it("clears acknowledged recovery codes in the parent across workspace navigation", async () => {
    const original = pendingImport().getMockImplementation()!;
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/auth/me")) return Response.json({ ...owner, recovery_code: "synthetic-recovery" });
      return original(input, init);
    }));
    render(<StoreAccess><WorkspaceCatalogAction /></StoreAccess>);
    fireEvent.click(await screen.findByText("I have stored it privately"));
    expect(screen.queryByText("synthetic-recovery")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Review my catalog" }));
    await screen.findByText("catalog.csv");
    expect(screen.queryByText("synthetic-recovery")).not.toBeInTheDocument();
  });
  it("requires confirmation before cancelling a named import", async () => {
    const fetcher = pendingImport();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    try {
      render(<StoreAccess><p>Workspace</p></StoreAccess>);
      fireEvent.click(await screen.findByRole("button", { name: "Cancel import" }));
      expect(confirm).toHaveBeenCalledWith(expect.stringContaining("catalog.csv"));
      expect(fetcher.mock.calls.some(([path]) => path.endsWith("/cancel"))).toBe(false);
      confirm.mockReturnValue(true);
      fireEvent.click(screen.getByRole("button", { name: "Cancel import" }));
      await waitFor(() => expect(fetcher.mock.calls.some(([path]) => path.endsWith("/cancel"))).toBe(true));
    } finally { confirm.mockRestore(); }
  });
  it("distinguishes unavailable authentication from a signed-out session", async () => {
    let unavailable = true;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({ profile: "self_hosted", login_method: "local", setup_required: false });
      if (input.endsWith("/auth/me") && unavailable)
        return Response.json({ error: { message: "Connection unavailable" } }, { status: 503 });
      return Response.json(owner);
    }));
    render(<StoreAccess initialView="workspace"><p>Private catalog</p></StoreAccess>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection unavailable");
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
    expect(screen.queryByText("Private catalog")).not.toBeInTheDocument();
    unavailable = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Private catalog")).toBeVisible();
  });

  it("requires sign-in for direct catalog access and preserves the destination", async () => {
    let signedIn = false;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({ profile: "self_hosted", login_method: "local", setup_required: false });
      if (input.endsWith("/auth/login")) signedIn = true;
      return signedIn ? Response.json(owner) : Response.json({ error: { message: "Sign in" } }, { status: 401 });
    }));
    render(<StoreAccess initialView="workspace"><p>Private catalog</p></StoreAccess>);
    await screen.findByLabelText("Username");
    expect(screen.getByText("GoodAgent")).toBeVisible();
    expect(screen.queryByText("Private catalog")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "owner" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Private catalog")).toBeVisible();
  });

  it("keeps the owner signed in when session revocation fails", async () => {
    let failLogout = true;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({ profile: "self_hosted", login_method: "local", setup_required: false });
      if (input.endsWith("/auth/logout")) return new Response(null, { status: failLogout ? 503 : 204 });
      return Response.json(owner);
    }));
    render(<StoreAccess initialView="workspace"><p>Private workspace</p></StoreAccess>);
    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("may still be active");
    expect(screen.getByText("Private workspace")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss sign-out notice" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    failLogout = false;
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByLabelText("Username")).toBeVisible();
  });

  it("resumes confirmed products at Preview despite unavailable analytics and gates sharing on search", async () => {
    let tested = false;
    const fetcher = vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({ profile: "self_hosted", login_method: "local", setup_required: false });
      if (input.endsWith("/auth/me")) return Response.json(owner);
      if (input.endsWith("/measurements")) return new Response(null, { status: 503 });
      if (input.endsWith("/imports/confirmed")) return Response.json({
        id: "confirmed", catalog_id: "catalog-1", filename: "catalog.csv", status: "confirmed", mapping: {}, columns: [],
        row_count: 48, product_count: 48, currency: "USD", errors: [], warnings: [], products: [],
        indexing: { status: "ready", catalog_id: "catalog-1", product_count: 48, indexed_product_count: 48 },
      });
      return Response.json({ ...readiness, latest_import_id: "confirmed",
        indexing: { status: "ready", catalog_id: "catalog-1", product_count: 48, indexed_product_count: 48 },
        checklist: { ...readiness.checklist, catalog_verified: true, search_tested: tested },
      });
    });
    vi.stubGlobal("fetch", fetcher);
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    expect(await screen.findByText("Try your store privately")).toBeVisible();
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Review sharing" }));
    expect(await screen.findByRole("button", { name: "Test shopper search" })).toBeEnabled();
    fireEvent.click(screen.getByLabelText("I reviewed the products and image issues."));
    fireEvent.click(screen.getByLabelText("Checkout is a demo. No real payments are taken."));
    const enable = screen.getByRole("button", { name: "Enable store link" });
    expect(enable).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Store activity is unavailable");
    tested = true;
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(enable).toBeEnabled());
    expect(fetcher.mock.calls.some(([path]) => path.endsWith("/sharing"))).toBe(false);
    expect(screen.queryByRole("button", { name: "Test shopper search" })).not.toBeInTheDocument();
    const measurementsBefore = fetcher.mock.calls.filter(([path]) => path.endsWith("/measurements")).length;
    fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
    await waitFor(() => expect(fetcher.mock.calls.filter(([path]) => path.endsWith("/measurements"))).toHaveLength(measurementsBefore + 1));
  });

  it("loads an import review even when optional measurements fail", async () => {
    const original = pendingImport().getMockImplementation()!;
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/measurements")) throw new Error("analytics offline");
      return original(input, init);
    }));
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    expect(await screen.findByRole("button", { name: "Confirm products" })).toBeEnabled();
    expect(screen.getByText("catalog.csv")).toBeVisible();
  });
  it("keeps polling when import completion arrives after an older readiness snapshot", async () => {
    let storeReads = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.endsWith("/auth/status")) return Response.json({
        profile: "self_hosted", login_method: "local", setup_required: false,
      });
      if (input.endsWith("/auth/me")) return Response.json(owner);
      if (input.endsWith("/measurements")) return new Response(null, { status: 503 });
      if (input.endsWith("/imports/confirmed")) return Response.json({
        id: "confirmed", catalog_id: "catalog-1", filename: "catalog.csv", status: "confirmed", mapping: {},
        columns: [], row_count: 2, product_count: 2, currency: "USD", errors: [],
        warnings: [], products: [], indexing: { status: "ready", catalog_id: "catalog-1", product_count: 2, indexed_product_count: 2 },
      });
      storeReads += 1;
      return Response.json({
        ...readiness, latest_import_id: "confirmed",
        indexing: { status: storeReads === 1 ? "running" : "ready", catalog_id: "catalog-1", product_count: 2, indexed_product_count: storeReads === 1 ? 0 : 2 },
        checklist: { ...readiness.checklist, catalog_verified: storeReads > 1 },
      });
    }));
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    const preview = await screen.findByRole("button", { name: "Open shopper preview" });
    expect(preview).toBeDisabled();
    await waitFor(() => expect(preview).toBeEnabled(), { timeout: 3500 });
    expect(storeReads).toBeGreaterThan(1);
  });
  function WorkspaceCatalogAction() {
    const navigation = useStoreNavigation();
    return <button onClick={navigation?.openProducts}>Review my catalog</button>;
  }

  function pendingImport() {
    let review: ImportReview = {
      review_fingerprint: "sha256:" + "a".repeat(64),
      id: "pending-upload", filename: "catalog.csv", status: "review",
      expires_at: "2099-01-01T00:00:00Z", row_count: 48, product_count: 48,
      columns: ["product_id", "title", "price", "sale_price"],
      mapping: { product_id: "product_id", title: "title", price: "price" },
      currency: "USD", errors: [], warnings: [], products: [],
    };
    let attempts = 0;
    const fetcher = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/auth/status")) return Response.json({
        profile: "self_hosted", login_method: "local", setup_required: false,
      });
      if (input.endsWith("/auth/me")) return Response.json(owner);
      if (input.endsWith("/mapping")) {
        review = { ...review, ...JSON.parse(String(init?.body)), review_fingerprint: "sha256:" + "b".repeat(64) };
        return Response.json(review);
      }
      if (input.endsWith("/confirm")) {
        attempts += 1;
        if (attempts === 1) return Response.json({ error: {
          message: "Connection interrupted. Retry confirmation.",
        } }, { status: 503 });
        review = { ...review, status: "confirmed", catalog_id: "catalog-1", indexing: {
          status: "ready", catalog_id: "catalog-1", product_count: 48, indexed_product_count: 48,
        } };
        return Response.json(review);
      }
      if (input.endsWith("/imports/pending-upload")) return Response.json(review);
      if (input.endsWith("/measurements")) return Response.json({});
      return Response.json({ ...readiness, latest_import_id: review.id,
        checklist: { ...readiness.checklist, catalog_verified: review.status === "confirmed" },
        indexing: review.indexing ?? readiness.indexing });
    });
    vi.stubGlobal("fetch", fetcher);
    return fetcher;
  }

  it("resumes the existing review from the workspace without confirming or uploading", async () => {
    const fetcher = pendingImport();
    render(<StoreAccess><WorkspaceCatalogAction /></StoreAccess>);
    expect(await screen.findByText(/48 products ready to import/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Review my catalog" }));
    expect(await screen.findByText("catalog.csv")).toBeVisible();
    expect(screen.getByRole("button", { name: "Confirm products" })).toBeEnabled();
    expect(fetcher.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  });

  it("requires mapping validation and keeps failed confirmation available for retry", async () => {
    const fetcher = pendingImport();
    render(<StoreAccess><WorkspaceCatalogAction /></StoreAccess>);
    const confirm = await screen.findByRole("button", { name: "Confirm products" });
    fireEvent.change(screen.getByLabelText("price", { exact: true }), {
      target: { value: "sale_price" },
    });
    expect(confirm).toBeDisabled();
    expect(screen.getByText("Mapping changes need validation.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Validate mapping" }));
    await waitFor(() => expect(confirm).toBeEnabled());
    expect(fetcher.mock.calls.find(([path]) => path.endsWith("/mapping"))?.[1]?.body)
      .toContain('"price":"sale_price"');
    fireEvent.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent("Retry confirmation");
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(await screen.findByText("Try your store privately")).toBeVisible();
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeEnabled();
    const confirmations = fetcher.mock.calls.filter(([path]) => path.endsWith("/confirm"));
    expect(confirmations).toHaveLength(2);
    expect(confirmations[0][1]?.body).toBe(JSON.stringify({ expected_review_fingerprint: "sha256:" + "b".repeat(64) }));
    expect(confirmations[1][1]?.body).toBe(confirmations[0][1]?.body);
    expect(new Headers(confirmations[1][1]?.headers).get("Idempotency-Key"))
      .toBe(new Headers(confirmations[0][1]?.headers).get("Idempotency-Key"));
  });

  it("keeps explicit legacy-demo entry compatible", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          profile: "legacy_demo",
          login_method: "legacy",
          setup_required: false,
        }),
      ),
    );
    render(
      <StoreAccess>
        <p>Existing workspace</p>
      </StoreAccess>,
    );
    expect(await screen.findByText("Existing workspace")).toBeVisible();
    expect(screen.queryByText("Make it your store")).not.toBeInTheDocument();
  });
  it("requires owner setup and does not attach sample products when exploring", async () => {
    const fetcher = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/auth/status"))
        return Response.json({
          profile: "self_hosted",
          login_method: "local",
          setup_required: true,
        });
      if (input.endsWith("/auth/me"))
        return Response.json(
          { error: { message: "Sign in" } },
          { status: 401 },
        );
      if (input.endsWith("/auth/setup")) {
        expect(init?.method).toBe("POST");
        return Response.json({
          ...owner,
          recovery_code: "synthetic-only-code",
        });
      }
      if (input.endsWith("/measurements"))
        return Response.json({
          successful_searches: 0,
          product_selections: 0,
          cart_additions: 0,
          demo_checkouts: 0,
        });
      return Response.json(readiness);
    });
    vi.stubGlobal("fetch", fetcher);
    render(
      <StoreAccess>
        <p>Existing workspace</p>
      </StoreAccess>,
    );
    await screen.findByText("Make it your store");
    fireEvent.change(screen.getByLabelText("Store name"), {
      target: { value: "Test store" },
    });
    fireEvent.change(screen.getByLabelText("Instance setup token"), {
      target: { value: "synthetic-token" },
    });
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "owner" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "synthetic-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create my store" }));
    expect(await screen.findByText("Bring your products")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Explore without data" }),
    );
    expect(screen.getByText("Existing workspace")).toBeVisible();
    expect(
      fetcher.mock.calls.some(([path]) => path.includes("/imports/")),
    ).toBe(false);
    fireEvent.click(
      screen.getByRole("button", { name: "Store setup & sharing" }),
    );
    await screen.findByText("Bring your products");
    fireEvent.click(screen.getByRole("button", { name: "3 Ready to share" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Enable store link" }),
      ).toBeDisabled(),
    );
    expect(screen.getByText("AI connection verified")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByText("Welcome back")).toBeVisible();
    expect(screen.queryByLabelText("Instance setup token")).not.toBeInTheDocument();
  });
});
