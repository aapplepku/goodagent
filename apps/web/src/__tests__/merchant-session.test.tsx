import { StrictMode } from "react";
import type { CatalogBrowseResponse, OwnerAuthResponse, StoreReadiness } from "@open-commerce/sdk-typescript";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CatalogPage from "@/app/manager/catalog/page";
import { StoreAccess } from "@/components/store-setup";
import { ActivityPanel } from "@/components/activity-panel";
import { RankingPanel } from "@/components/ranking-panel";
import { ShopifyPanel } from "@/components/shopify-panel";
import { deferred, denied, expectBinding, merchantServer, ownerA, ownerB } from "./merchant-test-server";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function readiness(identity: OwnerAuthResponse, ready = false): StoreReadiness {
  return {
    store: identity.store, indexing: { status: ready ? "ready" : "not_configured", catalog_id: ready ? "catalog-a" : undefined },
    image_failures: 0, latest_import_id: null,
    checklist: { catalog_verified: ready, ai_verified: false, sharing_enabled: false, search_tested: ready },
  };
}
function catalog(identity: OwnerAuthResponse): CatalogBrowseResponse {
  return {
    catalog: { id: identity.store.id, filename: identity.store.name + ".csv", source_version: "fixture", product_count: 0, published_at: null },
    indexing: { status: "ready" }, categories: [], items: [], total: 0, offset: 0, limit: 24,
  };
}
async function expired() {
  const heading = await screen.findByRole("heading", { name: "Your store session expired" });
  await waitFor(() => expect(heading).toHaveFocus());
  expect(screen.getByRole("button", { name: "Check session" })).toBeEnabled();
}
async function noBackgroundRequests(server: ReturnType<typeof merchantServer>) {
  const count = server.requests.length;
  vi.useFakeTimers();
  await act(async () => {
    fireEvent(window, new Event("focus"));
    await vi.advanceTimersByTimeAsync(31000);
  });
  expect(server.requests).toHaveLength(count);
  vi.useRealTimers();
}

