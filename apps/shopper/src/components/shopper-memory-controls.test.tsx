import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ShopperAccount, ShopperMemory } from "@open-commerce/sdk-typescript";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShopperApp } from "./shopper-app";

const account: ShopperAccount = { id: "80000000-0000-0000-0000-000000000001", username: "alex", display_name: "Alex", memory_enabled: true, is_guest: false, created_at: "2026-10-18T00:00:00Z" };
const other: ShopperAccount = { ...account, id: "80000000-0000-0000-0000-000000000002", display_name: "Blair" };
const memory: ShopperMemory = { id: "82000000-0000-0000-0000-000000000001", content: "I prefer reusable cotton bags", created_at: account.created_at };
const store = { slug: "memory-fixture", name: "Synthetic Store", description: "Offline fixture", currency: "USD" };
type Call = { path: string; method: string; account: string | null; store: string | null; key: string | null; body: string };
const calls: Call[] = [];
let cookie: ShopperAccount | null;
let items: ShopperMemory[];
let override: ((call: Call) => Response | Promise<Response> | undefined) | undefined;
const response = (data: unknown, status = 200) => Response.json(data, { status });
const errorResponse = (status: number, code: string) => response({ error: { code, message: "Synthetic request rejected", request_id: "fixture" } }, status);
const deletions = () => calls.filter(call => call.method === "DELETE" && call.path.startsWith("/v1/shopper/memories/"));

