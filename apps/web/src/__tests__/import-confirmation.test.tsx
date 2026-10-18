import type { ImportReview, StoreReadiness } from "@open-commerce/sdk-typescript";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StoreAccess } from "@/components/store-setup";
import { deferred, denied, expectBinding, merchantServer, ownerA } from "./merchant-test-server";

const firstToken = "sha256:" + "a".repeat(64);
const latestToken = "sha256:" + "b".repeat(64);
function setup() {
  const model = {
    review: {
      id: "import-a", filename: "reviewed.csv", status: "review", review_fingerprint: firstToken,
      expires_at: "2099-01-01T00:00:00Z", columns: ["id", "title", "price", "cost"],
      mapping: { product_id: "id", title: "title", price: "price" }, currency: "USD",
      row_count: 1, product_count: 1, products: [], errors: [], warnings: [],
    } as ImportReview,
    intercept: undefined as ((request: Request) => Response | Promise<Response> | undefined) | undefined,
  };
  const server = merchantServer(async (request) => {
    const intercepted = model.intercept?.(request);
    if (intercepted) return intercepted;
    const path = new URL(request.url).pathname;
    if (path.endsWith("/measurements")) return Response.json({});
    if (path.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (path.endsWith("/merchant/store")) {
      const state: StoreReadiness = {
        store: ownerA.store, latest_import_id: model.review.id, image_failures: 0,
        indexing: model.review.indexing ?? { status: "not_configured" },
        checklist: { catalog_verified: model.review.status === "confirmed" },
      };
      return Response.json(state);
    }
    if (path.endsWith("/confirm")) {
      const body = await request.clone().json();
      if (body.expected_review_fingerprint !== model.review.review_fingerprint) return denied(409);
      model.review = { ...model.review, status: "confirmed", catalog_id: "catalog-a", indexing: {
        catalog_id: "catalog-a", status: "ready", product_count: 1, indexed_product_count: 1,
      } };
    }
    if (path.includes("/imports/")) return Response.json(model.review);
    return denied(404);
  });
  function changeMapping() {
    model.review = { ...model.review, review_fingerprint: latestToken,
      mapping: { ...model.review.mapping, price: "cost" }, currency: "EUR" };
  }
  return { model, server, changeMapping };
}
async function mount() {
  render(<StoreAccess><p>Workspace</p></StoreAccess>);
  return await screen.findByRole("button", { name: "Confirm products" });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("review-bound import confirmation", () => {
  it("requires a fresh read and explicit new confirmation after another tab changes the review", async () => {
    const { server, changeMapping } = setup();
    const confirm = await mount();
    changeMapping();
    const reads = server.calls("/imports/import-a").length;
    fireEvent.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent("Request blocked");
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("button", { name: "Validate mapping" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "1 Products" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByLabelText("Price currency")).toHaveValue("USD");
    expect(server.calls("/imports/import-a")).toHaveLength(reads);
    expect(server.calls("/confirm")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(confirm).toBeEnabled());
    expect(screen.getByLabelText("Price currency")).toHaveValue("EUR");
    expect(screen.getByLabelText("price", { exact: true })).toHaveValue("cost");
    expect(server.calls("/confirm")).toHaveLength(1);
    fireEvent.click(confirm);
    expect(await screen.findByText("Try your store privately")).toBeVisible();
    const [first, latest] = server.calls("/confirm");
    expect(await first.json()).toEqual({ expected_review_fingerprint: firstToken });
    expect(await latest.json()).toEqual({ expected_review_fingerprint: latestToken });
    expect(latest.headers.get("Idempotency-Key")).not.toBe(first.headers.get("Idempotency-Key"));
    expectBinding(first, ownerA);
    expectBinding(latest, ownerA);
    expect(server.requests.filter((request) => request.method !== "GET")).toHaveLength(2);
  });

  it("retains the old context and recovery control after a failed latest-review read", async () => {
    const { model, server, changeMapping } = setup();
    const confirm = await mount();
    changeMapping();
    fireEvent.click(confirm);
    await screen.findByRole("alert");
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/imports/import-a") ? denied(503) : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Review latest mapping" })).toBeEnabled());
    expect(screen.getByText("reviewed.csv")).toBeVisible();
    expect(screen.getByLabelText("Price currency")).toHaveValue("USD");
    expect(confirm).toBeDisabled();
    expect(server.calls("/confirm")).toHaveLength(1);
    model.intercept = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(confirm).toBeEnabled());
    expect(server.calls("/confirm")).toHaveLength(1);
  });

  it.each(["network", "malformed", "unavailable"])("retries an unknown %s response with the exact key and body", async (failure) => {
    const { model, server } = setup();
    const confirm = await mount();
    model.intercept = (request) => {
      if (!new URL(request.url).pathname.endsWith("/confirm")) return;
      if (failure === "network") throw new TypeError("Synthetic offline failure");
      return failure === "malformed" ? new Response("not-json") : denied(503);
    };
    fireEvent.click(confirm);
    await screen.findByRole("alert");
    expect(confirm).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Review latest mapping" })).not.toBeInTheDocument();
    model.intercept = undefined;
    fireEvent.click(confirm);
    await screen.findByText("Try your store privately");
    const [first, retry] = server.calls("/confirm");
    expect(await retry.json()).toEqual(await first.json());
    expect(retry.headers.get("Idempotency-Key")).toBe(first.headers.get("Idempotency-Key"));
  });

  it("refreshes after an acknowledged confirm whose follow-up read fails without another POST", async () => {
    const { model, server } = setup();
    const confirm = await mount();
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/merchant/store") ? denied(503) : undefined;
    fireEvent.click(confirm);
    await screen.findByRole("alert");
    expect(confirm).toBeDisabled();
    model.intercept = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Review latest mapping" })).not.toBeInTheDocument());
    expect(server.calls("/confirm")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Confirm products" })).not.toBeInTheDocument();
  });

  it("requires a token refresh for an old pending response without sending tokenless confirmation", async () => {
    const { model, server } = setup();
    model.review.review_fingerprint = null;
    const confirm = await mount();
    expect(confirm).toBeDisabled();
    model.review.review_fingerprint = firstToken;
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(confirm).toBeEnabled());
    expect(server.calls("/confirm")).toHaveLength(0);
  });

  it("retires a late recovery read on owner logout without issuing confirmation", async () => {
    const { model, server, changeMapping } = setup();
    const confirm = await mount();
    changeMapping();
    fireEvent.click(confirm);
    await screen.findByRole("alert");
    const pending = deferred<Response>();
    model.intercept = (request) => new URL(request.url).pathname.endsWith("/imports/import-a") ? pending.promise : undefined;
    fireEvent.click(screen.getByRole("button", { name: "Review latest mapping" }));
    await waitFor(() => expect(server.calls("/imports/import-a")).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByLabelText("Username");
    await act(async () => { pending.resolve(Response.json(model.review)); });
    expect(screen.queryByText("reviewed.csv")).not.toBeInTheDocument();
    expect(server.calls("/confirm")).toHaveLength(1);
  });
});
