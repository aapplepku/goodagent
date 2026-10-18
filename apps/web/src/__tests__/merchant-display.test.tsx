import { StrictMode } from "react";
import type { StoreProfile, StoreReadiness } from "@open-commerce/sdk-typescript";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CatalogPage from "@/app/manager/catalog/page";
import { StoreAccess } from "@/components/store-setup";
import { MerchantStoreIdentity } from "@/components/merchant-store-identity";
import { MerchantDisplayProvider, useMerchantDisplay } from "@/lib/merchant-display";
import { deferred, denied, expectBinding, merchantServer, ownerA, ownerB } from "./merchant-test-server";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function readiness(store = ownerA.store): StoreReadiness {
  return { store, latest_import_id: null, indexing: { status: "not_configured" }, image_failures: 0, checklist: {} };
}
function DisplayWorkspace() {
  return <MerchantStoreIdentity />;
}
async function openWorkspace() {
  fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
  return screen.findByRole("group", { name: "Current store" });
}
function saveName(name: string) {
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: name } });
  fireEvent.click(screen.getByRole("button", { name: "Save details" }));
}

describe("verified merchant display identity", () => {
  it("shows name and slug on direct catalog access and distinguishes a same-name recovered store", async () => {
    const server = merchantServer(() => Response.json({
      catalog: null, indexing: { status: "not_configured" }, categories: [], items: [], total: 0, offset: 0, limit: 24,
    }));
    render(<CatalogPage />);
    const label = await screen.findByRole("group", { name: "Current store" });
    expect(label).toHaveTextContent("Store A/s/store-a");
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh catalog" })).toBeEnabled());
    server.identity = { ...ownerB, store: { ...ownerB.store, name: ownerA.store.name } };
    fireEvent.click(screen.getByRole("button", { name: "Refresh catalog" }));
    const expired = await screen.findByRole("heading", { name: "Your store session expired" });
    await waitFor(() => expect(expired).toHaveFocus());
    expect(screen.queryByRole("group", { name: "Current store" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect(await screen.findByRole("group", { name: "Current store" })).toHaveTextContent("Store A/s/store-b");
    expect(screen.queryByText("/s/store-a")).not.toBeInTheDocument();
    await waitFor(() => expect(server.calls("/manager/catalog")).toHaveLength(3));
    expectBinding(server.calls("/manager/catalog")[0], ownerA);
    expectBinding(server.calls("/manager/catalog")[1], ownerA);
    expectBinding(server.calls("/manager/catalog")[2], ownerB);
  });

  it("accepts the verified rename even when follow-up readiness fails, without rebinding discovery", async () => {
    let saved = false;
    const server = merchantServer((request) => {
      if (request.method === "PATCH") {
        saved = true;
        return Response.json({ ...ownerA.store, name: "Verified new name" });
      }
      if (new URL(request.url).pathname.endsWith("/merchant/store") && saved) return denied(503);
      return Response.json(readiness());
    });
    render(<StoreAccess><DisplayWorkspace /></StoreAccess>);
    await screen.findByLabelText("Store name");
    saveName("Unsaved client spelling");
    await screen.findByRole("alert");
    expect(await openWorkspace()).toHaveTextContent("Verified new name/s/store-a");
    expect(server.calls("/auth/me")).toHaveLength(1);
    server.calls("/merchant/store").forEach((request) => expectBinding(request, ownerA));
    fireEvent.click(screen.getByRole("button", { name: "Store setup & sharing" }));
    await waitFor(() => expect(server.calls("/merchant/store")).toHaveLength(4));
    expect(server.calls("/auth/me")).toHaveLength(1);
  });

  it.each(["draft", "failed", "wrong-store"])("does not relabel the store from a %s profile", async (mode) => {
    const server = merchantServer((request) => request.method === "PATCH"
      ? mode === "failed" ? denied(503) : Response.json({ ...ownerB.store, name: "Unverified replacement" })
      : Response.json(readiness()));
    render(<StoreAccess><DisplayWorkspace /></StoreAccess>);
    await screen.findByLabelText("Store name");
    fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "Draft only" } });
    if (mode !== "draft") {
      fireEvent.click(screen.getByRole("button", { name: "Save details" }));
      await waitFor(() => expect(screen.getByRole("button", { name: "Save details" })).toBeEnabled());
      expect(server.calls("/merchant/store").some((request) => request.method === "PATCH")).toBe(true);
    }
    expect(await openWorkspace()).toHaveTextContent("Store A/s/store-a");
  });

  it("updates from a verified focus read and fences its late completion after recovery", async () => {
    const pending = deferred<Response>();
    let hold = false;
    let profile = { ...ownerA.store, name: "Readiness name" };
    const server = merchantServer((request) => new URL(request.url).pathname.endsWith("/merchant/store") && hold
      ? pending.promise : Response.json(readiness(profile)));
    render(<StoreAccess><DisplayWorkspace /></StoreAccess>);
    await screen.findByLabelText("Store name");
    fireEvent.click(screen.getByRole("button", { name: "2 Preview" }));
    profile = { ...profile, name: "Fresh focus name" };
    fireEvent(window, new Event("focus"));
    await act(async () => {});
    expect(await openWorkspace()).toHaveTextContent("Fresh focus name/s/store-a");
    fireEvent.click(screen.getByRole("button", { name: "Store setup & sharing" }));
    await screen.findByLabelText("Store name");
    fireEvent.click(screen.getByRole("button", { name: "2 Preview" }));
    hold = true;
    fireEvent(window, new Event("focus"));
    await act(async () => {});
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Your store session expired" });
    hold = false;
    profile = ownerB.store;
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByLabelText("Store name");
    await act(async () => { pending.resolve(Response.json(readiness(ownerA.store))); });
    expect(await openWorkspace()).toHaveTextContent("Store B/s/store-b");
    expect(server.calls("/auth/me")).toHaveLength(2);
  });

  it("keeps full long identity text accessible without deriving it from a workspace label", async () => {
    const name = "VerifiedStore".repeat(10);
    const slug = "long-slug-".repeat(8);
    const server = merchantServer(() => Response.json({}));
    server.identity = { ...ownerA, store: { ...ownerA.store, name, slug } };
    render(<StoreAccess initialView="workspace"><p>Different workspace name</p></StoreAccess>);
    const label = await screen.findByRole("group", { name: "Current store" });
    expect(within(label).getByText(name)).toHaveAttribute("title", name);
    expect(within(label).getByText(`/s/${slug}`)).toHaveAttribute("title", `/s/${slug}`);
    expect(screen.getByRole("button", { name: "Store setup & sharing" })).toHaveAttribute("title");
    expect(screen.getByRole("button", { name: "Sign out" })).toHaveAttribute("title");
  });

  it("rejects older reads after a verified write, out-of-order reads and retired-generation callbacks", () => {
    let display!: NonNullable<ReturnType<typeof useMerchantDisplay>>;
    let active = true;
    function Observe() { display = useMerchantDisplay()!; return <MerchantStoreIdentity compact />; }
    render(<StrictMode><MerchantDisplayProvider initialStore={ownerA.store} isActive={() => active}><Observe /></MerchantDisplayProvider></StrictMode>);
    const oldRead = display.captureRead();
    act(() => display.acceptProfile({ ...ownerA.store, name: "Saved name" }));
    act(() => oldRead(ownerA.store));
    expect(screen.getByRole("group")).toHaveTextContent("Saved name");
    const earlier = display.captureRead();
    const later = display.captureRead();
    act(() => later({ ...ownerA.store, name: "Newest read" }));
    act(() => earlier(ownerA.store));
    expect(screen.getByRole("group")).toHaveTextContent("Newest read");
    const retired = display.captureRead();
    active = false;
    act(() => { retired(ownerA.store); display.acceptProfile(ownerA.store); });
    expect(screen.getByRole("group")).toHaveTextContent("Newest read");
  });

  it("does not replace B with a late accepted A profile response", async () => {
    const response = deferred<Response>();
    const server = merchantServer((request) => request.method === "PATCH" ? response.promise : Response.json(readiness(server.identity!.store)));
    render(<StoreAccess><DisplayWorkspace /></StoreAccess>);
    await screen.findByLabelText("Store name");
    saveName("Late A rename");
    await waitFor(() => expect(server.calls("/merchant/store").some((request) => request.method === "PATCH")).toBe(true));
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Your store session expired" });
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByLabelText("Store name");
    const reads = server.calls("/merchant/store").length;
    await act(async () => { response.resolve(Response.json({ ...ownerA.store, name: "Late A rename" } satisfies StoreProfile)); });
    expect(await openWorkspace()).toHaveTextContent("Store B/s/store-b");
    expect(server.calls("/merchant/store")).toHaveLength(reads);
  });
});