beforeEach(() => {
  cookie = { ...account };
  items = [memory];
  override = undefined;
  calls.length = 0;
  sessionStorage.clear(); localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const call: Call = { path: new URL(request.url).pathname.replace("/api/runtime", ""), method: request.method,
      account: request.headers.get("x-shopper-account-id"), store: request.headers.get("x-store-slug"),
      key: request.headers.get("idempotency-key"), body: await request.text() };
    calls.push(call);
    if (!cookie || (call.account && call.account !== cookie.id)) return errorResponse(401, "SHOPPER_AUTHENTICATION_FAILED");
    const custom = override?.(call);
    if (custom) return custom;
    if (call.path === "/v1/shopper/me") return response({ account: cookie });
    if (call.path === "/v1/shopper/preferences") {
      cookie = { ...cookie, memory_enabled: JSON.parse(call.body).enabled };
      return response({ account: cookie });
    }
    if (call.path === "/v1/shopper/memories") return response({ items });
    if (call.method === "DELETE" && call.path.startsWith("/v1/shopper/memories/")) {
      items = items.filter(item => item.id !== call.path.split("/").at(-1));
      return response({ deleted: true, memory_id: memory.id });
    }
    if (call.path === "/v1/shopper/discovery") return response({ catalog_status: "ready", product_count: 1, suggestions: [], conversation_mode: "basic" });
    if (call.path === "/v1/shopper/conversations") return response({ items: [] });
    if (call.path === "/v1/shopper/checkout/current") return response(null);
    if (call.path === "/v1/shopper/cart") return response({ id: null, status: "open", lines: [], item_count: 0, version: 0 });
    throw new Error("Unexpected synthetic endpoint");
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function open() {
  const rendered = render(<ShopperApp store={store} />);
  await screen.findByRole("textbox", { name: "Shopping request" });
  await waitFor(() => expect(screen.getByRole("button", { name: /Shopping memory/ })).toHaveTextContent("1"));
  fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
  await screen.findByRole("button", { name: `Forget ${memory.content}` });
  return rendered;
}
const forget = () => fireEvent.click(screen.getByRole("button", { name: `Forget ${memory.content}` }));
const retry = () => fireEvent.click(screen.getByRole("button", { name: /Retry removing/ }));
function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
}

describe("shopper memory management and uncertain deletion", () => {
  it("keeps stored preferences visible with an honest off state and selective deletion", async () => {
    cookie = { ...account, memory_enabled: false };
    await open();
    expect(screen.getByText(/Shopping memory is off/)).toBeVisible();
    expect(screen.queryByText("No saved preferences yet.")).not.toBeInTheDocument();
    forget();
    expect(await screen.findByText("No saved preferences yet.")).toBeVisible();
    expect(cookie?.memory_enabled).toBe(false);
    expect(calls.filter(call => call.method === "PATCH")).toHaveLength(0);
  });

  it("does not hide retained preferences while an off-setting refresh is pending", async () => {
    await open();
    const refresh = deferred();
    override = call => call.path === "/v1/shopper/memories" ? refresh.promise : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Close memory" }));
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Remember shopping preferences" }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "Remember shopping preferences" })).not.toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    expect(screen.getByRole("button", { name: `Forget ${memory.content}` })).toBeVisible();
    await act(async () => refresh.resolve(response({ items })));
    expect(await screen.findByText(/Shopping memory is off/)).toBeVisible();
  });

  it("replays a lost committed deletion with the same scoped key and no automatic write", async () => {
    let committedKey: string | null = null;
    override = call => {
      if (call.method !== "DELETE") return;
      if (!committedKey) {
        committedKey = call.key;
        items = [];
        return Promise.reject(new TypeError("Synthetic response lost after commit"));
      }
      return call.key === committedKey ? response({ deleted: true, memory_id: memory.id }) : errorResponse(404, "SHOPPER_MEMORY_NOT_FOUND");
    };
    await open(); forget();
    await screen.findByRole("button", { name: /Retry removing/ });
    expect(deletions()).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Close memory" }));
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    await waitFor(() => expect(calls.filter(call => call.path === "/v1/shopper/memories").length).toBeGreaterThan(1));
    retry();
    await waitFor(() => expect(screen.queryByRole("button", { name: /Retry removing/ })).not.toBeInTheDocument());
    expect(await screen.findByText("No saved preferences yet.")).toBeVisible();
    expect(deletions()).toHaveLength(2);
    expect(deletions()[1]).toMatchObject({ key: deletions()[0].key, account: account.id, store: store.slug });
    expect(sessionStorage.length).toBe(0); expect(localStorage.length).toBe(0);
  });

  it("suppresses duplicate removal clicks while a request is in flight", async () => {
    const pending = deferred();
    override = call => call.method === "DELETE" ? pending.promise : undefined;
    await open();
    const button = screen.getByRole("button", { name: `Forget ${memory.content}` });
    fireEvent.click(button); fireEvent.click(button);
    await waitFor(() => expect(deletions()).toHaveLength(1));
    expect(button).toBeDisabled();
    await act(async () => pending.resolve(response({ deleted: true, memory_id: memory.id })));
    expect(await screen.findByText("No saved preferences yet.")).toBeVisible();
  });

  it.each([403, 404, 500])("does not turn %s into a successful deletion", async status => {
    override = call => call.method === "DELETE" ? errorResponse(status, status === 404 ? "SHOPPER_MEMORY_NOT_FOUND" : "SYNTHETIC_DENIAL") : undefined;
    await open(); forget();
    await screen.findByRole("button", { name: /Retry removing/ });
    expect(screen.getByText(memory.content, { exact: true })).toBeVisible();
    retry();
    await waitFor(() => expect(deletions()).toHaveLength(2));
    expect(deletions()[1].key).toBe(deletions()[0].key);
    expect(screen.queryByText("No saved preferences yet.")).not.toBeInTheDocument();
  });

  it("keeps an interrupted key only after explicit same-account session recovery", async () => {
    let first = true;
    override = call => {
      if (call.method === "DELETE" && first) { first = false; return errorResponse(401, "SHOPPER_AUTHENTICATION_FAILED"); }
    };
    await open(); forget();
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(screen.queryByText(memory.content)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByRole("textbox", { name: "Shopping request" });
    expect(deletions()).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    retry();
    await screen.findByText("No saved preferences yet.");
    expect(deletions()[1].key).toBe(deletions()[0].key);
  });

  it("discards interrupted removal on different-account recovery", async () => {
    override = call => call.method === "DELETE" ? errorResponse(401, "SHOPPER_AUTHENTICATION_FAILED") : undefined;
    await open(); forget();
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    cookie = other; items = [];
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blair");
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    expect(screen.queryByRole("button", { name: /Retry removing/ })).not.toBeInTheDocument();
    expect(screen.queryByText(memory.content)).not.toBeInTheDocument();
    expect(deletions()).toHaveLength(1);
  });

  it.each([200, 401, 500])("ignores a late %s removal result after switching store", async status => {
    const pending = deferred();
    override = call => call.method === "DELETE" ? pending.promise : undefined;
    const rendered = await open(); forget();
    await waitFor(() => expect(deletions()).toHaveLength(1));
    cookie = other; items = [];
    rendered.rerender(<ShopperApp store={{ ...store, slug: "another-store", name: "Other Store" }} />);
    await screen.findByText("Blair");
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    await act(async () => pending.resolve(status === 200 ? response({ deleted: true, memory_id: memory.id }) : errorResponse(status, "SYNTHETIC_LATE_ERROR")));
    expect(screen.queryByRole("button", { name: /Retry removing/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
    expect(screen.queryByText(memory.content)).not.toBeInTheDocument();
    expect(deletions()).toHaveLength(1);
    expect(deletions()[0]).toMatchObject({ account: account.id, store: store.slug });
  });

  it("does not persist unresolved removal receipts across unmount/reload", async () => {
    override = call => call.method === "DELETE" ? Promise.reject(new TypeError("Synthetic uncertainty")) : undefined;
    const rendered = await open(); forget();
    await screen.findByRole("button", { name: /Retry removing/ });
    rendered.unmount();
    await open();
    expect(screen.queryByRole("button", { name: /Retry removing/ })).not.toBeInTheDocument();
    expect(deletions()).toHaveLength(1);
    expect(sessionStorage.length).toBe(0); expect(localStorage.length).toBe(0);
  });

  it("maintains independent keys for concurrent preference removals", async () => {
    const second = { ...memory, id: "82000000-0000-0000-0000-000000000002", content: "I prefer blue mugs" };
    const pending = deferred();
    await open();
    items = [memory, second];
    fireEvent.click(screen.getByRole("button", { name: "Close memory" }));
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    await screen.findByRole("button", { name: `Forget ${second.content}` });
    override = call => call.method === "DELETE" && call.path.endsWith(memory.id) ? pending.promise : undefined;
    forget();
    fireEvent.click(screen.getByRole("button", { name: `Forget ${second.content}` }));
    await waitFor(() => expect(deletions()).toHaveLength(2));
    expect(deletions()[0].key).not.toBe(deletions()[1].key);
    await waitFor(() => expect(screen.queryByText(second.content)).not.toBeInTheDocument());
    await act(async () => pending.resolve(response({ deleted: true, memory_id: memory.id })));
    expect(await screen.findByText("No saved preferences yet.")).toBeVisible();
  });

  it("retains temporary guest disclosure when memory is off", async () => {
    cookie = { ...account, is_guest: true, memory_enabled: false };
    await open();
    expect(screen.getByText(/expire after 24 hours/)).toBeVisible();
    expect(screen.getByText(/Shopping memory is off/)).toBeVisible();
    forget();
    await screen.findByText("No saved preferences yet.");
    expect(cookie?.is_guest).toBe(true);
  });
});
