import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShopperAccount } from "@open-commerce/sdk-typescript";
import { loadMemoryChange } from "@/lib/memory-change";
import { ShopperApp } from "./shopper-app";

const a: ShopperAccount = { id: "80000000-0000-0000-0000-000000000001", username: "alex", display_name: "Alex", is_guest: false, memory_enabled: true, created_at: "2026-10-18T00:00:00Z" };
const b: ShopperAccount = { ...a, id: "80000000-0000-0000-0000-000000000002", username: "blair", display_name: "Blair" };
const guest: ShopperAccount = { ...a, is_guest: true, display_name: "Guest" };
const newGuest: ShopperAccount = { ...guest, id: "80000000-0000-0000-0000-000000000003" };
const store = { slug: "alpha", name: "Alpha Store", description: "Synthetic", currency: "USD" };
const cart = { id: "cart", status: "open", lines: [], subtotal: { amount_minor: 0, currency: "USD" }, total: { amount_minor: 0, currency: "USD" }, item_count: 0, version: 1, updated_at: null };
const catalog = {
  catalog: { id: "catalog", filename: "fixture.csv", source_version: "synthetic", product_count: 1, published_at: "2026-10-18T00:00:00Z" },
  indexing: { status: "ready" }, categories: ["Fixture"], total: 1, offset: 0, limit: 24,
  items: [{ product_id: "product", title: "Fixture product", description: "Synthetic", brand: "Fixture", category: "Fixture", image_url: null, variant_id: "variant", price: { amount_minor: 100, currency: "USD" }, availability: "available", provenance: null }],
};
type Call = { path: string; method: string; account: string | null; store: string | null; key: string | null; body: string };
const calls: Call[] = [];
const writes: Call[] = [];
// Only the HTTP boundary is doubled. Components, contexts and both transports are real.
let cookieAccount: ShopperAccount | null;
let override: ((call: Call) => Response | Promise<Response> | undefined) | undefined;
const response = (data: unknown, status = 200) => Response.json(data, { status });
const denied = () => response({ error: { code: "SHOPPER_AUTHENTICATION_FAILED", message: "Session changed", request_id: "fixture" } }, 401);
const matching = (path: string) => calls.filter((call) => call.path === path);

