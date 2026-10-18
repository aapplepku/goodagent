import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createShopperClient, createShopperTransport } from "./api";

const request = vi.fn<typeof fetch>();
const errorBody = (code = "STORE_UNAVAILABLE") => ({ error: { message: "Unavailable", code, request_id: "fixture" } });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  request.mockReset();
  vi.stubGlobal("fetch", request);
  window.history.replaceState({}, "", "/s/alpha");
});
afterEach(() => vi.unstubAllGlobals());

describe.each(["sdk", "manual"] as const)("%s store transport", (kind) => {
  function read(transport: ReturnType<typeof createShopperTransport>) {
    return kind === "sdk" ? transport.client.shopperCatalog() : transport.request("/v1/shopper/catalog");
  }

  it("keeps immutable account/store bindings separate from explicit unbound discovery", async () => {
    request.mockImplementation(async () => response({ items: [] }));
    const base = createShopperTransport();
    const a = base.forAccount("80000000-0000-0000-0000-000000000001");
    window.history.pushState({}, "", "/s/beta");
    const b = a.forAccount("80000000-0000-0000-0000-000000000002");
    await read(a);
    await read(b);
    await read(a);
    await read(base);
    await read(a.forAccount(null));
    expect(request.mock.calls.map(([, init]) => new Headers(init?.headers).get("x-shopper-account-id")))
      .toEqual(["80000000-0000-0000-0000-000000000001", "80000000-0000-0000-0000-000000000002", "80000000-0000-0000-0000-000000000001", null, null]);
    expect(request.mock.calls.every(([, init]) => new Headers(init?.headers).get("x-store-slug") === "alpha")).toBe(true);
    expect(a.forAccount("80000000-0000-0000-0000-000000000001")).toBe(a);
  });

  it("retains the store generation fence and gate on account-bound descendants", async () => {
    let active = true;
    const onUnavailable = vi.fn();
    const base = createShopperTransport({ isActive: () => active, onUnavailable });
    const bound = base.forAccount("80000000-0000-0000-0000-000000000001");
    request.mockResolvedValueOnce(response(errorBody(), 404));
    await expect(read(bound)).rejects.toMatchObject({ status: 404 });
    expect(onUnavailable).toHaveBeenCalledOnce();
    active = false;
    await expect(read(bound)).rejects.toMatchObject({ name: "AbortError" });
    await expect(read(bound.forAccount(null))).rejects.toMatchObject({ name: "AbortError" });
    expect(request).toHaveBeenCalledOnce();
  });

  it("captures its originating store before the URL changes", async () => {
    request.mockImplementation(async () => response({ items: [] }));
    const transport = createShopperTransport();
    await read(transport);
    window.history.pushState({}, "", "/s/beta");
    await read(transport);
    for (const [, init] of request.mock.calls) {
      expect(new Headers(init?.headers).get("x-store-slug")).toBe("alpha");
      expect(init).toMatchObject({ credentials: "include", cache: "no-store" });
    }
  });

  it("honors explicit scope and keeps a legacy transport unscoped after navigation", async () => {
    request.mockImplementation(async () => response({ items: [] }));
    const explicit = createShopperTransport({ slug: "owner-store" });
    const legacy = createShopperTransport({ slug: null });
    window.history.pushState({}, "", "/s/beta");
    await read(explicit);
    await read(legacy);
    expect(new Headers(request.mock.calls[0][1]?.headers).get("x-store-slug")).toBe("owner-store");
    expect(new Headers(request.mock.calls[1][1]?.headers).has("x-store-slug")).toBe(false);
  });

  it.each([
    [404, "STORE_UNAVAILABLE", true],
    [404, "STORE_REQUEST_BLOCKED", false],
    [401, "STORE_UNAVAILABLE", false],
    [403, "STORE_UNAVAILABLE", false],
    [503, "STORE_UNAVAILABLE", false],
  ])("gates only dedicated denial: %s/%s", async (status, code, gates) => {
    const onUnavailable = vi.fn();
    request.mockResolvedValueOnce(response(errorBody(code), status));
    await expect(read(createShopperTransport({ slug: "alpha", onUnavailable })))
      .rejects.toMatchObject({ status, error: { code } });
    expect(onUnavailable).toHaveBeenCalledTimes(gates ? 1 : 0);
  });

  it("ignores a departed generation's delayed denial and fences subsequent requests", async () => {
    let resolve!: (value: Response) => void;
    let active = true;
    request.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const onUnavailable = vi.fn();
    const transport = createShopperTransport({ slug: "alpha", isActive: () => active, onUnavailable });
    const pending = read(transport);
    active = false;
    resolve(response(errorBody(), 404));
    await expect(pending).rejects.toMatchObject({ status: 404 });
    expect(onUnavailable).not.toHaveBeenCalled();
    await expect(read(transport)).rejects.toMatchObject({ name: "AbortError" });
    expect(request).toHaveBeenCalledOnce();
  });

  it("does not gate malformed errors or network failures", async () => {
    const onUnavailable = vi.fn();
    const transport = createShopperTransport({ onUnavailable });
    request.mockResolvedValueOnce(new Response("Not JSON", { status: 404 }));
    await expect(read(transport)).rejects.toBeDefined();
    request.mockRejectedValueOnce(new TypeError("Offline"));
    await expect(read(transport)).rejects.toBeInstanceOf(TypeError);
    expect(onUnavailable).not.toHaveBeenCalled();
  });
});

