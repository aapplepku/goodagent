// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { contentSecurityPolicy, isLocalRequest } from "./http-security";
import { proxyRuntime, serverApiUrl } from "./runtime-proxy";

function request(init: RequestInit = {}): Request {
  return new Request(
    "http://localhost:53000/api/runtime/v1/goals?limit=10",
    init,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe("local browser boundary", () => {
  it.each([
    ["GET", ["v1", "manager", "catalog"], undefined],
    ["POST", ["v1", "manager", "workspace", "reset"], '{"confirmation":"RESET"}'],
    ["PATCH", ["v1", "merchant", "store"], '{"name":"A draft"}'],
    ["DELETE", ["v1", "manager", "memories", "memory-id"], undefined],
    ["POST", ["v1", "merchant", "imports", "upload"], "title\nA"],
    ["POST", ["v1", "merchant", "auth", "logout"], undefined],
  ])("forwards merchant intent unchanged for %s %j, without tenant authority", async (method, segments, body) => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ error: { message: "Request blocked" } }, { status: 401 }));
    vi.stubGlobal("fetch", fetcher);
    const path = segments as string[];
    const response = await proxyRuntime(request({
      method: method as string,
      body: body as string | undefined,
      headers: {
        "X-Merchant-Owner-Id": "10000000-0000-4000-8000-000000000001",
        "X-Merchant-Store-Id": "20000000-0000-4000-8000-000000000001",
        "Idempotency-Key": "original-intent",
        "Content-Type": path.at(-1) === "upload" ? "text/csv" : "application/json",
        cookie: "open_commerce_merchant_session=replacement-B; unrelated=private",
        authorization: "Bearer untrusted",
        "X-Tenant-Id": "not-authority",
      },
    }), path);
    expect(response.status).toBe(401);
    expect(response.headers.has("set-cookie")).toBe(false);
    const headers = new Headers(fetcher.mock.calls[0][1].headers);
    expect(headers.get("X-Merchant-Owner-Id")).toBe("10000000-0000-4000-8000-000000000001");
    expect(headers.get("X-Merchant-Store-Id")).toBe("20000000-0000-4000-8000-000000000001");
    expect(headers.get("Idempotency-Key")).toBe("original-intent");
    expect(headers.get("cookie")).toBe("open_commerce_merchant_session=replacement-B");
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("X-Tenant-Id")).toBe(false);
  });

  it.each([
    ["POST", ["v1", "goals", "draft"], 100000],
    ["GET", ["v1", "goals", "draft"], 15000],
    ["POST", ["v1", "goals", "review"], 15000],
    ["POST", ["v1", "simulator", "instances", "id", "advance"], 120000],
    ["GET", ["v1", "simulator", "instances", "id", "advance"], 15000],
    ["POST", ["v1", "simulator", "instances", "id", "reset"], 15000],
    ["POST", ["v1", "search"], 120000],
    ["GET", ["v1", "search"], 15000],
    ["POST", ["v1", "search", "evaluate"], 15000],
  ] as const)("bounds %s %j separately", async (method, segments, timeout) => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({})));
    expect(
      (await proxyRuntime(request({ method }), [...segments])).status,
    ).toBe(200);
    expect(deadline).toHaveBeenCalledWith(timeout);
  });
  it("allows an empty POST stream without a JSON content type", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(Response.json({ status: "active" }));
    vi.stubGlobal("fetch", fetcher);
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.close();
      },
    });
    const init: RequestInit & { duplex: "half" } = {
      method: "POST",
      body,
      duplex: "half",
    };
    const response = await proxyRuntime(request(init), [
      "v1",
      "goals",
      "goal-id",
      "activate",
    ]);
    expect(response.status).toBe(200);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][1].body).toBeUndefined();
  });
  it.each<Record<string, string>>([
    { host: "attacker.example" },
    { host: "localhost.attacker.example" },
    { host: "user@localhost" },
    { origin: "https://attacker.example" },
    { origin: "http://localhost:3001" },
    { "sec-fetch-site": "cross-site" },
  ])("rejects an untrusted host or origin: %j", async (headers) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(isLocalRequest(request({ headers }))).toBe(false);
    expect(
      (await proxyRuntime(request({ headers }), ["v1", "goals"])).status,
    ).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("allows loopback requests with the exact browser origin", () => {
    expect(
      isLocalRequest(
        request({ headers: { origin: "http://localhost:53000" } }),
      ),
    ).toBe(true);
    expect(isLocalRequest(new Request("http://127.0.0.1:3000/"))).toBe(true);
    expect(isLocalRequest(new Request("http://[::1]:3000/"))).toBe(true);
  });

  it("requires a nonce in production and disallows arbitrary script execution", () => {
    const policy = contentSecurityPolicy("sample-nonce", false);
    expect(policy).toContain(
      "script-src 'self' 'nonce-sample-nonce' 'strict-dynamic'",
    );
    expect(policy).not.toContain("unsafe-eval");
    expect(policy).not.toContain("script-src 'unsafe-inline'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("connect-src 'self';");
  });

  it.each([
    "https://api:8000",
    "http://attacker.example",
    "http://169.254.169.254",
    "http://user:password@api:8000",
    "http://api:8000/v1",
    "http://api:8000/?target=other",
  ])("refuses an arbitrary upstream: %s", (url) => {
    vi.stubEnv("OPEN_COMMERCE_API_BASE_URL", url);
    expect(serverApiUrl).toThrow("configured local service");
  });

  it("forwards a bounded JSON request, but never cookies or authorization", async () => {
    vi.stubEnv("OPEN_COMMERCE_API_BASE_URL", "http://api:8000");
    const fetcher = vi.fn().mockResolvedValue(
      Response.json(
        { data: [] },
        {
          headers: {
            "set-cookie": "secret=value",
            "x-request-id": "safe-id",
            server: "internal",
          },
        },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    const response = await proxyRuntime(
      request({
        method: "POST",
        body: '{"seed":42}',
        headers: {
          "content-type": "application/json",
          "idempotency-key": "request-key",
          cookie: "session=private",
          authorization: "Bearer secret",
          "x-tenant-id": "other-tenant",
        },
      }),
      ["v1", "goals"],
    );
    expect(response.status).toBe(200);
    const [url, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api:8000/v1/goals?limit=10");
    expect(init).toMatchObject({
      body: '{"seed":42}',
      redirect: "error",
      credentials: "omit",
      cache: "no-store",
    });
    const headers = new Headers(init.headers);
    expect(headers.get("idempotency-key")).toBe("request-key");
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("x-tenant-id")).toBe(false);
    expect(response.headers.has("set-cookie")).toBe(false);
    expect(response.headers.has("server")).toBe(false);
    expect(response.headers.get("x-request-id")).toBe("safe-id");
  });

  it.each([
    ["v1", "..", "admin"],
    ["v1", "%2e%2e"],
    ["v1", "//external"],
    ["debug"],
  ])("rejects an invalid path %j", async (...segments) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect((await proxyRuntime(request(), segments)).status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("bounds streaming input even without a content-length header", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await proxyRuntime(
      request({
        method: "POST",
        body: "x".repeat(65537),
        headers: { "content-type": "application/json" },
      }),
      ["v1", "goals"],
    );
    expect(response.status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("allows the larger bounded body only for dataset profiling", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetcher);
    const body = `{"csv_text":"${"a".repeat(70000)}"}`;
    const accepted = await proxyRuntime(
      request({
        method: "POST",
        body,
        headers: { "content-type": "application/json" },
      }),
      ["v1", "manager", "threads", "thread-id", "datasets", "profile"],
    );
    const rejected = await proxyRuntime(
      request({
        method: "POST",
        body,
        headers: { "content-type": "application/json" },
      }),
      ["v1", "manager", "threads", "thread-id", "messages"],
    );

    expect(accepted.status).toBe(200);
    expect(rejected.status).toBe(413);
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("never forwards a partial body after its deadline", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('{"seed":'));
      },
    });
    const init: RequestInit & { duplex: "half" } = {
      method: "POST",
      body,
      duplex: "half",
      headers: { "content-type": "application/json" },
    };
    const pending = proxyRuntime(request(init), ["v1", "goals"]);
    await vi.advanceTimersByTimeAsync(10001);
    expect((await pending).status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects non-JSON bodies and conceals upstream exceptions", async () => {
    expect(
      (
        await proxyRuntime(request({ method: "POST", body: "bad" }), [
          "v1",
          "goals",
        ])
      ).status,
    ).toBe(415);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValue(new Error("password=private-secret /internal/path")),
    );
    const response = await proxyRuntime(request(), ["v1", "goals"]);
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("private-secret");
  });
});
