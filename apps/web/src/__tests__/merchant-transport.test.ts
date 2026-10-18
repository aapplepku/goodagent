import { afterEach, describe, expect, it, vi } from "vitest";
import { createMerchantTransport } from "@/lib/api";
import { deferred, denied, expectBinding, ownerA, ownerB } from "./merchant-test-server";

afterEach(() => vi.unstubAllGlobals());

describe("immutable merchant transport", () => {
  it("binds real SDK, JSON and upload requests and keeps the original retry key", async () => {
    const requests: Request[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push(new Request(typeof input === "string" ? new URL(input, window.location.origin) : input, init));
      return Response.json({});
    }));
    const binding = { ownerId: ownerA.user_id, storeId: ownerA.store.id };
    const a = createMerchantTransport({ binding });
    binding.ownerId = ownerB.user_id;
    binding.storeId = ownerB.store.id;
    const b = createMerchantTransport({ binding });
    await a.client.resetManagerWorkspace({ confirmation: "RESET" }, "original-reset");
    await b.request("/v1/merchant/store");
    await a.client.resetManagerWorkspace({ confirmation: "RESET" }, "original-reset");
    await a.request("/v1/merchant/store", "PATCH", { name: "A draft" }, "original-profile");
    const file = new File(["title\nA"], "a.csv", { type: "text/csv" });
    await a.upload("/v1/merchant/imports/upload?filename=a.csv", file, "original-upload");
    for (const index of [0, 2, 3, 4]) expectBinding(requests[index], ownerA);
    expectBinding(requests[1], ownerB);
    expect(requests[0].headers.get("Idempotency-Key")).toBe("original-reset");
    expect(requests[2].headers.get("Idempotency-Key")).toBe("original-reset");
    expect(requests[3].headers.get("Idempotency-Key")).toBe("original-profile");
    expect(await requests[3].json()).toEqual({ name: "A draft" });
    expect(requests[4].headers.get("Content-Type")).toBe("text/csv");
    expect(requests[4].headers.get("Idempotency-Key")).toBe("original-upload");
    expect(requests.every((request) => request.credentials === "include" && request.cache === "no-store")).toBe(true);
  });

  it("leaves discovery, authentication and legacy clients unbound", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expectBinding(new Request(typeof input === "string" ? new URL(input, window.location.origin) : input, init), null);
      return Response.json({});
    });
    vi.stubGlobal("fetch", fetcher);
    const base = createMerchantTransport();
    await base.request("/v1/merchant/auth/me");
    await base.request("/v1/merchant/auth/login", "POST", {});
    await base.client.managerWorkspace();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it.each([401, 403, 404, 503])("only suspends bound 401, not other statuses (%s)", async (status) => {
    vi.stubGlobal("fetch", vi.fn(async () => denied(status)));
    const expired = vi.fn();
    const bound = createMerchantTransport({ binding: { ownerId: ownerA.user_id, storeId: ownerA.store.id }, onSessionExpired: expired });
    await expect(bound.client.managerWorkspace()).rejects.toMatchObject({ status });
    await expect(bound.request("/v1/merchant/store")).rejects.toMatchObject({ status });
    expect(expired).toHaveBeenCalledTimes(status === 401 ? 2 : 0);
    await expect(createMerchantTransport({ onSessionExpired: expired }).request("/v1/merchant/auth/me")).rejects.toMatchObject({ status });
    expect(expired).toHaveBeenCalledTimes(status === 401 ? 2 : 0);
  });

  it.each([false, true])("rejects a late %s response before publication or another request", async (unauthorized) => {
    const response = deferred<Response>();
    const fetcher = vi.fn(() => response.promise);
    vi.stubGlobal("fetch", fetcher);
    let active = true;
    const expired = vi.fn();
    const old = createMerchantTransport({ binding: { ownerId: ownerA.user_id, storeId: ownerA.store.id }, isActive: () => active, onSessionExpired: expired });
    const pending = old.client.managerWorkspace();
    const result = expect(pending).rejects.toMatchObject({ name: "AbortError" });
    active = false;
    response.resolve(unauthorized ? denied() : Response.json({}));
    await result;
    await expect(old.client.resetManagerWorkspace({ confirmation: "RESET" }, "old-key")).rejects.toMatchObject({ name: "AbortError" });
    await expect(old.request("/v1/merchant/store", "PATCH", {})).rejects.toMatchObject({ name: "AbortError" });
    await expect(old.upload("/v1/merchant/imports/upload", new Blob())).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(expired).not.toHaveBeenCalled();
  });

  it.each(["sdk", "json", "upload"] as const)("fences retirement during %s body parsing", async (kind) => {
    const body = deferred<unknown>();
    const response = Response.json({});
    const parse = kind === "sdk"
      ? vi.spyOn(response, "text").mockImplementation(() => body.promise.then(() => "{}"))
      : vi.spyOn(response, "json").mockImplementation(() => body.promise);
    vi.stubGlobal("fetch", vi.fn(async () => response));
    let active = true;
    const old = createMerchantTransport({ isActive: () => active });
    const pending = kind === "sdk" ? old.client.managerWorkspace() : kind === "json"
      ? old.request("/v1/merchant/store") : old.upload("/v1/merchant/imports/upload", new Blob());
    const result = expect(pending).rejects.toMatchObject({ name: "AbortError" });
    await vi.waitFor(() => expect(parse).toHaveBeenCalled());
    active = false;
    body.resolve({});
    await result;
  });
});
