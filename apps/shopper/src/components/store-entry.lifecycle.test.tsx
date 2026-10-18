import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SearchParamsContext } from "next/dist/shared/lib/hooks-client-context.shared-runtime";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StorePage from "@/app/s/[slug]/page";
import { loadMemoryChange, saveMemoryChange } from "@/lib/memory-change";

const accountId = "80000000-0000-0000-0000-000000000001";
const receipt = { key: "12345678-1234-1234-1234-123456789012", enabled: false };
type Call = { path: string; slug: string; method: string; body?: string };
const calls: Call[] = [];
const previews = new Map<string, number>();
let override: ((call: Call) => Response | Promise<Response> | undefined) | undefined;

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
function denial(status = 404, code = "STORE_UNAVAILABLE") {
  return response({ error: { code, message: "This store is not accepting shoppers yet.", request_id: "fixture" } }, status);
}
function productName(slug: string) { return `${slug} Product ${previews.get(slug) ?? 0}`; }
function go(slug: string, hash = "") { window.history.pushState({}, "", `/s/${slug}${hash}`); }
async function page(slug: string) { return StorePage({ params: Promise.resolve({ slug }) }); }
function count(suffix: string) { return calls.filter((call) => call.path.endsWith(suffix)).length; }

beforeEach(() => {
  calls.length = 0;
  previews.clear();
  override = undefined;
  sessionStorage.clear();
  go("alpha");
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : String(input), window.location.origin).pathname;
    const slug = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined)).get("x-store-slug") ?? "";
    const call = { path, slug, method: init?.method ?? (input instanceof Request ? input.method : "GET"), body: typeof init?.body === "string" ? init.body : undefined };
    calls.push(call);
    const replaced = override?.(call);
    if (replaced) return replaced;
    if (path.endsWith("/preview")) {
      if (call.body?.includes("synthetic-invalid")) return denial(401, "STORE_REQUEST_BLOCKED");
      previews.set(slug, (previews.get(slug) ?? 0) + 1);
      return response({});
    }
    if (path.endsWith("/store")) return response({ slug, name: `${slug} Store`, description: "Synthetic", currency: "USD", preview: previews.has(slug) });
    if (path.endsWith("/me") || path.endsWith("/auth/guest")) return response({ account: {
      id: accountId, username: "fixture", display_name: `${slug} Account`, created_at: "2026-10-18T00:00:00Z", memory_enabled: true, is_guest: false,
    }, ...(path.endsWith("/auth/guest") ? { created: false } : {}) });
    if (path.endsWith("/conversations") || path.endsWith("/memories")) return response({ items: [] });
    if (path.endsWith("/discovery")) return response({ catalog_status: "ready", catalog_name: `${slug} catalog`, product_count: 1, suggestions: [] });
    if (path.endsWith("/cart")) return response({
      id: `${slug}-cart`, status: "open", lines: [{ id: "line", product_id: "saved", variant_id: "saved-variant", title: "Saved cart product", variant_title: "Default", image_url: null, quantity: 1, unit_price: { amount_minor: 100, currency: "USD" }, line_total: { amount_minor: 100, currency: "USD" }, available_quantity: 5, sellable_quantity: 5 }],
      subtotal: { amount_minor: 100, currency: "USD" }, total: { amount_minor: 100, currency: "USD" }, item_count: 1, version: 1, updated_at: null,
    });
    if (path.endsWith("/checkout/current")) return response(null);
    if (path.endsWith("/catalog")) return response({
      catalog: { id: `${slug}-catalog`, filename: `${slug}.csv`, source_version: "synthetic", product_count: 1, published_at: "2026-10-18T00:00:00Z" },
      indexing: { status: "ready" }, categories: ["Fixture"], total: 1, offset: 0, limit: 24,
      items: [{ product_id: `${slug}-product`, title: productName(slug), description: "Synthetic", brand: slug, category: "Fixture", image_url: null, variant_id: `${slug}-variant`, price: { amount_minor: 100, currency: "USD" }, availability: "available", provenance: null }],
    });
    throw new Error(`Unexpected mocked endpoint ${path}`);
  }));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.cookie = "open_commerce_shopper_session_beta=; Max-Age=0; Path=/";
});