beforeEach(() => {
  calls.length = 0;
  writes.length = 0;
  cookieAccount = a;
  override = undefined;
  sessionStorage.clear();
  window.history.replaceState({}, "", "/s/alpha");
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const call: Call = {
      path: new URL(request.url).pathname.replace("/api/runtime", ""), method: request.method,
      account: request.headers.get("x-shopper-account-id"), store: request.headers.get("x-store-slug"),
      key: request.headers.get("idempotency-key"), body: await request.text(),
    };
    calls.push(call);
    if (call.account && call.account !== cookieAccount?.id) return denied();
    const replaced = override?.(call);
    if (replaced) return replaced;
    if (call.method !== "GET") writes.push(call);
    if (call.path === "/v1/shopper/auth/login" || call.path === "/v1/shopper/auth/recover") {
      cookieAccount = b;
      return response({ account: b });
    }
    if (call.path === "/v1/shopper/auth/register") {
      cookieAccount = { ...a, is_guest: false };
      return response({ account: cookieAccount });
    }
    if (call.path === "/v1/shopper/auth/logout") {
      cookieAccount = null;
      return new Response(null, { status: 204 });
    }
    if (call.path === "/v1/shopper/auth/guest") {
      const created = cookieAccount === null;
      cookieAccount ??= newGuest;
      return response({ account: cookieAccount, created });
    }
    if (!cookieAccount) return denied();
    if (call.path === "/v1/shopper/me") return response({ account: cookieAccount });
    if (call.path === "/v1/shopper/preferences") return response({ account: { ...cookieAccount, memory_enabled: JSON.parse(call.body).enabled } });
    if (["/v1/shopper/conversations", "/v1/shopper/memories", "/v1/shopper/orders"].includes(call.path)) return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (call.path === "/v1/shopper/discovery") return response({ catalog_status: "ready", catalog_name: "Fixture", product_count: 1, suggestions: [] });
    if (call.path === "/v1/shopper/cart" || call.path === "/v1/shopper/cart/items") return response(cart);
    if (call.path === "/v1/shopper/checkout/current") return response(null);
    if (call.path === "/v1/shopper/catalog") return response(catalog);
    if (call.path === "/v1/shopper/product-selections") return new Response(null, { status: 204 });
    if (call.path === "/v1/shopper/auth/sessions") return response({ items: [] });
    if (call.path === "/v1/shopper/activity") return response({
      checked_at: "2026-10-18T00:00:00Z", events: [], observed_counts: {}, available_kinds: [], rules: [{
        id: "rule", definition: { name: "Fixture monitor", enabled: true, query: {} },
        check: { checked_at: "2026-10-18T00:00:00Z", state: "ok", sample_count: 1 },
      }],
    });
    throw new Error(`Unexpected synthetic endpoint: ${call.method} ${call.path}`);
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

async function open(view: "chat" | "catalog" = "catalog") {
  const rendered = render(<ShopperApp store={store} initialView={view} />);
  await screen.findByText(cookieAccount!.display_name);
  await waitFor(() => expect(screen.getByRole("button", { name: "Open cart with 0 items" })).toBeVisible());
  if (view === "catalog") await screen.findByRole("heading", { name: "Fixture product" });
  return rendered;
}
function accountDrawer() { fireEvent.click(screen.getByRole("button", { name: cookieAccount?.is_guest ? "Save your progress" : "Account" })); }
async function suspended() { await screen.findByRole("heading", { name: "Your shopping session expired" }); }
function signIn() {
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "blair" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-password" } });
  fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
}

describe("real account-bound shopper workspace", () => {
  it("binds the very first workspace load, child panels and later reads without repeating bootstrap", async () => {
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "View active sessions" }));
    await waitFor(() => expect(matching("/v1/shopper/auth/sessions")).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    fireEvent.click(screen.getByRole("button", { name: "Shopping activity" }));
    await screen.findByText("Fixture monitor");
    expect(matching("/v1/shopper/me").map((call) => call.account)).toEqual([null]);
    expect(calls.filter((call) => call.path !== "/v1/shopper/me").every((call) => call.account === a.id && call.store === "alpha")).toBe(true);
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    expect(matching("/v1/shopper/conversations")).toHaveLength(1);
    expect(matching("/v1/shopper/activity")).toHaveLength(1);
  });

  it("keeps Strict Mode bootstrap discovery unbound and its protected loads bound", async () => {
    render(<StrictMode><ShopperApp store={store} initialView="catalog" /></StrictMode>);
    await screen.findByRole("heading", { name: "Fixture product" });
    expect(matching("/v1/shopper/me")).toHaveLength(2);
    expect(matching("/v1/shopper/me").every((call) => call.account === null)).toBe(true);
    expect(matching("/v1/shopper/cart").every((call) => call.account === a.id)).toBe(true);
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
  });

  it.each([
    ["Confirm deletion", "/v1/shopper/shopping-data", "DELETE"],
    ["Sign out everywhere", "/v1/shopper/auth/sessions", "DELETE"],
    ["Remember shopping preferences", "/v1/shopper/preferences", "PATCH"],
    ["View active sessions", "/v1/shopper/auth/sessions", "GET"],
    ["Sign out", "/v1/shopper/auth/logout", "POST"],
    ["View product", "/v1/shopper/product-selections", "POST"],
    ["Demo orders", "/v1/shopper/orders", "GET"],
  ])("rejects stale A's %s against cookie B and suspends without adopting B", async (command, path, method) => {
    await open();
    if (["Confirm deletion", "Sign out everywhere", "Remember shopping preferences", "View active sessions"].includes(command)) accountDrawer();
    if (command === "Confirm deletion") fireEvent.click(screen.getByRole("button", { name: "Delete shopping data" }));
    cookieAccount = b;
    fireEvent.click(screen.getByRole(command === "Remember shopping preferences" ? "checkbox" : "button", { name: command }));
    await suspended();
    expect(matching(path).at(-1)).toMatchObject({ account: a.id, store: "alpha", method });
    expect(writes).toHaveLength(0);
    expect(cookieAccount).toBe(b);
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Fixture product" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/guest")).toHaveLength(0);
  });

  it("keeps the SDK cart continuation bound to A when the cookie changes after product lookup", async () => {
    await open();
    let finish!: (value: Response) => void;
    override = (call) => call.path === "/v1/shopper/catalog" ? new Promise<Response>((resolve) => { finish = resolve; }) : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Add Fixture product to cart" }));
    await waitFor(() => expect(finish).toBeDefined());
    cookieAccount = b;
    await act(async () => finish(response(catalog)));
    await suspended();
    expect(matching("/v1/shopper/cart/items")).toHaveLength(1);
    expect(matching("/v1/shopper/cart/items")[0]).toMatchObject({ account: a.id, body: JSON.stringify({ product_id: "product", quantity: 1 }) });
    expect(writes).toHaveLength(0);
  });

  it("binds an activity monitor change and stops its polling after mismatch", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Shopping activity" }));
    fireEvent.click(await screen.findByText("Fixture monitor"));
    cookieAccount = b;
    fireEvent.click(screen.getByRole("button", { name: "Pause Fixture monitor" }));
    await suspended();
    expect(calls.find((call) => call.path.includes("activity") && call.method === "POST")).toMatchObject({ account: a.id });
    const count = calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); });
    expect(calls).toHaveLength(count);
    expect(writes).toHaveLength(0);
  });

  it("does not reinterpret a lost memory receipt as B's write and never auto-replays it after recovery", async () => {
    await open();
    override = (call) => { if (call.path === "/v1/shopper/preferences") throw new TypeError("Response lost"); return undefined; };
    accountDrawer();
    fireEvent.click(screen.getByRole("checkbox", { name: "Remember shopping preferences" }));
    await screen.findByText(/Memory setting is unverified/);
    const first = matching("/v1/shopper/preferences")[0];
    expect(loadMemoryChange(`alpha:${a.id}`)).toMatchObject({ key: first.key, enabled: false });
    cookieAccount = b;
    override = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Retry memory change" }));
    await suspended();
    expect(matching("/v1/shopper/preferences")[1]).toEqual(first);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blair");
    await screen.findByRole("heading", { name: "Fixture product" });
    expect(matching("/v1/shopper/me").map((call) => call.account)).toEqual([null, null]);
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(b.id);
    expect(matching("/v1/shopper/preferences")).toHaveLength(2);
    expect(loadMemoryChange(`alpha:${a.id}`)?.key).toBe(first.key);
    expect(loadMemoryChange(`alpha:${b.id}`)).toBeNull();
    expect(writes).toHaveLength(0);
  });

  it("keeps an original chat retry's account, body and key when only the cookie changes", async () => {
    await open("chat");
    override = (call) => { if (call.path === "/v1/shopper/chat") throw new TypeError("Response lost"); return undefined; };
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "A synthetic request" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    cookieAccount = b;
    override = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await suspended();
    const attempts = matching("/v1/shopper/chat");
    expect(attempts).toHaveLength(2);
    expect(attempts[1]).toEqual(attempts[0]);
    expect(attempts[0].account).toBe(a.id);
    expect(JSON.parse(attempts[0].body).expected_account_id).toBe(a.id);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blair");
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Retry same request" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/chat")).toHaveLength(2);
  });

  it("ignores A's delayed manual success after explicit recovery has accepted B", async () => {
    await open();
    let finish!: (value: Response) => void;
    override = (call) => call.path === "/v1/shopper/preferences" ? new Promise<Response>((resolve) => { finish = resolve; }) : undefined;
    accountDrawer();
    fireEvent.click(screen.getByRole("checkbox", { name: "Remember shopping preferences" }));
    await waitFor(() => expect(finish).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    cookieAccount = b;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blair");
    await screen.findByRole("heading", { name: "Fixture product" });
    const boundary = calls.length;
    await act(async () => finish(response({ account: { ...a, memory_enabled: false } })));
    expect(screen.getByText("Blair")).toBeVisible();
    expect(screen.queryByText("Alex")).not.toBeInTheDocument();
    expect(calls).toHaveLength(boundary);
    expect(matching("/v1/shopper/preferences")[0].account).toBe(a.id);
    expect(loadMemoryChange(`alpha:${a.id}`)).toMatchObject({ enabled: false });
  });
});

