import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ShopperAccount, ShopperDiscoveryResponse, Storefront } from "@open-commerce/sdk-typescript";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShopperApp } from "./shopper-app";

const store: Storefront = { slug: "alpha", name: "Alpha Store", description: "Synthetic", currency: "USD", sample_data: false };
const a: ShopperAccount = { id: "80000000-0000-0000-0000-000000000001", username: "alex", display_name: "Alex", is_guest: false, created_at: "2026-10-18T00:00:00Z" };
const b: ShopperAccount = { ...a, id: "80000000-0000-0000-0000-000000000002", username: "blair", display_name: "Blair" };
const asset = (id = 1, slug = "alpha") => `/api/runtime/v1/shopper/assets/90000000-0000-0000-0000-${String(id).padStart(12, "0")}?store=${slug}`;
const suggestion = (image_url: string | null, category = "Mugs") => ({ label: `Explore ${category}`, query: `Find ${category.toLowerCase()}`, category, image_url });
const discovery = (suggestions: NonNullable<ShopperDiscoveryResponse["suggestions"]>): ShopperDiscoveryResponse => ({ catalog_status: "ready", product_count: 2, conversation_mode: "basic", suggestions });
type Call = { path: string; method: string; account: string | null; store: string | null; body: string };
const calls: Call[] = [];
let cookie: ShopperAccount | null;
let payload: ShopperDiscoveryResponse;
let override: ((call: Call) => Response | Promise<Response> | undefined) | undefined;
const response = (data: unknown, status = 200) => Response.json(data, { status });
const denied = () => response({ error: { code: "SHOPPER_AUTHENTICATION_FAILED", message: "Synthetic denial", request_id: "fixture" } }, 401);
const matching = (path: string) => calls.filter((call) => call.path === path);
const thumbnails = () => [...document.querySelectorAll<HTMLImageElement>(".prompt-row img")];
const absolute = (url: string) => new URL(url, window.location.href).href;

function credentialAsset() {
  const url = new URL(asset(), "https://example.invalid");
  url.username = "synthetic-user";
  url.password = "synthetic-password";
  return url.href;
}