describe("StoreAccess request intent and explicit recovery", () => {
  it("rejects stale profile edits and remounts fresh fields only after explicit discovery", async () => {
    const applied = vi.fn();
    const server = merchantServer((request) => {
      if (request.method === "PATCH") applied();
      return Response.json(readiness(server.identity!));
    });
    render(<StrictMode><StoreAccess><p>Private workspace</p></StoreAccess></StrictMode>);
    const name = await screen.findByLabelText("Store name");
    fireEvent.change(name, { target: { value: "A unsaved draft" } });
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    await expired();
    expect(screen.queryByLabelText("Store name")).not.toBeInTheDocument();
    expect(applied).not.toHaveBeenCalled();
    const patch = server.requests.find((request) => request.method === "PATCH")!;
    expectBinding(patch, ownerA);
    expect(await patch.json()).toMatchObject({ name: "A unsaved draft" });
    await noBackgroundRequests(server);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect(await screen.findByLabelText("Store name")).toHaveValue("Store B");
    expectBinding(server.calls("/merchant/store").at(-1)!, ownerB);
    expect(applied).not.toHaveBeenCalled();
    expect(server.requests.filter((request) => request.method === "PATCH")).toHaveLength(1);
  });

  it("keeps sharing-disable bound while the setup focus read is still pending", async () => {
    const focus = deferred<Response>();
    let holdFocus = false;
    const server = merchantServer((request) => {
      if (new URL(request.url).pathname.endsWith("/merchant/store") && holdFocus) return focus.promise;
      return Response.json({ ...readiness(ownerA, true), store: { ...ownerA.store, sharing_enabled: true, published_catalog_id: "catalog-a" } });
    });
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    await screen.findByRole("heading", { name: "Your store link is enabled" });
    holdFocus = true;
    fireEvent(window, new Event("focus"));
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Disable sharing" }));
    await expired();
    expectBinding(server.calls("/sharing")[0], ownerA);
    expect(await server.calls("/sharing")[0].json()).toMatchObject({ enabled: false, catalog_id: "catalog-a" });
    await act(async () => { focus.resolve(Response.json(readiness(ownerA, true))); });
    expect(screen.queryByText("Your store link is enabled")).not.toBeInTheDocument();
    await noBackgroundRequests(server);
  });

  it("binds the manual CSV upload and never refreshes or logs out after rejection", async () => {
    const server = merchantServer(() => Response.json(readiness(ownerA)));
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    const upload = await screen.findByLabelText("Upload catalog CSV");
    const reads = server.calls("/merchant/store").length;
    server.identity = ownerB;
    fireEvent.change(upload, { target: { files: [new File(["title\nA"], "A catalog.csv", { type: "text/csv" })] } });
    await expired();
    const request = server.calls("/imports/upload")[0];
    expectBinding(request, ownerA);
    expect(new URL(request.url).searchParams.get("filename")).toBe("A catalog.csv");
    expect(request.headers.get("Content-Type")).toBe("text/csv");
    expect(request.headers.get("Idempotency-Key")).toBeTruthy();
    expect(server.calls("/merchant/store")).toHaveLength(reads);
    expect(server.calls("/auth/logout")).toHaveLength(0);
  });

  it.each(["upload", "preview"] as const)("fences a late %s completion after recovery to B", async (operation) => {
    const pending = deferred<Response>();
    const opened = vi.spyOn(window, "open").mockReturnValue(null);
    const server = merchantServer((request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/upload") || path.endsWith("/preview")) return pending.promise;
      const indexing = { status: "ready", catalog_id: "catalog-a", product_count: 1, indexed_product_count: 1 };
      if (path.endsWith("/imports/confirmed")) return Response.json({
        id: "confirmed", catalog_id: "catalog-a", filename: "a.csv", status: "confirmed",
        mapping: {}, columns: [], row_count: 1, currency: "USD", indexing,
      });
      return Response.json({ ...readiness(server.identity!, true), latest_import_id: "confirmed", indexing });
    });
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    await screen.findByRole("button", { name: "Open shopper preview" });
    fireEvent.click(screen.getByRole("button", { name: "1 Products" }));
    if (operation === "upload") {
      fireEvent.change(screen.getByLabelText("Upload catalog CSV"), { target: { files: [new File(["title\nA"], "a.csv")] } });
      fireEvent.click(screen.getByRole("button", { name: "2 Preview" }));
    } else {
      fireEvent.click(screen.getByRole("button", { name: "2 Preview" }));
      fireEvent.click(screen.getByRole("button", { name: "Open shopper preview" }));
    }
    await waitFor(() => expect(server.calls(`/${operation}`)).toHaveLength(1));
    server.identity = ownerB;
    fireEvent(window, new Event("focus"));
    await expired();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByRole("button", { name: "Open shopper preview" });
    fireEvent.click(screen.getByRole("button", { name: "1 Products" }));
    expect(await screen.findByLabelText("Store name")).toHaveValue("Store B");
    const count = server.requests.length;
    await act(async () => { pending.resolve(Response.json({ token: "synthetic-unused", store_slug: "store-a" })); });
    expect(server.requests).toHaveLength(count);
    expect(opened).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Store name")).toHaveValue("Store B");
  });

  it("suspends setup on indexing poll 401 and removes its focus listener and timer", async () => {
    vi.useFakeTimers();
    const server = merchantServer((request) => Response.json(new URL(request.url).pathname.endsWith("/imports/confirmed") ? {
      id: "confirmed", filename: "a.csv", status: "confirmed", mapping: {}, columns: [], row_count: 1,
      product_count: 1, currency: "USD", errors: [], warnings: [], products: [], indexing: { status: "running" },
    } : { ...readiness(ownerA), latest_import_id: "confirmed", indexing: { status: "running" } }));
    render(<StoreAccess><p>Workspace</p></StoreAccess>);
    await act(async () => {});
    expect(screen.getByRole("button", { name: "Open shopper preview" })).toBeDisabled();
    server.identity = null;
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(screen.getByRole("heading", { name: "Your store session expired" })).toHaveFocus();
    const count = server.requests.length;
    await act(async () => { fireEvent(window, new Event("focus")); await vi.advanceTimersByTimeAsync(10000); });
    expect(server.requests).toHaveLength(count);
    expect(server.calls("/auth/me")).toHaveLength(1);
  });

  it("uses the actual direct catalog route, gates cached data, and resets filters on recovery", async () => {
    const server = merchantServer(() => Response.json(catalog(server.identity!)));
    render(<CatalogPage />);
    expect(await screen.findByText("Store A.csv")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Find catalog products"), { target: { value: "A-only search" } });
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await expired();
    expect(screen.queryByText("Store A.csv")).not.toBeInTheDocument();
    expectBinding(server.calls("/manager/catalog").at(-1)!, ownerA);
    await noBackgroundRequests(server);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect(await screen.findByText("Store B.csv")).toBeVisible();
    expect(screen.getByLabelText("Find catalog products")).toHaveValue("");
    expectBinding(server.calls("/manager/catalog").at(-1)!, ownerB);
    expect(server.calls("/auth/me")).toHaveLength(2);
  });

  it.each([403, 404, 503])("keeps the existing error behavior for protected %s", async (status) => {
    const server = merchantServer(() => Response.json(catalog(ownerA)));
    render(<CatalogPage />);
    await screen.findByText("Store A.csv");
    server.protectedStatus = status;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Showing last loaded data");
    expect(screen.getByText("Store A.csv")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Check session" })).not.toBeInTheDocument();
  });

  it.each(["setup", "workspace"] as const)("does not revoke B through stale %s logout", async (view) => {
    const revoke = vi.fn();
    const server = merchantServer((request) => {
      if (new URL(request.url).pathname.endsWith("/auth/logout")) { revoke(); return new Response(null, { status: 204 }); }
      return Response.json(readiness(ownerA));
    });
    render(<StoreAccess initialView={view}><p>Private workspace</p></StoreAccess>);
    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }).then((button) => {
      server.identity = ownerB;
      return button;
    }));
    await expired();
    expectBinding(server.calls("/auth/logout")[0], ownerA);
    expect(revoke).not.toHaveBeenCalled();
    expect(server.identity).toBe(ownerB);
    await noBackgroundRequests(server);
  });

  it.each(["login", "recover"] as const)("keeps explicit %s unbound and binds the immediately accepted identity", async (method) => {
    const server = merchantServer((request) => {
      if (new URL(request.url).pathname.endsWith(`/auth/${method}`)) { server.identity = ownerB; return Response.json(ownerB); }
      return Response.json(catalog(server.identity!));
    });
    render(<CatalogPage />);
    await screen.findByText("Store A.csv");
    server.identity = null;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await expired();
    if (method === "recover") fireEvent.click(screen.getByRole("button", { name: "Use a recovery code" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "fixture-b" } });
    fireEvent.change(screen.getByLabelText(method === "recover" ? "New password" : "Password"), { target: { value: "synthetic-test-only-password" } });
    if (method === "recover") fireEvent.change(screen.getByLabelText("Single-use recovery code"), { target: { value: "synthetic-test-only-code" } });
    fireEvent.click(screen.getByRole("button", { name: method === "recover" ? "Recover account" : "Sign in" }));
    expect(await screen.findByText("Store B.csv")).toBeVisible();
    expectBinding(server.calls(`/auth/${method}`)[0], null);
    expectBinding(server.calls("/manager/catalog").at(-1)!, ownerB);
    expect(server.calls("/auth/me")).toHaveLength(1);
    expect(server.calls("/auth/logout")).toHaveLength(0);
  });

  it("preserves legacy unbound catalog access without owner discovery", async () => {
    const server = merchantServer(() => Response.json(catalog(ownerA)));
    server.legacy = true;
    render(<CatalogPage />);
    await screen.findByText("Store A.csv");
    expectBinding(server.calls("/manager/catalog")[0], null);
    expect(server.calls("/auth/me")).toHaveLength(0);
  });
});