describe("deliberate account transitions", () => {
  it.each(["register", "login"])("binds guest %s to the guest owning the panel, preventing import/upgrade of cookie B", async (mode) => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    if (mode === "login") fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    cookieAccount = b;
    signIn();
    await suspended();
    expect(matching(`/v1/shopper/auth/${mode}`)[0].account).toBe(guest.id);
    if (mode === "login") expect(matching("/v1/shopper/me").at(-1)?.account).toBe(guest.id);
    expect(writes).toHaveLength(0);
    expect(cookieAccount).toBe(b);
  });

  it("keeps a wrong guest login local after verifying the original guest still owns the cookie", async () => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    override = (call) => call.path === "/v1/shopper/auth/login" ? denied() : undefined;
    signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("Session changed");
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/me").map((call) => call.account)).toEqual([null, guest.id]);
    expect(matching("/v1/shopper/auth/login")[0].account).toBe(guest.id);
  });

  it("loads the exact newly accepted account immediately after a successful guest sign-in", async () => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    signIn();
    await screen.findByText("Blair");
    await waitFor(() => expect(matching("/v1/shopper/cart")).toHaveLength(2));
    expect(matching("/v1/shopper/auth/login")[0].account).toBe(guest.id);
    const loginIndex = calls.findIndex((call) => call.path === "/v1/shopper/auth/login");
    expect(calls.slice(loginIndex + 1).every((call) => call.account === b.id)).toBe(true);
    expect(matching("/v1/shopper/me")).toHaveLength(1);
  });

  it("keeps a pending cart-merge choice bound to its original guest", async () => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    override = (call) => call.path === "/v1/shopper/auth/login"
      ? response({ account: guest, merge_token: "synthetic-merge", guest_cart_items: 1, account_cart_items: 1 }) : undefined;
    signIn();
    await screen.findByText("Which cart should we keep?");
    cookieAccount = b;
    fireEvent.click(screen.getByRole("button", { name: "Keep account cart (1 product)" }));
    await suspended();
    expect(matching("/v1/shopper/auth/merge")[0]).toMatchObject({ account: guest.id, method: "POST" });
    expect(writes).toHaveLength(0);
    expect(cookieAccount).toBe(b);
  });

  it("keeps a valid guest visit when its cart-choice permission requires fresh sign-in", async () => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    override = (call) => {
      if (call.path === "/v1/shopper/auth/login") return response({ account: guest, merge_token: "synthetic-merge", guest_cart_items: 1, account_cart_items: 1 });
      if (call.path === "/v1/shopper/auth/merge") return response({ error: { code: "SHOPPER_AUTHENTICATION_FAILED", message: "Sign in again to review cart changes.", request_id: "fixture" } }, 401);
    };
    signIn();
    await screen.findByText("Which cart should we keep?");
    fireEvent.click(screen.getByRole("button", { name: "Keep account cart (1 product)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in again to review cart changes.");
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fixture product" })).toBeVisible();
    expect(matching("/v1/shopper/me").map((call) => call.account)).toEqual([null, guest.id]);
    expect(matching("/v1/shopper/auth/merge")).toHaveLength(1);
    expect(matching("/v1/shopper/auth/guest")).toHaveLength(0);
    expect(cookieAccount).toBe(guest);
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(screen.getByLabelText("Username")).toBeVisible();
    expect(matching("/v1/shopper/auth/login")).toHaveLength(1);
    expect(matching("/v1/shopper/auth/merge")).toHaveLength(1);
  });

  it("keeps recovery-code authentication explicitly unbound while binding its resulting workspace", async () => {
    cookieAccount = guest;
    await open();
    accountDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Recover" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "blair" } });
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "synthetic-code" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "synthetic-password" } });
    cookieAccount = null;
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    await screen.findByRole("heading", { name: "Replacement recovery code unavailable" });
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(matching("/v1/shopper/auth/recover")[0]).toMatchObject({ account: null, store: "alpha" });
    expect(matching("/v1/shopper/me").at(-1)?.account).toBe(b.id);
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue without a replacement code" }));
    await screen.findByText("Blair");
    await waitFor(() => expect(matching("/v1/shopper/cart")).toHaveLength(2));
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(matching("/v1/shopper/auth/recover")[0].account).toBeNull();
    expect(matching("/v1/shopper/me").map(call => call.account)).toEqual([null, b.id, b.id]);
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(b.id);
  });

  it("uses deliberately unbound recovery login, then binds verification and the new workspace", async () => {
    await open();
    cookieAccount = null;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    signIn();
    await screen.findByText("Blair");
    await waitFor(() => expect(matching("/v1/shopper/cart")).toHaveLength(2));
    expect(matching("/v1/shopper/auth/login")[0].account).toBeNull();
    expect(matching("/v1/shopper/me").map((call) => call.account)).toEqual([null, b.id]);
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(b.id);
    expect(matching("/v1/shopper/auth/logout")).toHaveLength(0);
  });

  it("refuses to start a guest visit by revoking a different account's cookie", async () => {
    await open();
    cookieAccount = b;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    await screen.findByText(/We couldn't start a new guest visit/);
    expect(matching("/v1/shopper/me").at(-1)?.account).toBeNull();
    expect(matching("/v1/shopper/auth/logout")).toHaveLength(0);
    expect(matching("/v1/shopper/auth/guest")).toHaveLength(0);
    expect(cookieAccount).toBe(b);
  });

  it("starts a genuinely expired guest visit without attempting an unbound logout", async () => {
    cookieAccount = guest;
    await open();
    cookieAccount = null;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    await screen.findByRole("heading", { name: "Fixture product" });
    expect(matching("/v1/shopper/auth/logout")).toHaveLength(0);
    expect(matching("/v1/shopper/auth/guest")[0].account).toBeNull();
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(newGuest.id);
  });

  it.each([
    { created: false, isGuest: true },
    { created: undefined, isGuest: true },
    { created: true, isGuest: false },
  ])("rejects fresh-start response created=$created / guest=$isGuest after the cookie changes during the 401 preflight", async ({ created, isGuest }) => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    cookieAccount = guest;
    await open();
    cookieAccount = null;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    const replacement = { ...b, is_guest: isGuest };
    let finishIdentity!: (value: Response) => void;
    let guestResponse: Response | undefined;
    override = (call) => {
      if (call.path === "/v1/shopper/me")
        return new Promise<Response>((resolve) => { finishIdentity = resolve; });
      if (call.path === "/v1/shopper/auth/guest") {
        expect(cookieAccount).toBe(replacement);
        guestResponse = response({ account: replacement, ...(created === undefined ? {} : { created }) });
        return guestResponse;
      }
      return undefined;
    };
    const boundary = calls.length;
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" })); });
    expect(finishIdentity).toBeDefined();
    // The cookie changes after /me was rejected, before the unbound guest request.
    cookieAccount = replacement;
    await act(async () => finishIdentity(denied()));
    await screen.findByText(/We couldn't start a new guest visit/);
    expect(screen.getByRole("heading", { name: "Your shopping session expired" })).toBeVisible();
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Fixture product" })).not.toBeInTheDocument();
    expect(calls.slice(boundary).map(({ path, account }) => ({ path, account }))).toEqual([
      { path: "/v1/shopper/me", account: null },
      { path: "/v1/shopper/auth/guest", account: null },
    ]);
    expect(guestResponse!.headers.has("set-cookie")).toBe(false);
    expect(matching("/v1/shopper/auth/logout")).toHaveLength(0);
    expect(writes).toHaveLength(0);
    expect(cookieAccount).toBe(replacement);
    const count = calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); });
    expect(calls).toHaveLength(count);
  });

  it("still binds new-guest logout if the cookie changes after the identity check", async () => {
    await open();
    cookieAccount = null;
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    await suspended();
    cookieAccount = a;
    override = (call) => {
      if (call.path === "/v1/shopper/me") {
        cookieAccount = b;
        return response({ account: a });
      }
      return undefined;
    };
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    await screen.findByText(/We couldn't start a new guest visit/);
    expect(matching("/v1/shopper/auth/logout")[0].account).toBe(a.id);
    expect(matching("/v1/shopper/auth/guest")).toHaveLength(0);
    expect(cookieAccount).toBe(b);
    expect(writes).toHaveLength(0);
  });
});
