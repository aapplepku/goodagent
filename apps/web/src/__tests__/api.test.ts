import { afterEach, describe, expect, it, vi } from "vitest";

import { getMeta } from "@/lib/server-api";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("getMeta", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads runtime metadata from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            app_name: "Open Commerce Agent",
            version: "0.0.1",
            environment: "test",
            status: "ready",
            dependencies: [{ name: "postgres", ok: true, latency_ms: 1, detail: null }]
          },
          200
        )
      )
    );

    await expect(getMeta()).resolves.toMatchObject({
      app_name: "Open Commerce Agent",
      status: "ready"
    });
  });

  it("returns null when the API cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({}, 503))
    );

    await expect(getMeta()).resolves.toBeNull();
  });
});