beforeEach(() => {
  cookie = a;
  payload = discovery([]);
  override = undefined;
  calls.length = 0;
  sessionStorage.clear();
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const call: Call = {
      path: new URL(request.url).pathname.replace("/api/runtime", ""), method: request.method,
      account: request.headers.get("x-shopper-account-id"), store: request.headers.get("x-store-slug"),
      body: await request.text(),
    };
    calls.push(call);
    if (call.account && call.account !== cookie?.id) return denied();
    const custom = override?.(call);
    if (custom) return custom;
    if (!cookie) return denied();
    if (call.path === "/v1/shopper/me") return response({ account: cookie });
    if (call.path === "/v1/shopper/discovery") return response(payload);
    if (["/v1/shopper/conversations", "/v1/shopper/memories"].includes(call.path)) return response({ items: [] });
    if (call.path === "/v1/shopper/checkout/current") return response(null);
    if (call.path === "/v1/shopper/cart") return response({ id: null, status: "open", lines: [], item_count: 0, version: 0 });
    if (call.path === "/v1/shopper/chat") return response({}, 503);
    throw new Error(`Unexpected synthetic endpoint: ${call.method} ${call.path}`);
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function open(profile: Storefront | undefined = store) {
  const rendered = render(<ShopperApp store={profile} />);
  await screen.findByText("2 products at Alpha Store");
  await waitFor(() => expect(screen.getByRole("button", { name: "Open cart with 0 items" })).toBeVisible());
  return rendered;
}

function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("store-grounded welcome through ShopperApp and real transports", () => {
  it("keeps a no-image named store truthful and its original starter usable", async () => {
    payload = discovery([suggestion(null)]);
    await open();
    expect(screen.queryAllByAltText(/^Sample catalog:/)).toHaveLength(0);
    expect(document.querySelector(".empty-visual")).not.toBeInTheDocument();
    expect(thumbnails()).toHaveLength(0);
    expect(screen.queryByRole("link", { name: "Amazon.com / ABO" })).not.toBeInTheDocument();
    expect(screen.getByText("Basic mode: AI chat is not connected.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Explore Mugs" }));
    await screen.findByRole("button", { name: "Retry same request" });
    expect(matching("/v1/shopper/chat")).toHaveLength(1);
    expect(matching("/v1/shopper/chat")[0]).toMatchObject({ store: "alpha", account: a.id });
    expect(JSON.parse(matching("/v1/shopper/chat")[0].body)).toMatchObject({ content: "Find mugs", expected_account_id: a.id });
  });

  it.each([0, 1, 3])("renders %s supplied thumbnails once, directly, with no extra data queries", async (count) => {
    payload = discovery(Array.from({ length: count }, (_, index) => suggestion(asset(index + 1), `Category ${index}`)));
    await open();
    expect(document.querySelectorAll("img")).toHaveLength(count);
    expect(thumbnails().map((image) => image.src)).toEqual(payload.suggestions?.map((item) => absolute(item.image_url!)));
    for (const image of thumbnails()) {
      expect(image).toHaveAttribute("referrerpolicy", "no-referrer");
      expect(image).toHaveAttribute("width", "30");
      expect(image).toHaveAttribute("height", "30");
      expect(image).not.toHaveAttribute("srcset");
      expect(image).toHaveAttribute("alt", "");
    }
    expect(matching("/v1/shopper/discovery")).toHaveLength(1);
    expect(matching("/v1/shopper/catalog")).toHaveLength(0);
    expect(calls.every((call) => call.method === "GET")).toBe(true);
    expect(calls.every((call) => call.store === "alpha")).toBe(true);
    expect(matching("/v1/shopper/discovery")[0].account).toBe(a.id);
  });

  it.each([
    ["remote", `https://example.invalid${asset()}`],
    ["absolute same origin", `http://localhost:3000${asset()}`],
    ["protocol-relative", `//example.invalid${asset()}`],
    ["credentials", credentialAsset()],
    ["arbitrary path", "/abo-images/B07QCR35JF.jpg"],
    ["merchant asset", asset().replace("/shopper/", "/merchant/")],
    ["wrong store", asset(1, "beta")],
    ["duplicate store", `${asset()}&store=alpha`],
    ["conflicting store", `${asset()}&store=beta`],
    ["extra query", `${asset()}&token=synthetic`],
    ["missing store", asset().split("?")[0]],
    ["fragment", `${asset()}#image`],
    ["empty fragment", `${asset()}#`],
    ["leading space", ` ${asset()}`],
    ["newline", `${asset()}\n`],
    ["backslash", asset().replace("/assets/", "\\assets/")],
    ["dot segment", asset().replace("/assets/", "/ignored/../assets/")],
    ["encoded path", asset().replace("assets", "%61ssets")],
    ["encoded store", asset().replace("alpha", "%61lpha")],
    ["malformed uuid", "/api/runtime/v1/shopper/assets/not-a-uuid?store=alpha"],
    ["data URL", "data:image/png;base64,AA=="],
  ])("rejects %s without losing the starter", async (_label, url) => {
    payload = discovery([suggestion(url)]);
    await open();
    expect(thumbnails()).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Explore Mugs" })).toBeEnabled();
    expect(matching("/v1/shopper/catalog")).toHaveLength(0);
  });

  it("keeps failed-image geometry and never retries that URL during discovery refresh", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    payload = discovery([suggestion(asset())]);
    await open();
    const button = screen.getByRole("button", { name: "Explore Mugs" });
    const image = thumbnails()[0];
    const slot = image.parentElement;
    expect(slot).not.toBe(button);
    fireEvent.error(image);
    expect(thumbnails()).toHaveLength(0);
    expect(slot).toBeInTheDocument();
    expect(slot).toHaveAttribute("aria-hidden", "true");
    expect(button).toBeEnabled();
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(matching("/v1/shopper/discovery")).toHaveLength(3);
    expect(thumbnails()).toHaveLength(0);
    expect(slot).toBeInTheDocument();
    payload = discovery([suggestion(asset(2))]);
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(thumbnails()[0].src).toBe(absolute(asset(2)));
    fireEvent.click(button);
    await screen.findByRole("button", { name: "Retry same request" });
    expect(matching("/v1/shopper/chat")).toHaveLength(1);
  });

  it("uses only the verified sample flag for credits, and hides credits after the last usable image fails", async () => {
    payload = discovery([suggestion(asset())]);
    const rendered = await open({ ...store, sample_data: true });
    expect(screen.getByRole("link", { name: "Amazon.com / ABO" })).toBeVisible();
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toBeVisible();
    expect(screen.getByText(/Sample catalog photos:/)).toBeVisible();
    rendered.rerender(<ShopperApp store={{ ...store, name: "ABO Sample photos", sample_data: false }} />);
    expect(screen.queryByRole("link", { name: "Amazon.com / ABO" })).not.toBeInTheDocument();
    rendered.rerender(<ShopperApp store={{ ...store, sample_data: true }} />);
    fireEvent.error(thumbnails()[0]);
    expect(screen.queryByRole("link", { name: "Amazon.com / ABO" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Explore Mugs" })).toBeEnabled();
  });

  it("does not show sample credits for a sample store with no usable images", async () => {
    payload = discovery([suggestion(null), suggestion(asset(1, "beta"), "Throws")]);
    await open({ ...store, sample_data: true });
    expect(thumbnails()).toHaveLength(0);
    expect(screen.queryByRole("link", { name: "Amazon.com / ABO" })).not.toBeInTheDocument();
  });

  it("retains credits and other starters when one of several sample images fails", async () => {
    payload = discovery([suggestion(asset()), suggestion(asset(2), "Throws")]);
    await open({ ...store, sample_data: true, preview: true });
    fireEvent.error(thumbnails()[0]);
    expect(thumbnails().map((image) => image.src)).toEqual([absolute(asset(2))]);
    expect(screen.getByRole("link", { name: "Amazon.com / ABO" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Explore Mugs" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Explore Throws" })).toBeEnabled();
    expect(screen.queryAllByAltText(/^Sample catalog:/)).toHaveLength(0);
  });

  it("does not apply an old image's late error to a replacement discovery image", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    payload = discovery([suggestion(asset())]);
    await open();
    const oldImage = thumbnails()[0];
    payload = discovery([suggestion(asset(2))]);
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(oldImage).not.toBeInTheDocument();
    fireEvent.error(oldImage);
    expect(thumbnails().map((image) => image.src)).toEqual([absolute(asset(2))]);
    expect(screen.getByRole("button", { name: "Explore Mugs" })).toBeEnabled();
  });

  it("preserves the explicit legacy welcome and generic sign-in artwork", async () => {
    payload = discovery([suggestion("/abo-images/B07QCR35JF.jpg")]);
    const rendered = render(<ShopperApp />);
    await screen.findByRole("button", { name: "Explore Mugs" });
    expect(screen.getAllByAltText(/^Sample catalog:/)).toHaveLength(3);
    expect(thumbnails()[0].src).toBe(absolute("/abo-images/B07QCR35JF.jpg"));
    expect(screen.getByRole("link", { name: "Amazon.com / ABO" })).toBeVisible();
    rendered.unmount();
    cookie = null;
    render(<ShopperApp />);
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.getAllByAltText(/^Sample catalog:/)).toHaveLength(3);
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toBeVisible();
  });

  it("fences late original-store discovery after navigating to another store", async () => {
    const pending = deferred();
    override = (call) => call.path === "/v1/shopper/discovery" && call.store === "alpha" ? pending.promise : undefined;
    const rendered = render(<ShopperApp store={store} />);
    await waitFor(() => expect(matching("/v1/shopper/discovery")).toHaveLength(1));
    cookie = b;
    payload = discovery([suggestion(asset(2, "beta"), "Throws")]);
    rendered.rerender(<ShopperApp store={{ ...store, slug: "beta", name: "Beta Store" }} />);
    await screen.findByRole("button", { name: "Explore Throws" });
    await act(async () => pending.resolve(response(discovery([suggestion(asset())]))));
    expect(thumbnails().map((image) => image.src)).toEqual([absolute(asset(2, "beta"))]);
    expect(screen.queryByRole("button", { name: "Explore Mugs" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/discovery").map((call) => [call.store, call.account])).toEqual([["alpha", a.id], ["beta", b.id]]);
  });

  it("removes images on a changed-cookie denial and ignores a late A read after explicit B recovery", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    payload = discovery([suggestion(asset())]);
    await open();
    const pending = deferred();
    override = (call) => call.path === "/v1/shopper/discovery" ? pending.promise : undefined;
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    cookie = b;
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(document.querySelectorAll("img")).toHaveLength(0);
    const count = calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(calls).toHaveLength(count);
    override = undefined;
    payload = discovery([suggestion(asset(2), "Throws")]);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByRole("button", { name: "Explore Throws" });
    await act(async () => pending.resolve(response(discovery([suggestion(asset())]))));
    expect(thumbnails().map((image) => image.src)).toEqual([absolute(asset(2))]);
    expect(screen.getByText("Blair")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Explore Mugs" })).not.toBeInTheDocument();
    expect(matching("/v1/shopper/auth/logout")[0].account).toBe(a.id);
    expect(matching("/v1/shopper/discovery").at(-1)?.account).toBe(b.id);
  });

  it("does not replay a failed thumbnail under Strict Mode or parent rerender", async () => {
    payload = discovery([suggestion(asset())]);
    const rendered = render(<StrictMode><ShopperApp store={store} /></StrictMode>);
    await screen.findByRole("button", { name: "Explore Mugs" });
    fireEvent.error(thumbnails()[0]);
    rendered.rerender(<StrictMode><ShopperApp store={{ ...store }} /></StrictMode>);
    expect(thumbnails()).toHaveLength(0);
    expect(matching("/v1/shopper/discovery")).toHaveLength(1);
  });

  it("does not reset an unchanged image source when the parent rerenders", async () => {
    payload = discovery([suggestion(asset())]);
    const rendered = await open();
    const original = thumbnails()[0];
    const assignment = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    rendered.rerender(<ShopperApp store={{ ...store }} />);
    expect(thumbnails()[0]).toBe(original);
    expect(assignment).not.toHaveBeenCalled();
  });

  it("does not reset a surviving image source when its sibling fails", async () => {
    payload = discovery([suggestion(asset()), suggestion(asset(2), "Throws")]);
    await open();
    const [failed, original] = thumbnails();
    const assignment = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    fireEvent.error(failed);
    expect(thumbnails()).toEqual([original]);
    expect(assignment).not.toHaveBeenCalled();
  });

  it("does not reset image sources while editing the unsent shopper message", async () => {
    payload = discovery([suggestion(asset())]);
    await open();
    const original = thumbnails()[0];
    const assignment = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    const composer = screen.getByRole("textbox");
    for (const value of ["m", "mu", "mug"]) fireEvent.change(composer, { target: { value } });
    expect(thumbnails()[0]).toBe(original);
    expect(assignment).not.toHaveBeenCalled();
    expect(matching("/v1/shopper/chat")).toHaveLength(0);
  });
});
