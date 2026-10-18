import type { OwnerAuthResponse } from "@open-commerce/sdk-typescript";
import { expect, vi } from "vitest";

export const ownerA: OwnerAuthResponse = {
  user_id: "10000000-0000-4000-8000-000000000001",
  store: { id: "20000000-0000-4000-8000-000000000001", slug: "store-a", name: "Store A", readiness: {} },
};
export const ownerB: OwnerAuthResponse = {
  user_id: "10000000-0000-4000-8000-000000000002",
  store: { id: "20000000-0000-4000-8000-000000000002", slug: "store-b", name: "Store B", readiness: {} },
};

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

export function expectBinding(request: Request, identity: OwnerAuthResponse | null) {
  expect(request.headers.get("X-Merchant-Owner-Id")).toBe(identity?.user_id ?? null);
  expect(request.headers.get("X-Merchant-Store-Id")).toBe(identity?.store.id ?? null);
}

export function denied(status = 401) {
  return Response.json({ error: { code: "REQUEST_BLOCKED", message: "Request blocked", request_id: "test" } }, { status });
}

/** Only the HTTP boundary is doubled: components, hooks and both transports stay real. */
export function merchantServer(handle: (request: Request) => Response | Promise<Response>) {
  const requests: Request[] = [];
  const server = {
    identity: ownerA as OwnerAuthResponse | null,
    protectedStatus: 0,
    legacy: false,
    requests,
    calls: (suffix: string) => requests.filter((request) => new URL(request.url).pathname.endsWith(suffix)),
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(typeof input === "string" ? new URL(input, window.location.origin) : input, init);
    requests.push(request);
    const path = new URL(request.url).pathname;
    if (path.endsWith("/auth/status")) {
      expectBinding(request, null);
      return Response.json({ profile: server.legacy ? "legacy_demo" : "self_hosted", login_method: "local", setup_required: false });
    }
    if (path.endsWith("/auth/me")) {
      expectBinding(request, null);
      return server.identity ? Response.json(server.identity) : denied();
    }
    if (path.endsWith("/auth/login") || path.endsWith("/auth/recover")) {
      expectBinding(request, null);
      return handle(request);
    }
    if (!server.legacy && (server.protectedStatus || !server.identity ||
      request.headers.get("X-Merchant-Owner-Id") !== server.identity.user_id ||
      request.headers.get("X-Merchant-Store-Id") !== server.identity.store.id)) {
      return denied(server.protectedStatus || 401);
    }
    return handle(request);
  }));
  return server;
}