describe("real store route and transport", () => {
  it("isolates branding, catalog, preview and same-account memory receipts across keyed routes", async () => {
    previews.set("alpha", 1);
    saveMemoryChange(`alpha:${accountId}`, receipt);
    const view = render(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    expect(screen.getByText("Private preview")).toBeVisible();
    expect(screen.getByText(/Memory setting is unverified/)).toBeVisible();
    const boundary = calls.length;
    go("beta");
    view.rerender(await page("beta"));
    expect(screen.queryByRole("heading", { name: productName("alpha") })).not.toBeInTheDocument();
    await screen.findByRole("heading", { name: productName("beta") });
    expect(screen.getByText("beta Store")).toBeVisible();
    expect(screen.queryByText("alpha Store")).not.toBeInTheDocument();
    expect(screen.queryByText("Private preview")).not.toBeInTheDocument();
    expect(screen.queryByText(/Memory setting is unverified/)).not.toBeInTheDocument();
    expect(loadMemoryChange(`alpha:${accountId}`)).toEqual(receipt);
    expect(loadMemoryChange(`beta:${accountId}`)).toBeNull();
    expect(calls.slice(boundary).every((call) => call.slug === "beta")).toBe(true);
    go("alpha");
    view.rerender(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    expect(screen.getByText(/Memory setting is unverified/)).toBeVisible();
    expect(count("/preferences")).toBe(0);
  });

  it("unmounts a revoked store, stops polling, and explicitly restores the same session/cart/receipt without another guest write", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
    go("beta");
    document.cookie = "open_commerce_shopper_session_beta=synthetic-session; Path=/";
    await act(async () => { render(await page("beta")); });
    await act(async () => { await vi.waitFor(() => expect(screen.getByRole("heading", { name: productName("beta") })).toBeVisible()); });
    expect(screen.getByRole("button", { name: "Open cart with 1 items" })).toBeVisible();
    saveMemoryChange(`beta:${accountId}`, receipt);
    override = () => denial();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" })); });
    await act(async () => { await vi.waitFor(() => expect(screen.getByRole("heading", { name: "This store is unavailable" })).toBeVisible()); });
    expect(screen.queryByRole("region", { name: "Browse store catalog" })).not.toBeInTheDocument();
    expect(screen.queryByText("beta Store")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Account" })).not.toBeInTheDocument();
    const closedCount = calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); });
    expect(calls).toHaveLength(closedCount);
    expect(document.cookie).toContain("open_commerce_shopper_session_beta=synthetic-session");
    expect(loadMemoryChange(`beta:${accountId}`)).toEqual(receipt);
    override = undefined;
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Try again" })); });
    await act(async () => { await vi.waitFor(() => expect(screen.getByRole("heading", { name: productName("beta") })).toBeVisible()); });
    expect(screen.getByText("beta Account")).toBeVisible();
    expect(screen.getByText(/Memory setting is unverified/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Open cart with 1 items" }));
    expect(screen.getByText("Saved cart product")).toBeVisible();
    expect(count("/auth/guest")).toBe(1);
    expect(count("/auth/logout")).toBe(0);
    expect(count("/preferences")).toBe(0);
  });

  it.each([[403, "STORE_REQUEST_BLOCKED"], [404, "STORE_REQUEST_BLOCKED"], [503, "temporarily_unavailable"]])("retains normal catalog failure behavior for %s/%s", async (status, code) => {
    render(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    override = (call) => call.path.endsWith("/catalog") ? denial(Number(status), String(code)) : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Showing last loaded data.");
    expect(screen.getByRole("heading", { name: productName("alpha") })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "This store is unavailable" })).not.toBeInTheDocument();
  });

  it("keeps a 401 on the existing shopper session recovery path", async () => {
    render(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    override = (call) => call.path.endsWith("/catalog") ? denial(401, "SHOPPER_SESSION_EXPIRED") : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    expect(await screen.findByRole("heading", { name: "Your shopping session expired" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "This store is unavailable" })).not.toBeInTheDocument();
  });

  it("manual memory denial closes the whole store while retaining its uncertain receipt", async () => {
    render(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    override = (call) => call.path.endsWith("/preferences") ? denial() : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    await screen.findByRole("heading", { name: "This store is unavailable" });
    const saved = loadMemoryChange(`alpha:${accountId}`);
    expect(saved).toMatchObject({ enabled: false });
    override = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("heading", { name: productName("alpha") });
    expect(screen.getByText(/Memory setting is unverified/)).toBeVisible();
    expect(loadMemoryChange(`alpha:${accountId}`)).toEqual(saved);
    expect(count("/preferences")).toBe(1);
    expect(count("/auth/guest")).toBe(1);
  });

  it("account drawer manual requests use the owning store gate", async () => {
    render(await page("alpha"));
    await screen.findByRole("heading", { name: productName("alpha") });
    override = (call) => call.path.endsWith("/auth/sessions") ? denial() : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByRole("button", { name: "View active sessions" }));
    await screen.findByRole("heading", { name: "This store is unavailable" });
    expect(calls.find((call) => call.path.endsWith("/auth/sessions"))?.slug).toBe("alpha");
    expect(screen.queryByRole("button", { name: "View active sessions" })).not.toBeInTheDocument();
  });
});

describe("same-document preview navigation", () => {
  it("consumes native hash replacements once and recovers from a failed grant without replay", async () => {
    render(<StrictMode>{await page("alpha")}</StrictMode>);
    await screen.findByRole("heading", { name: productName("alpha") });
    await act(async () => { window.location.hash = "preview=synthetic-invalid"; });
    await screen.findByRole("heading", { name: "This store is unavailable" });
    expect(count("/preview")).toBe(1);
    expect(window.location.hash).toBe("");
    await act(async () => { window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(count("/preview")).toBe(1);
    await act(async () => { window.location.hash = "preview=synthetic-fresh"; });
    await screen.findByRole("heading", { name: "alpha Product 1" });
    expect(screen.getByText("Private preview")).toBeVisible();
    expect(window.location.hash).toBe("");
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(count("/preview")).toBe(2);
    expect(JSON.stringify(sessionStorage)).not.toContain("synthetic-");
  });

  it("handles Next's canonical-URL search-params context on hash-only navigation and ignores the old preview's late denial", async () => {
    const element = await page("alpha");
    // Next 15 rebuilds this context from canonicalUrl, including hash-only router navigation.
    const nextTree = () => <SearchParamsContext.Provider value={new URL(window.location.href).searchParams}>{element}</SearchParamsContext.Provider>;
    const view = render(nextTree());
    await screen.findByRole("heading", { name: "alpha Product 0" });
    go("alpha", "#preview=synthetic-next-first");
    // pushState emits neither hashchange nor popstate; only the real Next hook's context changes.
    view.rerender(nextTree());
    await screen.findByRole("heading", { name: "alpha Product 1" });
    let resolve!: (result: Response) => void;
    override = (call) => call.path.endsWith("/catalog") ? new Promise<Response>((done) => { resolve = done; }) : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await waitFor(() => expect(resolve).toBeDefined());
    override = undefined;
    go("alpha", "#preview=synthetic-next-second");
    view.rerender(nextTree());
    await screen.findByRole("heading", { name: "alpha Product 2" });
    await act(async () => resolve(denial()));
    expect(screen.getByRole("heading", { name: "alpha Product 2" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "This store is unavailable" })).not.toBeInTheDocument();
    expect(count("/preview")).toBe(2);
    expect(window.location.hash).toBe("");
  });
});