describe("merchant child panels use the originating transport", () => {
  it("binds activity reads and monitor mutations, then stops polling on mismatch", async () => {
    const server = merchantServer(() => Response.json({
      scope: "store_activity", observed_counts: {}, available_kinds: [], available_fields: [], checked_at: "2026-10-18T00:00:00Z", events: [],
      rules: [{ id: "rule-a", definition: { name: "A monitor", enabled: true }, check: { state: "ok", sample_count: 1, checked_at: "2026-10-18T00:00:00Z" } }],
    }));
    render(<StoreAccess initialView="workspace"><ActivityPanel /></StoreAccess>);
    fireEvent.click(await screen.findByText("A monitor"));
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Pause A monitor" }));
    await expired();
    expectBinding(server.calls("/manager/activity")[0], ownerA);
    expectBinding(server.calls("/activity/rules")[0], ownerA);
    expect(await server.calls("/activity/rules")[0].json()).toMatchObject({ enabled: false, name: "A monitor" });
    await noBackgroundRequests(server);
  });

  it.each(["ranking", "shopify"] as const)("retains the original %s retry key and never replays after recovery", async (panel) => {
    const writePath = panel === "ranking" ? "/ranking/train" : "/shopify/import";
    const server = merchantServer((request) => {
      if (new URL(request.url).pathname.endsWith(writePath)) return denied(503);
      return Response.json(panel === "ranking"
        ? { catalog_id: "catalog-a", dataset: { event_count: 5, product_count: 1, event_counts: {} }, models: [] }
        : { connected: true, detail: "Synthetic test connection", shop: "fixture.invalid" });
    });
    render(<StoreAccess initialView="workspace">{panel === "ranking" ? <RankingPanel /> : <ShopifyPanel />}</StoreAccess>);
    let command: HTMLElement;
    if (panel === "ranking") {
      command = await screen.findByRole("button", { name: "Build candidate" });
      await waitFor(() => expect(command).toBeEnabled());
    } else {
      fireEvent.click(await screen.findByRole("button", { name: "Check connection" }));
      fireEvent.click(await screen.findByRole("button", { name: "Import catalog" }));
      command = screen.getByRole("button", { name: "Confirm import" });
    }
    fireEvent.click(command);
    await screen.findByText(/Request blocked/);
    await waitFor(() => expect(command).toBeEnabled());
    server.identity = ownerB;
    fireEvent.click(command);
    await expired();
    const [first, retry] = server.calls(writePath);
    expectBinding(first, ownerA);
    expectBinding(retry, ownerA);
    expect(retry.headers.get("Idempotency-Key")).toBe(first.headers.get("Idempotency-Key"));
    expect(retry.headers.get("Idempotency-Key")).toBeTruthy();
    await noBackgroundRequests(server);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByRole("button", { name: panel === "ranking" ? "Build candidate" : "Check connection" });
    expect(server.calls(writePath)).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Confirm import" })).not.toBeInTheDocument();
  });
});
