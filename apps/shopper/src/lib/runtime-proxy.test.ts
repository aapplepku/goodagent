import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { proxyRuntime } from "./runtime-proxy";

const accountId = "80000000-0000-0000-0000-000000000001";
const upstream = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubEnv("OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST", "");
  vi.stubEnv("OPEN_COMMERCE_API_BASE_URL", "http://127.0.0.1:8000");
  vi.stubEnv("OPEN_COMMERCE_PUBLIC_ORIGINS", "[]");
  upstream.mockReset();
  vi.stubGlobal("fetch", upstream);
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("shopper account precondition proxy", () => {
  it.each(["GET", "POST", "PATCH", "DELETE"])("forwards the %s expectation with the store, cookie and receipt", async (method) => {
    upstream.mockResolvedValue(new Response(null, { status: 204 }));
    const result = await proxyRuntime(new Request("http://localhost:3001/api/runtime/v1/shopper/preferences", {
      method,
      headers: {
        "X-Shopper-Account-Id": accountId,
        "X-Store-Slug": "alpha",
        "Idempotency-Key": "original-receipt",
        cookie: "open_commerce_shopper_session_alpha=synthetic; unrelated=omit",
        authorization: "synthetic-not-forwarded",
      },
    }), ["v1", "shopper", "preferences"]);
    expect(result.status).toBe(204);
    const headers = new Headers(upstream.mock.calls[0][1]?.headers);
    expect(headers.get("X-Shopper-Account-Id")).toBe(accountId);
    expect(headers.get("X-Store-Slug")).toBe("alpha");
    expect(headers.get("Idempotency-Key")).toBe("original-receipt");
    expect(headers.get("cookie")).toBe("open_commerce_shopper_session_alpha=synthetic");
    expect(headers.has("authorization")).toBe(false);
  });

  it("keeps discovery unbound and propagates a mismatch without clearing cookies", async () => {
    upstream.mockResolvedValue(Response.json({ error: { code: "SHOPPER_AUTHENTICATION_FAILED", message: "Session changed" } }, { status: 401 }));
    const response = await proxyRuntime(new Request("http://localhost:3001/api/runtime/v1/shopper/me"), ["v1", "shopper", "me"]);
    expect(new Headers(upstream.mock.calls[0][1]?.headers).has("X-Shopper-Account-Id")).toBe(false);
    expect(response.status).toBe(401);
    expect(response.headers.has("set-cookie")).toBe(false);
    expect(await response.json()).toMatchObject({ error: { message: "Session changed" } });
  });

  it("does not loosen the same-origin boundary for bound requests", async () => {
    const response = await proxyRuntime(new Request("http://localhost:3001/api/runtime/v1/shopper/me", {
      headers: { "X-Shopper-Account-Id": accountId, origin: "https://invalid.example" },
    }), ["v1", "shopper", "me"]);
    expect(response.status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });
});
