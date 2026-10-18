import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ShopperAccount } from "@open-commerce/sdk-typescript";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShopperApp } from "./shopper-app";

const a: ShopperAccount = { id: "80000000-0000-0000-0000-000000000001", username: "alex", display_name: "Alex", is_guest: false, created_at: "2026-10-18T00:00:00Z" };
const b: ShopperAccount = { ...a, id: "80000000-0000-0000-0000-000000000002", username: "blair", display_name: "Blair" };
const store = { slug: "alpha", name: "Alpha Store", description: "Synthetic", currency: "USD" };
const replacementCode = "synthetic-replacement-code";
type Call = { path: string; method: string; account: string | null; store: string | null; key: string | null; body: string };
const calls: Call[] = [];
const invoked: Omit<Call, "body">[] = [];
let cookie: ShopperAccount | null;
let mode: string | undefined;
let override: ((call: Call) => Response | Promise<Response> | undefined) | undefined;
const response = (data: unknown, status = 200) => Response.json(data, { status });
const denied = () => response({ error: { code: "SHOPPER_AUTHENTICATION_FAILED", message: "Synthetic denial", request_id: "fixture" } }, 401);
const matching = (path: string) => calls.filter((call) => call.path === path);

beforeEach(() => {
  cookie = a;
  mode = undefined;
  override = undefined;
  calls.length = 0;
  invoked.length = 0;
  sessionStorage.clear();
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const identity = {
      path: new URL(request.url).pathname.replace("/api/runtime", ""), method: request.method,
      account: request.headers.get("x-shopper-account-id"), store: request.headers.get("x-store-slug"),
      key: request.headers.get("idempotency-key"),
    };
    invoked.push(identity);
    const call: Call = { ...identity, body: await request.text() };
    calls.push(call);
    if (call.account && call.account !== cookie?.id) return denied();
    const custom = override?.(call);
    if (custom) return custom;
    if (call.path === "/v1/shopper/auth/recover") {
      cookie = a;
      return response({ account: a, recovery_code: replacementCode });
    }
    if (!cookie) return denied();
    if (call.path === "/v1/shopper/me") return response({ account: cookie });
    if (call.path === "/v1/shopper/discovery") return response({ catalog_status: "ready", product_count: 2, suggestions: [], ...(mode === undefined ? {} : { conversation_mode: mode }) });
    if (["/v1/shopper/conversations", "/v1/shopper/memories"].includes(call.path)) return response({ items: [] });
    if (call.path === "/v1/shopper/checkout/current") return response(null);
    if (call.path === "/v1/shopper/cart") return response({ id: null, status: "open", lines: [], item_count: 0, version: 0 });
    throw new Error(`Unexpected synthetic endpoint: ${call.method} ${call.path}`);
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function open() {
  const rendered = render(<ShopperApp store={store} />);
  await screen.findByText("Alex");
  await waitFor(() => expect(screen.getByRole("button", { name: "Open cart with 0 items" })).toBeVisible());
  return rendered;
}
async function expire() {
  cookie = null;
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await screen.findByRole("heading", { name: "Your shopping session expired" });
}
function recoverAccount() {
  fireEvent.click(screen.getByRole("button", { name: "Use a recovery code" }));
  submitRecovery();
}
function submitRecovery() {
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alex" } });
  fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "synthetic-original-code" } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "synthetic-new-password" } });
  fireEvent.submit(screen.getByRole("form", { name: "Recover account" }));
}

function deferred<T = Response>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
const acknowledge = () => fireEvent.click(screen.getByRole("button", { name: "I stored it privately; continue" }));

