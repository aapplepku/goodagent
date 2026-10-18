import { describe, expect, it } from "vitest";
import { OpenCommerceClient } from "./transport";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fixture(body: unknown = {}, status = 200) {
  const calls: Request[] = [];
  const client = new OpenCommerceClient({
    baseUrl: "http://api.test/",
    fetcher: async (input, init) => {
      calls.push(new Request(input, init));
      return jsonResponse(body, status);
    },
  });
  return { client, calls };
}

describe("OpenCommerceClient", () => {
  it("returns readiness details for its documented 503 response", async () => {
    const body = {
      status: "not_ready",
      dependencies: [{ name: "postgres", ok: false, latency_ms: 2 }],
    };
    const { client } = fixture(body, 503);
    await expect(client.ready()).resolves.toEqual(body);
  });

  it("sends idempotency keys and JSON for simulator mutations", async () => {
    const { client, calls } = fixture({}, 201);
    await client.createSimulatorInstance(
      "acquisition_v1",
      { seed: 42 },
      "create-1",
    );
    expect(calls[0].url).toBe(
      "http://api.test/v1/simulator/scenarios/acquisition_v1/instances",
    );
    expect(calls[0].headers.get("Idempotency-Key")).toBe("create-1");
    expect(await calls[0].json()).toEqual({ seed: 42 });
    expect(calls[0].credentials).toBe("omit");
    expect(calls[0].redirect).toBe("error");
  });

  it("supports capabilities and root simulator creation", async () => {
    const { client, calls } = fixture();
    await client.capabilities();
    await client.createSimulatorInstanceFromRequest(
      { scenario_id: "acquisition_v1", seed: 42 },
      "root-create",
    );
    expect(calls[0].url).toBe("http://api.test/v1/capabilities");
    expect(calls[1].url).toBe("http://api.test/v1/simulator/instances");
    expect(calls[1].headers.get("Idempotency-Key")).toBe("root-create");
  });

  it("searches in the selected goal context without a write key", async () => {
    const { client, calls } = fixture();
    await client.search({
      query: "trail",
      mode: "hybrid_boosted",
      goal_context_id: "goal-1",
    });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].headers.has("Idempotency-Key")).toBe(false);
    expect(await calls[0].json()).toEqual({
      query: "trail",
      mode: "hybrid_boosted",
      goal_context_id: "goal-1",
    });
    await client.searchRules("goal-1");
    expect(calls[1].url).toBe(
      "http://api.test/v1/search/rules?goal_context_id=goal-1",
    );
  });

  it("sends a write key for bounded event ingestion", async () => {
    const { client, calls } = fixture({ accepted: 1, deduplicated: 0 });
    await client.ingestEventBatch(
      {
        events: [
          {
            event_id: "evt-1",
            occurred_at: "2026-09-04T00:00:00Z",
            session_id: "session-1",
            type: "product_impression",
            surface: "search",
          },
        ],
      },
      "events-1",
    );
    expect(calls[0].headers.get("Idempotency-Key")).toBe("events-1");
    expect("createSearchRule" in client).toBe(false);
    expect("deleteSearchRule" in client).toBe(false);
    expect("evaluateController" in client).toBe(false);
  });

  it("uses idempotent shopper cart and test-checkout commands", async () => {
    const { client, calls } = fixture({}, 200);
    await client.addShopperCartItem(
      { product_id: "product-1", quantity: 2 },
      "cart-add-1",
    );
    await client.confirmShopperCheckout(
      { checkout_id: "11111111-1111-4111-8111-111111111111", payment_method: "test_success" },
      "checkout-confirm-1",
    );

    expect(calls[0].url).toBe("http://api.test/v1/shopper/cart/items");
    expect(calls[0].headers.get("Idempotency-Key")).toBe("cart-add-1");
    expect(await calls[0].json()).toEqual({ product_id: "product-1", quantity: 2 });
    expect(calls[1].url).toBe("http://api.test/v1/shopper/checkout/confirm");
    expect(calls[1].headers.get("Idempotency-Key")).toBe("checkout-confirm-1");
  });

  it("requires a nonempty write key and preserves conflict status", async () => {
    const { client, calls } = fixture({}, 409);
    expect(() => client.createGoal({}, "")).toThrow("idempotency key");
    expect(calls).toHaveLength(0);
    await expect(
      client.executeAction("action-1", "execute-key"),
    ).rejects.toThrow("Open Commerce API request failed: 409");
    expect(calls[0].headers.get("Idempotency-Key")).toBe("execute-key");
  });

  it("preserves safe error metadata", async () => {
    const { client } = fixture(
      {
        error: {
          type: "not_found",
          code: "NOT_FOUND",
          message: "goal not found",
          details: {},
          request_id: "req-1",
          retryable: false,
        },
      },
      404,
    );
    await expect(client.goal("missing")).rejects.toMatchObject({
      status: 404,
      error: { request_id: "req-1", message: "goal not found" },
    });
  });

  it("retains SSE cursors and returns text", async () => {
    const calls: Request[] = [];
    const client = new OpenCommerceClient({
      baseUrl: "http://api.test",
      fetcher: async (input, init) => {
        calls.push(new Request(input, init));
        return new Response("id: 7\nevent: trace\ndata: {}\n\n", {
          headers: { "content-type": "text/event-stream" },
        });
      },
    });
    await expect(client.runEvents("run-1", "6")).resolves.toContain("id: 7");
    expect(calls[0].headers.get("Last-Event-ID")).toBe("6");
  });
});

// Compiled by tsc, never dispatched. These must remain schema-level type errors.
function rejectsInvalidContracts(client: OpenCommerceClient) {
  // @ts-expect-error Direct provider-like search writes are not an API operation.
  void client.api.POST("/v1/search/rules", { body: {} });
  // @ts-expect-error Mutation headers require an idempotency key.
  void client.api.POST("/v1/goals", { body: {} });
  // @ts-expect-error Ranking modes come from the API enum.
  void client.search({ query: "trail", mode: "unrestricted" });
  // @ts-expect-error Typed requests do not accept arbitrary code.
  void client.createGoal({ script: "execute anything" }, "key");
  void client.confirmShopperCheckout(
    {
      checkout_id: "checkout-1",
      // @ts-expect-error Checkout accepts only the finite local test methods.
      payment_method: "card_4242",
    },
    "key",
  );
}
void rejectsInvalidContracts;
