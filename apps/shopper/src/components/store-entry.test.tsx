import type { Storefront } from "@open-commerce/sdk-typescript";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StorePage from "@/app/s/[slug]/page";
import { StoreEntry } from "./store-entry";

vi.mock("./shopper-app", () => ({
  ShopperApp: ({ store, initialView }: { store: Storefront; initialView: "chat" | "catalog" }) => (
    <section aria-label="Store catalog" data-initial-view={initialView}>{store.name}{store.preview && <span>Private preview</span>}</section>
  ),
}));

const storefront: Storefront = {
  slug: "trail-table", name: "Trail & Table", description: "Everyday goods", currency: "USD",
};
const request = vi.fn<typeof fetch>();
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}
function path(input: RequestInfo | URL) {
  return new URL(input instanceof Request ? input.url : String(input)).pathname;
}
function go(slug: string, hash = "") {
  window.history.pushState({}, "", "/s/" + slug + hash);
}

beforeEach(() => {
  request.mockReset();
  vi.stubGlobal("fetch", request);
  go(storefront.slug);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("store entry and recovery", () => {
  it.each([false, true])("opens verified preview %s at its intended first task without sending a message", async (preview) => {
    request.mockResolvedValueOnce(response({ ...storefront, preview })).mockResolvedValueOnce(response({}));
    render(<StoreEntry slug={storefront.slug} />);
    expect(await screen.findByRole("region", { name: "Store catalog" })).toHaveAttribute("data-initial-view", preview ? "chat" : "catalog");
    expect(request.mock.calls.map(([input]) => path(input))).toEqual([
      "/api/runtime/v1/shopper/store", "/api/runtime/v1/shopper/auth/guest",
    ]);
  });

  it("shows loading until both store and guest initialization succeed", async () => {
    const pendingStore = deferred();
    const pendingGuest = deferred();
    request.mockReturnValueOnce(pendingStore.promise).mockReturnValueOnce(pendingGuest.promise);
    render(<StoreEntry slug={storefront.slug} />);
    expect(screen.getByRole("status")).toHaveTextContent("Getting your products ready");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Store catalog" })).not.toBeInTheDocument();
    await act(async () => pendingStore.resolve(response(storefront)));
    expect(screen.queryByRole("region", { name: "Store catalog" })).not.toBeInTheDocument();
    await act(async () => pendingGuest.resolve(response({})));
    expect(await screen.findByRole("region", { name: "Store catalog" })).toHaveTextContent(storefront.name);
    expect(request).toHaveBeenCalledTimes(2);
    expect(path(request.mock.calls[0][0])).toBe("/api/runtime/v1/shopper/store");
    expect(new Headers(request.mock.calls[0][1]?.headers).get("x-store-slug")).toBe(storefront.slug);
    expect(path(request.mock.calls[1][0])).toBe("/api/runtime/v1/shopper/auth/guest");
  });

  it("keeps a denied store closed and rechecks only on an explicit action", async () => {
    request.mockResolvedValueOnce(response({ error: { message: "This store is not accepting shoppers yet.", code: "STORE_UNAVAILABLE" } }, 404));
    render(<StoreEntry slug={storefront.slug} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("This store is not accepting shoppers yet.");
    expect(screen.getByRole("heading", { name: "This store is unavailable" })).toBeVisible();
    expect(screen.queryByRole("region", { name: "Store catalog" })).not.toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Try again" });
    expect(retry).toHaveClass("store-retry");
    expect(retry).toHaveAttribute("type", "button");
    expect(retry.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    retry.focus();
    expect(retry).toHaveFocus();
    expect(request).toHaveBeenCalledTimes(1);
    request.mockResolvedValueOnce(response(storefront)).mockResolvedValueOnce(response({}));
    fireEvent.click(retry);
    expect(await screen.findByRole("region", { name: "Store catalog" })).toBeVisible();
    expect(request).toHaveBeenCalledTimes(3);
  });

  it("does not render products when guest-session initialization fails", async () => {
    request.mockResolvedValueOnce(response(storefront));
    request.mockRejectedValueOnce(new Error("Connection unavailable. Please retry."));
    render(<StoreEntry slug={storefront.slug} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection unavailable. Please retry.");
    expect(screen.queryByRole("region", { name: "Store catalog" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("shares a pending preview initialization under Strict Mode, preserving history and query", async () => {
    const preview = deferred();
    const historyState = { __NA: true, fixture: "keep" };
    window.history.replaceState(historyState, "", "/s/trail-table?sort=price#preview=synthetic-one-use-token");
    request.mockReturnValueOnce(preview.promise);
    request.mockResolvedValueOnce(response({ ...storefront, preview: true }));
    request.mockResolvedValueOnce(response({}));
    render(<StrictMode><StoreEntry slug={storefront.slug} /></StrictMode>);
    expect(request).toHaveBeenCalledOnce();
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?sort=price");
    expect(window.history.state).toEqual(historyState);
    await act(async () => preview.resolve(response({})));
    expect(await screen.findByText("Private preview")).toBeVisible();
    expect(request).toHaveBeenCalledTimes(3);
    expect(path(request.mock.calls[0][0])).toBe("/api/runtime/v1/stores/trail-table/preview");
    expect(request.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify({ token: "synthetic-one-use-token" }) });
  });

  it("does not replay a failed preview on duplicate events, reintroduced fragment or explicit retry", async () => {
    go(storefront.slug, "#preview=synthetic-failed-grant");
    request.mockResolvedValueOnce(response({ error: { message: "Preview expired." } }, 401));
    render(<StrictMode><StoreEntry slug={storefront.slug} /></StrictMode>);
    await screen.findByRole("alert");
    go(storefront.slug, "#preview=synthetic-failed-grant");
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(request).toHaveBeenCalledOnce();
    expect(window.location.hash).toBe("");
    request.mockResolvedValueOnce(response({ error: { message: "Not shared.", code: "STORE_UNAVAILABLE" } }, 404));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Not shared."));
    expect(request.mock.calls.map(([input]) => path(input))).toEqual([
      "/api/runtime/v1/stores/trail-table/preview", "/api/runtime/v1/shopper/store",
    ]);
  });

  it.each(["store", "preview"] as const)("stops abandoned %s initialization before any next request", async (stage) => {
    const old = deferred();
    const alpha = { ...storefront, slug: "alpha", name: "Alpha" };
    const beta = { ...storefront, slug: "beta", name: "Beta" };
    go("alpha", stage === "preview" ? "#preview=synthetic-alpha" : "");
    request.mockImplementation((input, init) => {
      const slug = new Headers(init?.headers).get("x-store-slug");
      if (slug === "alpha") return old.promise;
      return Promise.resolve(response(path(input).endsWith("/store") ? beta : {}));
    });
    const view = render(await StorePage({ params: Promise.resolve({ slug: "alpha" }) }));
    expect(request).toHaveBeenCalledOnce();
    go("beta");
    view.rerender(await StorePage({ params: Promise.resolve({ slug: "beta" }) }));
    expect(await screen.findByRole("region", { name: "Store catalog" })).toHaveTextContent("Beta");
    expect(request).toHaveBeenCalledTimes(3);
    await act(async () => old.resolve(response(alpha)));
    expect(request).toHaveBeenCalledTimes(3);
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
    expect(request.mock.calls.map(([, init]) => new Headers(init?.headers).get("x-store-slug"))).toEqual(["alpha", "beta", "beta"]);
  });

  it("ignores a departed entry's delayed denial after a different store opens", async () => {
    const old = deferred();
    request.mockReturnValueOnce(old.promise);
    const view = render(await StorePage({ params: Promise.resolve({ slug: storefront.slug }) }));
    go("beta");
    request.mockResolvedValueOnce(response({ ...storefront, slug: "beta", name: "Beta" }));
    request.mockResolvedValueOnce(response({}));
    view.rerender(await StorePage({ params: Promise.resolve({ slug: "beta" }) }));
    await screen.findByText("Beta");
    await act(async () => old.resolve(response({ error: { code: "STORE_UNAVAILABLE", message: "Old denial" } }, 404)));
    expect(screen.getByText("Beta")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