it.each([401, 403, 503])("manual requests preserve HTTP %s for JSON and non-JSON failures", async (status) => {
  const shopperRequest = createShopperTransport().request;
  request.mockResolvedValueOnce(response(errorBody("test"), status));
  await expect(shopperRequest("/v1/shopper/account")).rejects.toMatchObject({ status, message: "Unavailable" });
  request.mockResolvedValueOnce(new Response("Not JSON", { status }));
  await expect(shopperRequest("/v1/shopper/account")).rejects.toBeInstanceOf(OpenCommerceApiError);
  request.mockResolvedValueOnce(new Response("Not JSON", { status }));
  await expect(shopperRequest("/v1/shopper/account")).rejects.toMatchObject({ status });
});

it("retains no-content success, the supplied key and JSON body on manual writes", async () => {
  const shopperRequest = createShopperTransport().request;
  request.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await expect(shopperRequest("/v1/shopper/data", "DELETE", { fixture: true }, "fixed-key")).resolves.toBeNull();
  const [url, init] = request.mock.calls[0];
  expect(url).toBe(window.location.origin + "/api/runtime/v1/shopper/data");
  expect(init).toMatchObject({ method: "DELETE", body: JSON.stringify({ fixture: true }) });
  expect(new Headers(init?.headers).get("Idempotency-Key")).toBe("fixed-key");
});

it("does not turn malformed manual success into an expired session", async () => {
  request.mockResolvedValueOnce(new Response("Not JSON", { status: 200 }));
  await expect(createShopperTransport().request("/v1/shopper/account")).rejects.not.toBeInstanceOf(OpenCommerceApiError);
});

it("SDK writes retain the supplied key and request properties after scope injection", async () => {
  request.mockResolvedValueOnce(response({}));
  const client = createShopperClient({ slug: "alpha" });
  window.history.pushState({}, "", "/s/beta");
  await client.addShopperCartItem({ product_id: "fixture", quantity: 1 }, "fixed-key");
  const [input, init] = request.mock.calls[0];
  expect(input).toBeInstanceOf(Request);
  expect((input as Request).method).toBe("POST");
  expect(new Headers(init?.headers).get("Idempotency-Key")).toBe("fixed-key");
  expect(new Headers(init?.headers).get("x-store-slug")).toBe("alpha");
  expect(await (input as Request).json()).toEqual({ product_id: "fixture", quantity: 1 });
});