async function openGuest() {
  cookie = { ...a, id: "80000000-0000-0000-0000-000000000003", is_guest: true, display_name: "Guest" };
  const rendered = render(<ShopperApp store={store} />);
  await screen.findByText("Guest");
  fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "Unsent guest request" } });
  fireEvent.click(screen.getByRole("button", { name: "Save your progress" }));
  return rendered;
}
async function requestRecoveryFromGuest() {
  const rendered = await openGuest();
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  expect(await screen.findByRole("heading", { name: "Recover your shopping account" })).toHaveFocus();
  expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
  expect(screen.getByRole("form", { name: "Recover account" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Back to sign in" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Start a new guest visit" })).not.toBeInTheDocument();
  expect(matching("/v1/shopper/auth/recover")).toHaveLength(0);
  return rendered;
}

describe("guest account-panel recovery uses the verified receipt flow", () => {
  it("blocks a same-event recovery handoff while registration is pending and keeps its code", async () => {
    await openGuest();
    const guest = cookie!;
    const pending = deferred();
    override = call => call.path === "/v1/shopper/auth/register" ? pending.promise : undefined;
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Member" } });
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "member" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-password" } });
    const recover = screen.getByRole("button", { name: "Recover" });
    act(() => {
      fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
      fireEvent.click(recover);
    });
    await waitFor(() => expect(matching("/v1/shopper/auth/register")).toHaveLength(1));
    expect(screen.queryByRole("heading", { name: "Recover your shopping account" })).not.toBeInTheDocument();
    expect(recover).toBeDisabled();
    cookie = { ...guest, is_guest: false, display_name: "Member" };
    await act(async () => pending.resolve(response({ account: cookie, recovery_code: replacementCode })));
    expect(await screen.findByText(replacementCode)).toBeVisible();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(0);
  });

  it("keeps the code until acknowledgement and does not silently merge the guest's draft", async () => {
    await requestRecoveryFromGuest();
    expect(screen.getByText(/does not transfer this guest visit's conversations or cart/)).toBeVisible();
    submitRecovery();
    expect(await screen.findByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
    expect(matching("/v1/shopper/auth/recover")[0]).toMatchObject({ account: null, store: "alpha" });
    expect(matching("/v1/shopper/me").at(-1)?.account).toBe(a.id);
    expect(calls.filter(call => call.account === a.id && call.path !== "/v1/shopper/me")).toHaveLength(0);
    expect(screen.queryByRole("textbox", { name: "Shopping request" })).not.toBeInTheDocument();
    acknowledge();
    await screen.findByText("Alex");
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveValue("");
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(a.id);
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(calls.some(call => call.path === "/v1/shopper/auth/merge")).toBe(false);
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(JSON.stringify([localStorage, sessionStorage])).not.toContain(replacementCode);
  });

  it("returns to the same still-valid guest visit without a recovery mutation", async () => {
    await requestRecoveryFromGuest();
    fireEvent.click(screen.getByRole("button", { name: "Return to current visit" }));
    await screen.findByText("Guest");
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveValue("Unsent guest request");
    expect(calls.every(call => call.method === "GET")).toBe(true);
  });

  it("keeps invalid credentials local without claiming expiry or exposing server text", async () => {
    await requestRecoveryFromGuest();
    override = call => call.path === "/v1/shopper/auth/recover"
      ? response({ error: { code: "STORE_ERROR", message: "private-server-detail", request_id: "fixture" } }, 401)
      : undefined;
    submitRecovery();
    expect(await screen.findByRole("alert")).toHaveTextContent("Recovery could not be confirmed");
    expect(screen.queryByText("private-server-detail")).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(screen.queryByLabelText("Replacement recovery code")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Return to current visit" }));
    await screen.findByText("Guest");
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveValue("Unsent guest request");
  });

  it("retries verification and acknowledgement without resubmitting recovery", async () => {
    await requestRecoveryFromGuest();
    let unavailable = true;
    override = call => unavailable && call.path === "/v1/shopper/me" && call.account === a.id
      ? response({ error: { message: "Synthetic offline" } }, 503) : undefined;
    submitRecovery();
    await screen.findByRole("heading", { name: "Check your recovered session" });
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    unavailable = false;
    fireEvent.click(screen.getByRole("button", { name: "Check recovered session" }));
    await screen.findByLabelText("Replacement recovery code");
    unavailable = true;
    acknowledge();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Keep this receipt"));
    expect(screen.getByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
    unavailable = false;
    acknowledge();
    await screen.findByText("Alex");
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("hides the receipt if the recovered cookie changes before verification", async () => {
    await requestRecoveryFromGuest();
    override = call => {
      if (call.path === "/v1/shopper/auth/recover") {
        cookie = b;
        return response({ account: a, recovery_code: replacementCode });
      }
      return undefined;
    };
    submitRecovery();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("recovered session changed"));
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("discards a delayed recovery response after navigating to a different store", async () => {
    const view = await requestRecoveryFromGuest();
    const pending = deferred();
    override = call => call.path === "/v1/shopper/auth/recover" ? pending.promise : undefined;
    submitRecovery();
    await waitFor(() => expect(matching("/v1/shopper/auth/recover")).toHaveLength(1));
    cookie = b;
    view.rerender(<ShopperApp store={{ ...store, slug: "beta", name: "Beta Store" }} />);
    await screen.findByText("Blair");
    await act(async () => pending.resolve(response({ account: a, recovery_code: replacementCode })));
    expect(screen.getByText("Blair")).toBeVisible();
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Recover your shopping account" })).not.toBeInTheDocument();
    expect(calls.filter(call => call.path === "/v1/shopper/me" && call.account === a.id)).toHaveLength(0);
  });
});

describe("shopper welcome and recovery with real transports", () => {
  it("discloses Basic mode before the first send", async () => {
    mode = "basic";
    await open();
    expect(await screen.findByText("Basic mode: AI chat is not connected.")).toBeVisible();
    expect(screen.queryByText(/Give me the whole situation/)).not.toBeInTheDocument();
    expect(matching("/v1/shopper/chat")).toHaveLength(0);
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveAttribute("placeholder", "Search for a product or category...");
  });

  it.each([undefined, "unknown", "future-unsupported-value"])("uses neutral copy for %s, not assumed Basic or connected mode", async (value) => {
    mode = value;
    await open();
    expect(screen.getByLabelText("Conversation mode")).toHaveTextContent("Search the store catalog.");
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveAttribute("placeholder", "Search the store catalog...");
    expect(screen.queryByText(/Give me the whole situation|AI chat is not connected|AI mode:/)).not.toBeInTheDocument();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("describes selected AI mode without implying credentials or connectivity", async () => {
    mode = "model_configured";
    await open();
    expect(screen.getByLabelText("Conversation mode")).toHaveTextContent("AI mode: connection not checked.");
    expect(screen.queryByText(/AI is connected|key validated|AI chat is not connected/)).not.toBeInTheDocument();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("retains a verified replacement code until acknowledgment before restoring a same-account draft", async () => {
    await open();
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "My unsent request" } });
    await expire();
    recoverAccount();
    expect(await screen.findByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
    expect(screen.queryByRole("textbox", { name: "Shopping request" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")[0]).toMatchObject({ account: null, store: "alpha" });
    expect(matching("/v1/shopper/me").at(-1)?.account).toBe(a.id);
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "I stored it privately; continue" }));
    expect(await screen.findByRole("textbox", { name: "Shopping request" })).toHaveValue("My unsent request");
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(matching("/v1/shopper/chat")).toHaveLength(0);
    expect(matching("/v1/shopper/me").slice(-2).map((call) => call.account)).toEqual([a.id, a.id]);
    expect(matching("/v1/shopper/cart").at(-1)?.account).toBe(a.id);
    expect(JSON.parse(matching("/v1/shopper/auth/recover")[0].body)).toEqual({ username: "alex", code: "synthetic-original-code", password: "synthetic-new-password" });
  });

  it("preserves the exact failed chat separately from a newer draft without replay on recovery", async () => {
    await open();
    override = (call) => { if (call.path === "/v1/shopper/chat") throw new TypeError("Synthetic response loss"); return undefined; };
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "Original request" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    const original = matching("/v1/shopper/chat")[0];
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "New draft" } });
    await expire();
    recoverAccount();
    await screen.findByLabelText("Replacement recovery code");
    acknowledge();
    expect(await screen.findByRole("textbox", { name: "Shopping request" })).toHaveValue("New draft");
    expect(matching("/v1/shopper/chat")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await waitFor(() => expect(matching("/v1/shopper/chat")).toHaveLength(2));
    expect(matching("/v1/shopper/chat")[1]).toEqual(original);
  });

  it.each([403, 503])("retains a hidden receipt on verification HTTP %s and retries only the bound read", async (status) => {
    await open();
    await expire();
    override = (call) => call.path === "/v1/shopper/me" && call.account ? response({ error: { message: "Do not expose synthetic secret", code: "failed", request_id: "fixture" } }, status) : undefined;
    recoverAccount();
    await screen.findByText(/Choose Check recovered session/);
    expect(screen.queryByLabelText("Replacement recovery code")).not.toBeInTheDocument();
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByText(/Do not expose synthetic secret/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Recover account" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    override = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Check recovered session" }));
    expect(await screen.findByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
    expect(matching("/v1/shopper/me").slice(-2).every((call) => call.account === a.id)).toBe(true);
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it.each(["denied", "mismatched-body"])("drops the receipt on %s initial verification without adopting another account", async (failure) => {
    await open();
    await expire();
    override = (call) => {
      if (call.path === "/v1/shopper/me" && call.account) {
        cookie = b;
        return failure === "denied" ? denied() : response({ account: b });
      }
      return undefined;
    };
    recoverAccount();
    await screen.findByText(/The recovered session changed/);
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("hides a verified code when the acknowledgment check discovers a changed cookie", async () => {
    await open();
    await expire();
    recoverAccount();
    await screen.findByLabelText("Replacement recovery code");
    cookie = b;
    acknowledge();
    await screen.findByText(/The recovered session changed/);
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blair");
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("retains a displayed code when acknowledgment verification is temporarily unavailable", async () => {
    await open();
    await expire();
    recoverAccount();
    await screen.findByLabelText("Replacement recovery code");
    override = (call) => call.path === "/v1/shopper/me" ? response({}, 503) : undefined;
    acknowledge();
    await screen.findByText(/Keep this receipt and check again/);
    expect(screen.getByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
    expect(matching("/v1/shopper/cart")).toHaveLength(1);
    override = undefined;
    acknowledge();
    await screen.findByRole("textbox", { name: "Shopping request" });
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("does not replay a recovery whose response was lost or claim its replacement code was delivered", async () => {
    await open();
    await expire();
    override = (call) => {
      if (call.path === "/v1/shopper/auth/recover") { cookie = a; throw new TypeError("Synthetic lost response containing private-request-detail"); }
      return undefined;
    };
    recoverAccount();
    await screen.findByText(/Recovery could not be confirmed. It may have completed/);
    expect(screen.queryByLabelText("Replacement recovery code")).not.toBeInTheDocument();
    expect(screen.queryByText(/private-request-detail/)).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByRole("textbox", { name: "Shopping request" });
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(screen.queryByText(/code.*saved|replacement code/i)).not.toBeInTheDocument();
  });

  it("makes a missing-code response explicit without fabricating delivery or repeating recovery", async () => {
    await open();
    await expire();
    override = (call) => {
      if (call.path === "/v1/shopper/auth/recover") { cookie = a; return response({ account: a }); }
      return undefined;
    };
    recoverAccount();
    await screen.findByRole("heading", { name: "Replacement recovery code unavailable" });
    expect(screen.queryByLabelText("Replacement recovery code")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I stored it privately; continue" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue without a replacement code" }));
    await screen.findByRole("textbox", { name: "Shopping request" });
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("keeps recovery credentials and code out of browser storage and forgets the code on unmount", async () => {
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const rendered = await open();
    await expire();
    recoverAccount();
    await screen.findByLabelText("Replacement recovery code");
    expect(JSON.stringify(storage.mock.calls)).not.toMatch(/synthetic-(original-code|replacement-code|new-password)/);
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
    rendered.unmount();
    await open();
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
  });

  it("does not restore A's draft when explicitly recovering verified B", async () => {
    await open();
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "A private draft" } });
    await expire();
    override = (call) => {
      if (call.path === "/v1/shopper/auth/recover") { cookie = b; return response({ account: b, recovery_code: replacementCode }); }
      return undefined;
    };
    recoverAccount();
    await screen.findByLabelText("Replacement recovery code");
    expect(matching("/v1/shopper/me").at(-1)?.account).toBe(b.id);
    acknowledge();
    expect(await screen.findByRole("textbox", { name: "Shopping request" })).toHaveValue("");
    expect(screen.getByText("Blair")).toBeVisible();
  });

  it.each(["post", "verification", "acknowledgment"].flatMap(stage =>
    ["before", "after"].map(order => ({ stage, order })),
  ))("fences a late $stage response when new-store checkout is recorded $order it", async ({ stage, order }) => {
    const rendered = await open();
    await waitFor(() => expect(matching("/v1/shopper/checkout/current")).toHaveLength(1));
    fireEvent.change(screen.getByRole("textbox", { name: "Shopping request" }), { target: { value: "Alpha private draft" } });
    await expire();
    const pending = deferred();
    const betaLog = deferred<void>();
    const originalText = Request.prototype.text;
    // Hold only fixture bookkeeping so an already-started, valid Beta read can
    // finish on either side of Alpha's obsolete recovery response.
    vi.spyOn(Request.prototype, "text").mockImplementation(function (this: Request) {
      const body = originalText.call(this);
      return this.headers.get("x-store-slug") === "beta" && new URL(this.url).pathname.endsWith("/checkout/current")
        ? betaLog.promise.then(() => body) : body;
    });
    let held = false;
    override = (call) => {
      if (stage === "post" && call.path === "/v1/shopper/auth/recover") { held = true; return pending.promise; }
      if (stage === "verification" && call.path === "/v1/shopper/me" && call.account) { held = true; return pending.promise; }
      return undefined;
    };
    recoverAccount();
    if (stage === "acknowledgment") {
      await screen.findByLabelText("Replacement recovery code");
      override = (call) => {
        if (call.path === "/v1/shopper/me" && call.account) { held = true; return pending.promise; }
        return undefined;
      };
      acknowledge();
    }
    await waitFor(() => expect(held).toBe(true));
    cookie = b;
    override = undefined;
    rendered.rerender(<ShopperApp store={{ ...store, slug: "beta", name: "Beta Store" }} />);
    await screen.findByText("Blair");
    const betaRequests = ["me", "conversations", "memories", "discovery", "cart", "checkout/current"].map(path => ({
      path: `/v1/shopper/${path}`, method: "GET", account: path === "me" ? null : b.id, store: "beta", key: null,
    })).sort((left, right) => left.path.localeCompare(right.path));
    await waitFor(() => expect(invoked.filter(call => call.store === "beta").sort((left, right) => left.path.localeCompare(right.path))).toEqual(betaRequests));
    await waitFor(() => expect(calls.filter(call => call.store === "beta").sort((left, right) => left.path.localeCompare(right.path))).toEqual(
      betaRequests.filter(call => call.path !== "/v1/shopper/checkout/current").map(call => ({ ...call, body: "" })),
    ));
    const started = [...invoked];
    const alphaCalls = calls.filter(call => call.store === "alpha");
    const finishBetaRead = async () => {
      const boundary = calls.length;
      await act(async () => betaLog.resolve());
      expect(calls.slice(boundary)).toEqual([{ path: "/v1/shopper/checkout/current", method: "GET", account: b.id, store: "beta", key: null, body: "" }]);
      expect(invoked).toEqual(started);
    };
    if (order === "before") await finishBetaRead();
    const boundary = calls.length;
    await act(async () => pending.resolve(response({ account: a, recovery_code: replacementCode })));
    expect(calls).toHaveLength(boundary);
    expect(invoked).toEqual(started);
    if (order === "after") await finishBetaRead();
    expect(calls.filter(call => call.store === "alpha")).toEqual(alphaCalls);
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    expect(matching("/v1/shopper/chat")).toHaveLength(0);
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
    expect(screen.queryByText("Alex")).not.toBeInTheDocument();
    expect(screen.getByText("Blair")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Shopping request" })).toHaveValue("");
  });

  it("does not start verification after an abandoned recovery POST completes", async () => {
    const rendered = await open();
    await expire();
    const pending = deferred();
    override = (call) => call.path === "/v1/shopper/auth/recover" ? pending.promise : undefined;
    recoverAccount();
    await waitFor(() => expect(matching("/v1/shopper/auth/recover")).toHaveLength(1));
    rendered.unmount();
    const boundary = calls.length;
    await act(async () => pending.resolve(response({ account: a, recovery_code: replacementCode })));
    expect(calls).toHaveLength(boundary);
    expect(screen.queryByText(replacementCode)).not.toBeInTheDocument();
  });

  it("keeps one recovery POST under Strict Mode and duplicate submit events, with no receipt polling", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    render(<StrictMode><ShopperApp store={store} /></StrictMode>);
    await screen.findByText("Alex");
    await expire();
    const pending = deferred();
    override = (call) => call.path === "/v1/shopper/auth/recover" ? pending.promise : undefined;
    await act(async () => {
      recoverAccount();
      fireEvent.submit(screen.getByRole("form", { name: "Recover account" }));
      fireEvent.submit(screen.getByRole("form", { name: "Recover account" }));
    });
    expect(matching("/v1/shopper/auth/recover")).toHaveLength(1);
    cookie = a;
    await act(async () => pending.resolve(response({ account: a, recovery_code: replacementCode })));
    await screen.findByLabelText("Replacement recovery code");
    const boundary = calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); });
    expect(calls).toHaveLength(boundary);
    expect(screen.getByLabelText("Replacement recovery code")).toHaveTextContent(replacementCode);
  });

  it("does not apply an old store's late mode response to the next store", async () => {
    const pending = deferred();
    override = (call) => call.path === "/v1/shopper/discovery" ? pending.promise : undefined;
    const rendered = await open();
    mode = "model_configured";
    override = undefined;
    cookie = b;
    rendered.rerender(<ShopperApp store={{ ...store, slug: "beta", name: "Beta Store" }} />);
    await screen.findByText("AI mode: connection not checked.");
    await act(async () => pending.resolve(response({ catalog_status: "ready", product_count: 2, suggestions: [], conversation_mode: "basic" })));
    expect(screen.getByLabelText("Conversation mode")).toHaveTextContent("AI mode: connection not checked.");
    expect(screen.getByText("Blair")).toBeVisible();
    expect(screen.queryByText("Basic mode: AI chat is not connected.")).not.toBeInTheDocument();
  });

  it.each(["preview", "legacy"])("does not add code recovery to unsupported %s entry", async (entry) => {
    render(<ShopperApp store={entry === "preview" ? { ...store, preview: true } : undefined} />);
    await screen.findByText("Alex");
    await expire();
    expect(screen.queryByRole("button", { name: "Use a recovery code" })).not.toBeInTheDocument();
  });

  it("directs a fresh-guest conflict to Check session without adopting the cookie", async () => {
    await open();
    await expire();
    cookie = { ...b, is_guest: true };
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    expect(await screen.findByText(/No new visit was confirmed. Choose Check session/)).toBeVisible();
    expect(screen.queryByText("Blair")).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/guest")).toHaveLength(0);
  });
});
