import type {
  ManagerAgentReply,
  ManagerDataOnboarding,
  ManagerMessage,
  ManagerRuntimeStatus,
  ManagerRun,
  ManagerRunEvents,
  ManagerThread,
  ManagerThreadDetail,
  ManagerWorkspaceResponse,
  OnboardingPrompt,
} from "@open-commerce/sdk-typescript";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { ManagerWorkspace } from "@/components/manager-workspace";
import { StoreNavigationContext } from "@/components/store-navigation";
import { StoreAccess } from "@/components/store-setup";
import { deferred, denied, expectBinding, merchantServer, ownerA, ownerB } from "./merchant-test-server";

const tenantId = "00000000-0000-0000-0000-000000000001";
const onboardingId = "10000000-0000-0000-0000-000000000001";
const statusId = "10000000-0000-0000-0000-000000000006";
const searchId = "10000000-0000-0000-0000-000000000002";
const recommendationsId = "10000000-0000-0000-0000-000000000003";
const buyAgainId = "10000000-0000-0000-0000-000000000004";
const replyId = "10000000-0000-0000-0000-000000000005";
const rootId = "20000000-0000-0000-0000-000000000001";
const now = "2026-09-08T12:00:00Z";

// JSDOM has no native modal top layer. These shims cover lifecycle only, not Tab/inertness.
const dialogMethods = Object.getOwnPropertyDescriptors(HTMLDialogElement.prototype);
beforeAll(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value() { this.setAttribute("open", ""); } },
    close: { configurable: true, value() { this.removeAttribute("open"); } },
  });
});
afterAll(() => {
  for (const name of ["showModal", "close"]) {
    if (dialogMethods[name]) Object.defineProperty(HTMLDialogElement.prototype, name, dialogMethods[name]);
    else Reflect.deleteProperty(HTMLDialogElement.prototype, name);
  }
});

describe("Workspace dialog and menu keyboard lifecycle", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  function rejectable<T>() {
    let reject!: (error: Error) => void;
    const promise = new Promise<T>((_, fail) => { reject = fail; });
    return { promise, reject };
  }

  async function mount(client = fakeClient(), strict = false) {
    const workspace = <ManagerWorkspace initialMeta={null} client={client} />;
    render(strict ? <StrictMode>{workspace}</StrictMode> : workspace);
    await screen.findByText("Good to see you.");
    return client;
  }
  function activate(button: HTMLElement) { act(() => { button.focus(); }); fireEvent.click(button); }
  function cancel(dialog = screen.getByRole("dialog")) {
    return fireEvent(dialog, new Event("cancel", { bubbles: false, cancelable: true }));
  }
  async function actions() {
    activate(screen.getByRole("button", { name: "#search" }));
    await screen.findByLabelText("Message the commerce agent");
    const button = screen.getByRole("button", { name: "Agent actions" });
    button.focus();
    fireEvent.keyDown(button, { key: "ArrowDown" });
    return button;
  }

  it.each([false, true])("restores settings and chained reset focus without writing (StrictMode=%s)", async (strict) => {
    const client = await mount(fakeClient(), strict);
    const opener = screen.getByRole("button", { name: "Workspace settings" });
    activate(opener);
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Close settings" })).toHaveFocus();
    expect(cancel()).toBe(false);
    expect(opener).toHaveFocus();
    activate(opener);
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Reset workspace" })).not.toHaveFocus();
    cancel();
    expect(opener).toHaveFocus();
    expect(client.resetManagerWorkspace).not.toHaveBeenCalled();
  });

  it("navigates the menu and returns from rename and clear to the surviving trigger", async () => {
    const client = await mount();
    const trigger = await actions();
    const rename = screen.getByRole("menuitem", { name: "Rename agent" });
    const clear = screen.getByRole("menuitem", { name: "Clear agent history" });
    const archive = screen.getByRole("menuitem", { name: "Archive agent" });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(rename).toHaveFocus();
    fireEvent.keyDown(rename, { key: "ArrowDown" }); expect(clear).toHaveFocus();
    fireEvent.keyDown(clear, { key: "End" }); expect(archive).toHaveFocus();
    fireEvent.keyDown(archive, { key: "ArrowDown" }); expect(rename).toHaveFocus();
    fireEvent.keyDown(rename, { key: "ArrowUp" }); expect(archive).toHaveFocus();
    fireEvent.keyDown(archive, { key: "Home" }); expect(rename).toHaveFocus();
    fireEvent.keyDown(rename, { key: "Escape" });
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.keyDown(trigger, { key: "ArrowUp" });
    expect(screen.getByRole("menuitem", { name: "Archive agent" })).toHaveFocus();
    activate(screen.getByRole("menuitem", { name: "Rename agent" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Agent name")).toHaveFocus();
    cancel(); expect(trigger).toHaveFocus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    activate(screen.getByRole("menuitem", { name: "Clear agent history" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
    cancel(); expect(trigger).toHaveFocus();
    expect(client.updateManagerThread).not.toHaveBeenCalled();
    expect(client.clearManagerChannel).not.toHaveBeenCalled();
  });

  it("allows menu focus to leave and dismisses outside pointers without restoring over the new target", async () => {
    await mount();
    const trigger = await actions();
    const settings = screen.getByRole("button", { name: "Workspace settings" });
    act(() => { settings.focus(); });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(settings).toHaveFocus();
    activate(trigger);
    fireEvent.pointerDown(settings);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on trigger activation and on Shift+Tab leaving for the trigger", async () => {
    await mount();
    const trigger = await actions();
    activate(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const rename = screen.getByRole("menuitem", { name: "Rename agent" });
    fireEvent.keyDown(rename, { key: "Tab", shiftKey: true });
    act(() => { trigger.focus(); }); // Models the destination, not native Tab traversal.
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveFocus();
  });

  it("skips disabled Clear history while an agent is working", async () => {
    const client = fakeClient();
    const pending = deferred<ManagerAgentReply>();
    client.sendManagerMessage.mockImplementationOnce(() => pending.promise);
    await mount(client);
    activate(screen.getByRole("button", { name: "#search" }));
    const composer = await screen.findByLabelText("Message the commerce agent");
    fireEvent.change(composer, { target: { value: "Synthetic pending message" } });
    activate(screen.getByRole("button", { name: "Send" }));
    const trigger = screen.getByRole("button", { name: "Agent actions" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(screen.getByRole("menuitem", { name: "Clear agent history" })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole("menuitem", { name: "Rename agent" }), { key: "ArrowDown" });
    expect(screen.getByRole("menuitem", { name: "Archive agent" })).toHaveFocus();
    await act(async () => { pending.resolve(replyFor(searchChannel, "Synthetic pending message")); });
  });

  it("focuses the current view when archiving removes the menu trigger", async () => {
    await mount();
    await actions();
    activate(screen.getByRole("menuitem", { name: "Archive agent" }));
    expect(await screen.findByRole("heading", { name: "Good to see you." })).toHaveFocus();
  });

  it("returns create focus and keeps the implementation file input out of tab order", async () => {
    await mount();
    const opener = screen.getAllByRole("button", { name: "Create agent" })[0];
    activate(opener);
    expect(screen.getByLabelText("Agent name")).toHaveFocus();
    cancel(); expect(opener).toHaveFocus();
    const input = screen.getByLabelText("Choose dataset CSV");
    expect(input).toHaveAttribute("hidden");
    expect(input).toHaveAttribute("tabindex", "-1");
    const picker = vi.spyOn(input, "click").mockImplementation(() => {});
    activate(screen.getByRole("button", { name: "#search" }));
    await screen.findByLabelText("Message the commerce agent");
    fireEvent.click(screen.getByRole("button", { name: "Attach catalog CSV" }));
    expect(picker).toHaveBeenCalledTimes(1);
  });

  it("guards pending reset, shows failure in the dialog and never retries automatically", async () => {
    const client = fakeClient();
    const pending = rejectable<Awaited<ReturnType<typeof client.resetManagerWorkspace>>>();
    client.resetManagerWorkspace.mockImplementationOnce(() => pending.promise);
    await mount(client);
    const opener = screen.getByRole("button", { name: "Workspace settings" });
    activate(opener);
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    const confirm = screen.getByRole("button", { name: "Reset workspace" });
    activate(confirm); fireEvent.click(confirm);
    expect(client.resetManagerWorkspace).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "Reset manager workspace?" })).toHaveFocus();
    cancel();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await act(async () => { pending.reject(new Error("Synthetic reset failure")); });
    expect(within(screen.getByRole("dialog")).getByRole("alert")).toHaveTextContent("Synthetic reset failure");
    expect(client.resetManagerWorkspace).toHaveBeenCalledTimes(1);
    cancel(); expect(opener).toHaveFocus();
  });

  it("guards pending clear and restores the trigger after a failed request", async () => {
    const client = fakeClient();
    const pending = rejectable<Awaited<ReturnType<typeof client.clearManagerChannel>>>();
    client.clearManagerChannel.mockImplementationOnce(() => pending.promise);
    await mount(client);
    const trigger = await actions();
    activate(screen.getByRole("menuitem", { name: "Clear agent history" }));
    const confirm = screen.getByRole("button", { name: "Clear history" });
    activate(confirm); fireEvent.click(confirm); cancel();
    expect(client.clearManagerChannel).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await act(async () => { pending.reject(new Error("Synthetic clear failure")); });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(screen.getByText("Synthetic clear failure")).toBeVisible();
  });

  it("retains failed editor input and retries only the refresh after a committed create", async () => {
    const client = fakeClient();
    const pending = rejectable<Awaited<ReturnType<typeof client.createManagerThread>>>();
    client.createManagerThread.mockImplementationOnce(() => pending.promise);
    await mount(client);
    activate(screen.getAllByRole("button", { name: "Create agent" })[0]);
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Seasonal" } });
    fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Retain this purpose" } });
    const form = screen.getByLabelText("Agent name").closest("form")!;
    fireEvent.submit(form); fireEvent.submit(form); cancel();
    expect(client.createManagerThread).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await act(async () => { pending.reject(new Error("Synthetic create failure")); });
    expect(screen.getByLabelText("Agent name")).toHaveValue("Seasonal");
    expect(screen.getByLabelText("Purpose")).toHaveValue("Retain this purpose");
    expect(screen.getByRole("alert")).toHaveTextContent("Synthetic create failure");
    client.managerWorkspace.mockRejectedValueOnce(new Error("Synthetic refresh failure"));
    fireEvent.submit(form);
    await screen.findByRole("button", { name: "Refresh workspace" });
    expect(client.createManagerThread).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("Agent name")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Refresh workspace" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(client.createManagerThread).toHaveBeenCalledTimes(2);
  });

  it("focuses the new interview after successful reset and leaves its upload input hidden", async () => {
    await mount();
    activate(screen.getByRole("button", { name: "Workspace settings" }));
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    activate(screen.getByRole("button", { name: "Reset workspace" }));
    await screen.findByText("What should I call this commerce workspace?");
    expect(screen.getByText("Workspace setup")).toHaveFocus();
    expect(screen.getByLabelText("Choose dataset CSV")).toHaveAttribute("hidden");
  });

  it("allows a corrected new intent after an explicit validation rejection", async () => {
    const client = fakeClient();
    client.createManagerThread.mockRejectedValueOnce(new OpenCommerceApiError(422, {
      code: "INVALID_NAME", message: "Use another name", request_id: "synthetic",
    }));
    await mount(client);
    activate(screen.getAllByRole("button", { name: "Create agent" })[0]);
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Invalid" } });
    fireEvent.submit(screen.getByLabelText("Agent name").closest("form")!);
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Agent name")).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Corrected" } });
    fireEvent.submit(screen.getByLabelText("Agent name").closest("form")!);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const calls = client.createManagerThread.mock.calls as unknown as [unknown, string][];
    expect(calls).toHaveLength(2);
    expect(calls[0][1]).not.toBe(calls[1][1]);
    expect(calls[1][0]).toEqual({ title: "Corrected", description: null });
  });

  it("keeps confirmed reset refresh-only across repeated failures, cancellation and intervening work", async () => {
    const client = await mount();
    const originalThread = client.managerThread.getMockImplementation()!;
    let failures = 2;
    client.managerThread.mockImplementation(async (id) => {
      if (id === onboardingId && failures-- > 0) throw new Error("Synthetic detail read failure");
      return originalThread(id);
    });
    activate(screen.getByRole("button", { name: "Workspace settings" }));
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    activate(screen.getByRole("button", { name: "Reset workspace" }));
    await screen.findByRole("button", { name: "Refresh workspace" });
    expect(screen.getByRole("dialog")).toHaveTextContent("Workspace reset");
    expect(screen.getByRole("dialog")).toHaveTextContent("This removed manager channels");
    expect(screen.queryByRole("button", { name: /^Cancel$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reset workspace" })).not.toBeInTheDocument();
    const intervening = await client.createManagerThread({ title: "Intervening", description: null });
    const resetSnapshot = client.resetManagerWorkspace.mock.results[0].value;
    const originalOnboarding = (await resetSnapshot).workspace.channels[0].id;
    activate(screen.getByRole("button", { name: "Refresh workspace" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workspace" })).toBeEnabled());
    expect(screen.getByRole("alert")).toHaveTextContent("Synthetic detail read failure");
    expect(client.resetManagerWorkspace).toHaveBeenCalledTimes(1);
    cancel();
    activate(screen.getByRole("button", { name: "Workspace settings" }));
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    expect(screen.getByRole("button", { name: "Refresh workspace" })).toBeEnabled();
    activate(screen.getByRole("button", { name: /^Close$/ }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(client.resetManagerWorkspace).toHaveBeenCalledTimes(1);
    activate(screen.getByRole("button", { name: "Workspace settings" }));
    activate(screen.getByRole("button", { name: "Reset and clean up" }));
    expect(screen.getByRole("button", { name: "Refresh workspace" })).toBeEnabled();
    activate(screen.getByRole("button", { name: "Refresh workspace" }));
    await screen.findByText("What should I call this commerce workspace?");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Workspace setup")).toHaveFocus();
    const current = await client.managerWorkspace();
    expect(current.channels.map((item) => item.id)).toContain(intervening.thread.id);
    expect(current.channels.find((item) => item.channel_kind === "onboarding")?.id).toBe(originalOnboarding);
    expect(client.resetManagerWorkspace).toHaveBeenCalledTimes(1);
  });
});

describe("ManagerWorkspace merchant intent over the real SDK", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  function serverForWorkspace(intercept?: (request: Request) => Response | Promise<Response> | undefined) {
    const server = merchantServer((request) => {
      const intercepted = intercept?.(request);
      if (intercepted) return intercepted;
      const path = new URL(request.url).pathname;
      if (path.endsWith("/workspace/bootstrap") || path.endsWith("/workspace")) return Response.json(completedWorkspace({
        onboarding: onboarding({ workspace_profile: { workspace_name: server.identity!.store.name } }),
      }));
      if (path.endsWith("/status")) return Response.json({ generated_at: now, components: [] });
      const target = [onboardingChannel, statusChannel, searchChannel, recommendationsChannel, buyAgainChannel]
        .find((item) => path.endsWith(`/threads/${item.id}`));
      if (target) return Response.json(detail(target));
      return denied(404);
    });
    return server;
  }
  async function mountWorkspace() {
    render(<StoreAccess initialView="workspace"><ManagerWorkspace initialMeta={null} /></StoreAccess>);
    await screen.findAllByText("Store A");
    await act(async () => {});
  }
  async function confirmReset() {
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("dialog", { name: "Workspace settings" })).toHaveTextContent("Signed-in store owner");
    expect(screen.queryByText("This local demo does not use a separate manager login.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset and clean up" }));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Reset workspace" })); });
  }

  it.each([
    ["create", "network"], ["create", "json"], ["create", "shape"],
    ["rename", "network"], ["rename", "json"], ["rename", "shape"],
  ] as const)("retains exact %s intent after a committed %s response loss, including cancel/reopen", async (mode, failure) => {
    const receipts = new Map<string, { body: unknown; response: ManagerThreadDetail }>();
    let persisted = completedWorkspace();
    let attempts = 0;
    let writes = 0;
    const server = serverForWorkspace((request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/workspace") && request.method === "GET") return Response.json(persisted);
      const mutation = mode === "create"
        ? path.endsWith("/threads") && request.method === "POST"
        : path.endsWith(`/threads/${searchId}`) && request.method === "PATCH";
      if (!mutation) return;
      return (async () => {
        attempts += 1;
        const body = await request.clone().json();
        const key = request.headers.get("Idempotency-Key")!;
        let receipt = receipts.get(key);
        if (receipt) expect(body).toEqual(receipt.body);
        else {
          writes += 1;
          const thread = mode === "create"
            ? channel(crypto.randomUUID(), "seasonal", "custom", 100, { title: body.title, description: body.description })
            : { ...searchChannel, title: body.title, description: body.description };
          receipt = { body, response: detail(thread) };
          receipts.set(key, receipt);
          persisted = { ...persisted, channels: mode === "create" ? [...persisted.channels, thread]
            : persisted.channels.map((item) => item.id === searchId ? thread : item) };
        }
        if (attempts === 1) {
          if (failure === "network") throw new TypeError("Synthetic response lost");
          return failure === "json" ? new Response("{", { status: 200 }) : Response.json({});
        }
        return Response.json(receipt.response);
      })();
    });
    await mountWorkspace();
    async function openEditor() {
      if (mode === "create") fireEvent.click(screen.getAllByRole("button", { name: "Create agent" })[0]);
      else {
        fireEvent.click(screen.getByRole("button", { name: "#search" }));
        await screen.findByLabelText("Message the commerce agent");
        fireEvent.click(screen.getByRole("button", { name: "Agent actions" }));
        fireEvent.click(screen.getByRole("menuitem", { name: "Rename agent" }));
      }
    }
    await openEditor();
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "  Seasonal  " } });
    fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "  Original intent  " } });
    fireEvent.submit(screen.getByLabelText("Agent name").closest("form")!);
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry save" })).toBeEnabled());
    expect(writes).toBe(1);
    expect(attempts).toBe(1);
    expect(screen.getByLabelText("Agent name")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Edited intent" } });
    expect(screen.getByLabelText("Agent name")).toHaveValue("Seasonal");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await openEditor();
    expect(screen.getByLabelText("Agent name")).toHaveValue("Seasonal");
    expect(screen.getByLabelText("Purpose")).toHaveValue("Original intent");
    expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
    expect(attempts).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(attempts).toBe(2);
    expect(writes).toBe(1);
    expect(receipts.size).toBe(1);
    expect([...receipts.values()][0].body).toEqual({ title: "Seasonal", description: "Original intent" });
    const requests = server.requests.filter((request) => mode === "create"
      ? new URL(request.url).pathname.endsWith("/threads") && request.method === "POST"
      : new URL(request.url).pathname.endsWith(`/threads/${searchId}`) && request.method === "PATCH");
    expect(requests).toHaveLength(2);
    expect(requests[0].headers.get("Idempotency-Key")).toBe(requests[1].headers.get("Idempotency-Key"));
    requests.forEach((request) => expectBinding(request, ownerA));
    if (mode === "create") {
      await openEditor();
      expect(screen.getByLabelText("Agent name")).toBeEnabled();
      expect(screen.getByLabelText("Agent name")).toHaveValue("");
      expect(attempts).toBe(2);
    }
  });

  it.each(["network", "json", "shape"] as const)("retries an unknown reset with the same receipt after %s response loss", async (failure) => {
    const receipts = new Map<string, { workspace: ManagerWorkspaceResponse }>();
    let persisted = completedWorkspace();
    let attempts = 0;
    let writes = 0;
    const server = serverForWorkspace((request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/workspace") && request.method === "GET") return Response.json(persisted);
      if (!path.endsWith("/workspace/reset")) return;
      return (async () => {
        attempts += 1;
        expect(await request.clone().json()).toEqual({ confirmation: "RESET" });
        const key = request.headers.get("Idempotency-Key")!;
        let receipt = receipts.get(key);
        if (!receipt) {
          writes += 1;
          persisted = completedWorkspace({ channels: [onboardingChannel] });
          receipt = { workspace: persisted };
          receipts.set(key, receipt);
        }
        if (attempts === 1) {
          if (failure === "network") throw new TypeError("Synthetic reset response lost");
          return failure === "json" ? new Response("{", { status: 200 }) : Response.json({});
        }
        return Response.json(receipt);
      })();
    });
    await mountWorkspace();
    await confirmReset();
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry reset" })).toBeEnabled());
    const intervening = channel(crypto.randomUUID(), "intervening", "custom", 100);
    persisted = { ...persisted, channels: [...persisted.channels, intervening] };
    expect(attempts).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset and clean up" }));
    fireEvent.click(screen.getByRole("button", { name: "Retry reset" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(writes).toBe(1);
    expect(attempts).toBe(2);
    expect(screen.getByRole("button", { name: "#intervening" })).toBeVisible();
    expect(persisted.channels[0].id).toBe(onboardingId);
    const requests = server.calls("/workspace/reset");
    expect(requests[0].headers.get("Idempotency-Key")).toBe(requests[1].headers.get("Idempotency-Key"));
    requests.forEach((request) => expectBinding(request, ownerA));
  });

  it("shows verified store identity separately from the workspace label and in cleanup dialogs", async () => {
    const server = serverForWorkspace((request) => {
      if (new URL(request.url).pathname.endsWith("/workspace/bootstrap")) return Response.json(completedWorkspace());
    });
    await mountWorkspace();
    await screen.findAllByText("Northstar Goods");
    const identity = screen.getByRole("group", { name: "Current store" });
    expect(identity).toHaveTextContent("Store A");
    expect(identity).toHaveTextContent("/s/store-a");
    expect(identity).not.toHaveTextContent("Northstar Goods");
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(within(screen.getByRole("dialog")).getByRole("group", { name: "Store target" }))
      .toHaveTextContent("Store A/s/store-a");
    fireEvent.click(screen.getByRole("button", { name: "Reset and clean up" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Store workspace cleanup");
    expect(within(screen.getByRole("dialog")).getByRole("group", { name: "Store target" }))
      .toHaveTextContent("Store A/s/store-a");
    expect(screen.queryByText("Local demo cleanup")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "#search" }));
    await screen.findByLabelText("Message the commerce agent");
    fireEvent.click(screen.getByRole("button", { name: "Agent actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Clear agent history" }));
    expect(within(screen.getByRole("dialog")).getByRole("group", { name: "Store target" }))
      .toHaveTextContent("Store A/s/store-a");
    expect(server.calls("/workspace/bootstrap")).toHaveLength(1);
    expectBinding(server.calls("/workspace/bootstrap")[0], ownerA);
  });

  it.each(["reset", "commerce", "agent"] as const)("rejects stale A %s before B work and never replays it on recovery", async (operation) => {
    const server = serverForWorkspace();
    await mountWorkspace();
    if (operation === "agent") {
      fireEvent.click(screen.getByRole("button", { name: "#search" }));
      fireEvent.change(await screen.findByLabelText("Message the commerce agent"), { target: { value: "A original command" } });
    }
    server.identity = ownerB;
    if (operation === "reset") await confirmReset();
    else await act(async () => { fireEvent.click(screen.getByRole("button", { name: operation === "commerce" ? "Open commerce operations" : "Send" })); });
    const heading = await screen.findByRole("heading", { name: "Your store session expired" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.queryAllByText("Store A")).toHaveLength(0);
    const suffix = operation === "reset" ? "/workspace/reset" : operation === "commerce" ? "/commerce/overview" : "/runs";
    const request = server.calls(suffix)[0];
    expectBinding(request, ownerA);
    if (operation !== "commerce") {
      expect(request.headers.get("Idempotency-Key")).toBeTruthy();
      expect(await request.json()).toEqual(operation === "reset" ? { confirmation: "RESET" } : { content: "A original command" });
    }
    const count = server.requests.length;
    vi.useFakeTimers();
    await act(async () => { await vi.advanceTimersByTimeAsync(600000); });
    expect(server.requests).toHaveLength(count);
    vi.useRealTimers();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect((await screen.findAllByText("Store B"))[0]).toBeVisible();
    await act(async () => {});
    expectBinding(server.calls("/workspace/bootstrap").at(-1)!, ownerB);
    expect(server.calls(suffix)).toHaveLength(1);
    expect(server.calls("/workspace/bootstrap")).toHaveLength(2);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("A original command")).not.toBeInTheDocument();
  });

  it("fences a late reset body before follow-up reads or local storage cleanup", async () => {
    const pendingStatus = deferred<Response>();
    const pendingBody = deferred<string>();
    const resetResponse = Response.json({});
    const parse = vi.spyOn(resetResponse, "text").mockImplementation(() => pendingBody.promise);
    let holdStatus = true;
    const server = serverForWorkspace((request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/status") && holdStatus) return pendingStatus.promise;
      if (path.endsWith("/workspace/reset")) return resetResponse;
    });
    await mountWorkspace();
    await confirmReset();
    await waitFor(() => expect(parse).toHaveBeenCalled());
    server.identity = ownerB;
    holdStatus = false;
    await act(async () => { pendingStatus.resolve(denied()); });
    await screen.findByRole("heading", { name: "Your store session expired" });
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findAllByText("Store B");
    await act(async () => {});
    const count = server.requests.length;
    const removed = vi.spyOn(Storage.prototype, "removeItem");
    await act(async () => { pendingBody.resolve(JSON.stringify({ workspace: completedWorkspace() })); });
    expect(removed).not.toHaveBeenCalled();
    expect(server.requests).toHaveLength(count);
    expect(screen.getAllByText("Store B")[0]).toBeVisible();
    expect(server.calls("/workspace/reset")).toHaveLength(1);
  });

  it.each(["create", "reset-refresh"] as const)("ignores late %s completion after owner retirement", async (operation) => {
    const pendingStatus = deferred<Response>();
    const pendingWork = deferred<Response>();
    let holdStatus = true;
    let resetStarted = false;
    let resetReads = 0;
    const server = serverForWorkspace((request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/status") && holdStatus) return pendingStatus.promise;
      if (operation === "create" && path.endsWith("/threads") && request.method === "POST") {
        return pendingWork.promise;
      }
      if (operation === "reset-refresh") {
        if (path.endsWith("/workspace/reset")) {
          resetStarted = true;
          return Response.json({ workspace: completedWorkspace() });
        }
        if (resetStarted && path.endsWith(`/threads/${onboardingId}`)) {
          resetReads += 1;
          return pendingWork.promise;
        }
      }
    });
    await mountWorkspace();
    if (operation === "create") {
      fireEvent.click(screen.getAllByRole("button", { name: "Create agent" })[0]);
      fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "A pending intent" } });
      fireEvent.submit(screen.getByLabelText("Agent name").closest("form")!);
      await waitFor(() => expect(server.calls("/threads")).toHaveLength(1));
    } else {
      await confirmReset();
      await waitFor(() => expect(resetReads).toBe(1));
    }
    server.identity = ownerB;
    holdStatus = false;
    resetStarted = false;
    await act(async () => { pendingStatus.resolve(denied()); });
    const recovery = await screen.findByRole("heading", { name: "Your store session expired" });
    expect(recovery).toHaveFocus();
    const requestsBeforeLateResponse = server.requests.length;
    const storage = vi.spyOn(Storage.prototype, "removeItem");
    await act(async () => { pendingWork.resolve(Response.json(detail(
      operation === "create" ? channel(crypto.randomUUID(), "old-a", "custom", 100) : onboardingChannel,
    ))); });
    expect(server.requests).toHaveLength(requestsBeforeLateResponse);
    expect(storage).not.toHaveBeenCalled();
    expect(recovery).toHaveFocus();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findAllByText("Store B");
    await act(async () => {});
    fireEvent.click(screen.getAllByRole("button", { name: "Create agent" })[0]);
    expect(screen.getByLabelText("Agent name")).toHaveValue("");
    expect(screen.getByLabelText("Agent name")).toBeEnabled();
    expect(server.calls(operation === "create" ? "/threads" : "/workspace/reset")).toHaveLength(1);
  });

  it("stops an abandoned bootstrap before fetching old agent threads", async () => {
    const pending = deferred<Response>();
    let hold = true;
    const server = serverForWorkspace((request) => {
      if (new URL(request.url).pathname.endsWith("/workspace/bootstrap") && hold) return pending.promise;
    });
    render(<StoreAccess initialView="workspace"><ManagerWorkspace initialMeta={null} /></StoreAccess>);
    await waitFor(() => expect(server.calls("/workspace/bootstrap")).toHaveLength(1));
    server.identity = ownerB;
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Your store session expired" });
    hold = false;
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findAllByText("Store B");
    await act(async () => {});
    const count = server.requests.length;
    await act(async () => { pending.resolve(Response.json(completedWorkspace())); });
    expect(server.requests).toHaveLength(count);
    expect(screen.queryByText("Northstar Goods")).not.toBeInTheDocument();
    const threadReads = server.requests.filter((request) => new URL(request.url).pathname.includes("/threads/"));
    expect(threadReads.length).toBeGreaterThan(0);
    threadReads.forEach((request) => expectBinding(request, ownerB));
  });
});

function prompt(overrides: Partial<OnboardingPrompt> = {}): OnboardingPrompt {
  return {
    field: "workspace_name",
    section: "Your business",
    question: "What should I call this commerce workspace?",
    intro: "First, give this workspace a useful identity.",
    input_kind: "text",
    choices: [],
    required: true,
    ordinal: 1,
    total: 8,
    ...overrides,
  };
}

function onboarding(
  overrides: Partial<ManagerDataOnboarding> = {},
): ManagerDataOnboarding {
  return {
    tenant_id: tenantId,
    catalog: null,
    engagement: null,
    engagement_decision: "pending",
    cadence: null,
    incremental_mode: null,
    watermark_column: null,
    timezone: "UTC",
    status: "needs_catalog",
    scheduled_loads_active: false,
    workspace_status: "completed",
    current_prompt: null,
    completed_fields: [],
    workspace_profile: {
      workspace_name: "Northstar Goods",
      business_summary: "Outdoor goods for weekend explorers",
      manager_role: "merchandising",
      primary_goal: "Improve product discovery",
      starter_agents: ["status", "search", "recommendations"],
      priority_surfaces: ["search", "pdp_recommendations"],
      search_baseline: "keyword",
      recommendation_surfaces: ["pdp"],
      buy_again_strategy: "later",
      success_metrics: ["conversion", "search_success"],
      guardrails: ["relevance", "availability"],
      operating_mode: "draft_only",
      response_style: "balanced",
    },
    catalog_decision: "defer",
    limited_mode: true,
    status_refresh_minutes: 5,
    completed_at: now,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function channel(
  id: string,
  slug: string,
  kind: ManagerThread["channel_kind"],
  position: number,
  overrides: Partial<ManagerThread> = {},
): ManagerThread {
  return {
    id,
    tenant_id: tenantId,
    title: slug.replaceAll("-", " "),
    status: "active",
    thread_type: "channel",
    channel_kind: kind,
    slug,
    description: `${slug} strategy`,
    position,
    parent_thread_id: null,
    root_message_id: null,
    working_memory: {
      current_topic: null,
      open_question: null,
      objective: null,
      recent_decisions: [],
    },
    user_turn_count: 0,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function message(
  id: string,
  threadId: string,
  content: string,
  role: ManagerMessage["role"] = "assistant",
): ManagerMessage {
  return {
    id,
    tenant_id: tenantId,
    thread_id: threadId,
    role,
    content,
    steps: [],
    reply_count: 0,
    created_at: now,
  };
}

const onboardingChannel = channel(onboardingId, "onboarding", "onboarding", 0);
const statusChannel = channel(statusId, "status", "status", 5);
const searchChannel = channel(searchId, "search", "search", 10);
const recommendationsChannel = channel(
  recommendationsId,
  "recommendations",
  "recommendations",
  20,
);
const buyAgainChannel = channel(buyAgainId, "buy-it-again", "buy_again", 30);

function detail(
  thread: ManagerThread,
  content = `Welcome to #${thread.slug}`,
): ManagerThreadDetail {
  return {
    thread,
    messages: [message(rootId, thread.id, content)],
    memories: [],
    capabilities: {
      semantic_backend: "all-MiniLM-L6-v2 (pinned local)",
      learned_semantics: true,
      conversation_provider: "deterministic",
      conversation_model: "bounded-rule-interpreter",
      model_backed: false,
      supported_surfaces: ["search", "recommendations", "both"],
      supported_ranking_signals: ["relevance", "popularity", "quality"],
      complex_tools_simulated: true,
    },
    onboarding: onboarding(),
    root_message: null,
  };
}

function completedWorkspace(
  overrides: Partial<ManagerWorkspaceResponse> = {},
): ManagerWorkspaceResponse {
  return {
    channels: [
      onboardingChannel,
      statusChannel,
      searchChannel,
      recommendationsChannel,
      buyAgainChannel,
    ],
    onboarding: onboarding(),
    capabilities: detail(searchChannel).capabilities,
    catalog_index: {
      status: "not_configured",
      product_count: 0,
      indexed_product_count: 0,
    },
    ...overrides,
  };
}

function replyFor(thread: ManagerThread, content: string): ManagerAgentReply {
  return {
    thread: { ...thread, user_turn_count: (thread.user_turn_count ?? 0) + 1 },
    user_message: message(crypto.randomUUID(), thread.id, content, "user"),
    assistant_message: {
      ...message(
        crypto.randomUUID(),
        thread.id,
        "I prepared a reviewable discovery draft.",
      ),
      steps: [
        {
          stage: "act",
          title: "Compile discovery objective",
          detail: "Validated a typed draft without activating a model.",
          status: "simulated",
          tool: "discovery.draft_objective",
        },
      ],
    },
    memories: [],
    periodic_memory_created: null,
    capabilities: detail(thread).capabilities,
    onboarding: onboarding(),
    workspace_changed: false,
  };
}

function fakeClient(initial = completedWorkspace()) {
  let workspace = initial;
  const details: Record<string, ManagerThreadDetail> = Object.fromEntries(
    initial.channels.map((item) => [
      item.id,
      { ...detail(item), onboarding: initial.onboarding },
    ]),
  );
  const replyThread = channel(replyId, "reply", null, 0, {
    title: "Thread: Search planning",
    thread_type: "reply",
    slug: null,
    parent_thread_id: searchId,
    root_message_id: rootId,
    description: "Reply thread in #search",
  });
  const replyDetail: ManagerThreadDetail = {
    ...detail(replyThread, "Follow-up context"),
    messages: [],
    root_message:
      details[searchId]?.messages[0] ??
      message(rootId, searchId, "Search planning"),
  };
  return {
    bootstrapManagerWorkspace: vi.fn(async () => workspace),
    managerWorkspace: vi.fn(async () => workspace),
    managerCommerceOverview: vi.fn(async () => ({
      inventory: [
        {
          product_id: "pasta-kit",
          variant_id: "pasta-kit-default",
          sku: "PASTA-1",
          title: "Weeknight Pasta Kit",
          variant_title: "Default",
          image_url: null,
          observed_quantity: 12,
          reserved_quantity: 2,
          sellable_quantity: 10,
          state: "healthy" as const,
          observed_at: now,
        },
      ],
      reservations: [],
      orders: [],
      payments: [],
      inventory_writes_enabled: false as const,
      payment_mode: "local_test" as const,
      generated_at: now,
    })),
    managerStatus: vi.fn(
      async (): Promise<ManagerRuntimeStatus> => ({
        generated_at: now,
        components: [
          {
            key: "api",
            label: "API",
            state: "green",
            detail: "Status endpoint responding",
            latency_ms: 2,
          },
          {
            key: "shopper_web",
            label: "Shopper app",
            state: "yellow",
            detail: "Waiting for the shopper app",
            latency_ms: null,
          },
        ],
      }),
    ),
    managerThread: vi.fn(async (id: string) => details[id] ?? replyDetail),
    managerReplyThread: vi.fn(async () => replyDetail),
    createManagerReplyThread: vi.fn(async () => replyDetail),
    createManagerThread: vi.fn(
      async (body: { title?: string; description?: string | null }) => {
        const created = channel(
          "10000000-0000-0000-0000-000000000099",
          (body.title ?? "channel").toLowerCase().replaceAll(" ", "-"),
          "custom",
          100,
          { title: body.title ?? "channel", description: body.description },
        );
        const createdDetail = detail(created);
        details[created.id] = createdDetail;
        workspace = {
          ...workspace,
          channels: [...workspace.channels, created],
        };
        return createdDetail;
      },
    ),
    updateManagerThread: vi.fn(
      async (
        id: string,
        body: {
          title?: string | null;
          description?: string | null;
          status?: string | null;
        },
      ) => {
        const current = details[id];
        const updated = {
          ...current,
          thread: {
            ...current.thread,
            title: body.title ?? current.thread.title,
            slug: body.title
              ? body.title.toLowerCase().replaceAll(" ", "-")
              : current.thread.slug,
            description: body.description ?? current.thread.description,
            status: (body.status ?? current.thread.status) as
              | "active"
              | "archived",
          },
        };
        details[id] = updated;
        workspace = {
          ...workspace,
          channels: workspace.channels.map((item) =>
            item.id === id ? updated.thread : item,
          ),
        };
        return updated;
      },
    ),
    clearManagerChannel: vi.fn(async (id: string) => {
      const current = details[id];
      const reset: ManagerThreadDetail = {
        ...current,
        thread: {
          ...current.thread,
          user_turn_count: 0,
          working_memory: {
            current_topic: null,
            open_question: null,
            objective: null,
            recent_decisions: [],
          },
        },
        messages: [
          message(crypto.randomUUID(), id, "History cleared. Agent ready."),
        ],
        memories: current.memories.filter((item) => item.layer === "long_term"),
      };
      details[id] = reset;
      workspace = {
        ...workspace,
        channels: workspace.channels.map((item) =>
          item.id === id ? reset.thread : item,
        ),
      };
      return {
        detail: reset,
        deleted_message_count: current.messages.length,
        deleted_reply_thread_count: 1,
      };
    }),
    resetManagerWorkspace: vi.fn(async () => {
      const resetOnboarding = onboarding({
        workspace_status: "in_progress",
        current_prompt: prompt(),
        completed_at: null,
        workspace_profile: {},
        catalog_decision: "pending",
        limited_mode: false,
      });
      workspace = completedWorkspace({
        channels: [onboardingChannel],
        onboarding: resetOnboarding,
      });
      details[onboardingId] = {
        ...detail(onboardingChannel),
        onboarding: resetOnboarding,
      };
      return {
        workspace,
        deleted_channel_count: 5,
        deleted_message_count: 12,
        deleted_memory_count: 3,
      };
    }),
    sendManagerMessage: vi.fn(async (id: string, body: { content: string }) => {
      const target = id === replyId ? replyThread : details[id].thread;
      return replyFor(target, body.content);
    }),
    profileManagerDataset: vi.fn(),
    deleteManagerMemory: vi.fn(async (id: string) => ({
      memory_id: id,
      deleted: true,
    })),
  };
}

describe("ManagerWorkspace", () => {
  it("uses GoodAgent when no merchant workspace name is set", async () => {
    const workspace = completedWorkspace({
      onboarding: onboarding({ workspace_profile: {} }),
    });
    render(<ManagerWorkspace initialMeta={null} client={fakeClient(workspace)} />);
    const overview = await screen.findByRole("button", { name: "Workspace overview" });
    const header = within(overview.closest("header")!);
    expect(header.getByText("GoodAgent")).toBeVisible();
    expect(header.getByText("GA")).toBeVisible();
    expect(screen.getByRole("button", { name: "Home" })).toHaveTextContent("GA");
  });

  it.each(["Northstar Goods", "Open Commerce", "Open Commerce Shop"])(
    "preserves the merchant workspace name %s",
    async (name) => {
      const workspace = completedWorkspace({
        onboarding: onboarding({ workspace_profile: { workspace_name: name } }),
      });
      render(<ManagerWorkspace initialMeta={null} client={fakeClient(workspace)} />);
      const overview = await screen.findByRole("button", { name: "Workspace overview" });
      const header = within(overview.closest("header")!);
      expect(header.getByText(name)).toBeVisible();
      expect(header.queryByText("GoodAgent")).not.toBeInTheDocument();
    },
  );

  it("brands assistant attribution without rewriting saved message text", async () => {
    const client = fakeClient();
    const content = "Welcome to Open Commerce Agent.";
    client.managerThread.mockResolvedValue(detail(searchChannel, content));
    render(<ManagerWorkspace initialMeta={null} client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    const row = (await screen.findByText(content)).closest("article")!;
    expect(within(row).getByText("GoodAgent")).toBeVisible();
    expect(within(row).getByText(content)).toBeVisible();
  });

  it("labels the Home shortcut honestly instead of offering unimplemented workspace search", async () => {
    render(<ManagerWorkspace initialMeta={null} client={fakeClient()} />);
    const home = await screen.findByRole("button", { name: "Workspace overview" });
    expect(screen.queryByRole("button", { name: /Search workspace/ })).not.toBeInTheDocument();
    fireEvent.click(home);
    expect(screen.getByRole("button", { name: "Connect data" })).toBeVisible();
  });
  it("replaces limited mode with live indexing and clears the warning when verification finishes", async () => {
    const queued = completedWorkspace({ catalog_index: {
      status: "queued", product_count: 48, indexed_product_count: 0,
    } });
    const fake = fakeClient(queued);
    fake.managerWorkspace.mockResolvedValue(completedWorkspace({ catalog_index: {
      status: "ready", product_count: 48, indexed_product_count: 48,
    } }));
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    expect(await screen.findByText("Catalog queued for indexing")).toBeVisible();
    expect(screen.queryByText("Limited exploration mode")).not.toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeVisible();
    await waitFor(() => expect(screen.getByText("48 products ready")).toBeVisible(), { timeout: 3000 });
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText("Limited exploration mode")).not.toBeInTheDocument();
    expect(fake.managerStatus).toHaveBeenCalledTimes(1);
  });

  it("opens the legacy CSV picker from Home without a selected conversation", async () => {
    render(<ManagerWorkspace initialMeta={null} client={fakeClient()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Connect data" }));
    const picker = vi.spyOn(screen.getByLabelText("Choose dataset CSV"), "click");
    fireEvent.click(screen.getAllByRole("button", { name: "Attach CSV" })[0]);
    expect(picker).toHaveBeenCalledOnce();
    picker.mockRestore();
  });

  it("routes self-service Home and catalog controls to reviewed imports, not legacy connectors", async () => {
    const openProducts = vi.fn();
    render(<StoreNavigationContext.Provider value={{ openProducts }}>
      <ManagerWorkspace initialMeta={null} client={fakeClient()} />
    </StoreNavigationContext.Provider>);
    fireEvent.click(await screen.findByRole("button", { name: "Connect data" }));
    expect(openProducts).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: /Data readiness/ }));
    expect(screen.queryByText("Shopify")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Upload or review catalog" }));
    expect(openProducts).toHaveBeenCalledTimes(2);
    const picker = vi.spyOn(screen.getByLabelText("Choose dataset CSV"), "click");
    fireEvent.click(screen.getByRole("button", { name: "Attach CSV" }));
    expect(picker).toHaveBeenCalledOnce();
    picker.mockRestore();
    fireEvent.click(screen.getByRole("button", { name: "#search" }));
    fireEvent.click(await screen.findByRole("button", { name: "Attach catalog CSV" }));
    expect(openProducts).toHaveBeenCalledTimes(3);
  });

  it("shows actual model connection evidence in the Model panel", async () => {
    const fake = fakeClient();
    fake.managerStatus.mockResolvedValue({ generated_at: now, components: [{
      key: "manager_agent", label: "Conversation model", state: "green",
      detail: "Received an actual model response", observed_at: now,
    }] });
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    fireEvent.click(screen.getByRole("button", { name: "Open details panel" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Model" }));
    expect(await screen.findByText("Response verified")).toBeVisible();
    expect(screen.getByText("Received an actual model response")).toBeVisible();
    expect(screen.getByText("Last observed")).toBeVisible();
  });

  it("saves an asynchronous message, resumes after reload, and stops without resending", async () => {
    const fake = fakeClient();
    const run: ManagerRun = {
      id: "30000000-0000-0000-0000-000000000001",
      thread_id: searchId,
      user_message_id: "20000000-0000-0000-0000-000000000099",
      status: "running", phase: "Checking catalog readiness",
      created_at: now, updated_at: now,
    };
    let current = run;
    let saved: ManagerThreadDetail | null = null;
    const originalThread = fake.managerThread.getMockImplementation()!;
    fake.managerThread.mockImplementation(async (id: string) =>
      id === searchId && saved ? saved : originalThread(id));
    const client = {
      ...fake,
      createManagerRun: vi.fn(async () => {
        const original = await originalThread(searchId);
        saved = { ...original, active_run: run, messages: [...original.messages,
          { ...message(run.user_message_id, searchId, "Check my new store"), role: "user" as const }] };
        return run;
      }),
      managerRunEvents: vi.fn(async (): Promise<ManagerRunEvents> => ({
        run: current, items: [], next_cursor: 0,
      })),
      cancelManagerRun: vi.fn(async () => {
        current = { ...run, status: "cancelled", phase: "Stopped" };
        if (saved) saved = { ...saved, active_run: null };
        return current;
      }),
    };
    const first = render(<ManagerWorkspace initialMeta={null} client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    fireEvent.change(await screen.findByLabelText("Message the commerce agent"), {
      target: { value: "Check my new store" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText("Check my new store")).toBeVisible();
    expect(await screen.findByRole("button", { name: "Stop agent" })).toBeVisible();
    first.unmount();
    render(<ManagerWorkspace initialMeta={null} client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    expect(await screen.findByText("Check my new store")).toBeVisible();
    fireEvent.click(await screen.findByRole("button", { name: "Stop agent" }));
    await waitFor(() => expect(client.cancelManagerRun).toHaveBeenCalledWith(run.id, `stop-${run.id}`));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Stop agent" })).not.toBeInTheDocument(), { timeout: 2500 });
    expect(screen.getByText("Check my new store")).toBeVisible();
    expect(client.createManagerRun).toHaveBeenCalledTimes(1);
    expect(fake.sendManagerMessage).not.toHaveBeenCalled();
  });

  it("shows observed inventory and the local commerce safety boundary", async () => {
    const fake = fakeClient();
    render(<ManagerWorkspace initialMeta={null} client={fake} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Open commerce operations" }),
    );
    expect(await screen.findByText("Commerce operations")).toBeVisible();
    expect(screen.getByText("Weeknight Pasta Kit")).toBeVisible();
    expect(screen.getByText("10")).toBeVisible();
    expect(
      screen.getByText(/Payments are deterministic tests/),
    ).toBeVisible();
    expect(fake.managerCommerceOverview).toHaveBeenCalledOnce();
  });

  it("opens with a full-screen guided interview and advances contextual controls", async () => {
    const first = onboarding({
      workspace_status: "in_progress",
      current_prompt: prompt(),
      completed_at: null,
      limited_mode: false,
      workspace_profile: {},
    });
    const next = onboarding({
      workspace_status: "in_progress",
      current_prompt: prompt({
        field: "starter_agents",
        section: "Your agents",
        question: "Which agents should I set up first? Choose one or more.",
        input_kind: "multi_select",
        choices: [
          { value: "general", label: "General commerce", description: null },
          { value: "search", label: "Search", description: null },
        ],
        ordinal: 4,
      }),
      completed_fields: ["workspace_name", "business_summary"],
      workspace_profile: { workspace_name: "Northstar Goods" },
      completed_at: null,
      limited_mode: false,
    });
    const workspace = completedWorkspace({
      channels: [onboardingChannel],
      onboarding: first,
    });
    const fake = fakeClient(workspace);
    fake.sendManagerMessage.mockResolvedValue({
      ...replyFor(onboardingChannel, "Northstar Goods"),
      onboarding: next,
    });

    render(<ManagerWorkspace initialMeta={null} client={fake} />);

    expect(
      await screen.findByText("Set up your operator workspace"),
    ).toBeVisible();
    expect(screen.getByText("1 of 8")).toBeVisible();
    expect(within(screen.getByRole("banner")).getByText("GoodAgent")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Your onboarding answer"), {
      target: { value: "Northstar Goods" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send answer" }));

    expect(
      await screen.findByText(
        "Which agents should I set up first? Choose one or more.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /General commerce/ }),
    ).toBeEnabled();
    expect(fake.sendManagerMessage).toHaveBeenCalledWith(
      onboardingId,
      { content: "Northstar Goods" },
      expect.stringMatching(/^manager-message-/),
    );
  });

  it("supports review editing and confirms limited exploration explicitly", async () => {
    const review = onboarding({
      workspace_status: "review",
      current_prompt: prompt({
        field: "review",
        section: "Review",
        question: "Review the setup summary. Is it ready to use?",
        input_kind: "review",
        choices: [
          { value: "confirm", label: "Open workspace", description: null },
        ],
        ordinal: 8,
      }),
      completed_at: null,
    });
    const workspace = completedWorkspace({
      channels: [onboardingChannel],
      onboarding: review,
    });
    const fake = fakeClient(workspace);
    const completed = onboarding();
    fake.sendManagerMessage.mockImplementation(
      async (_id: string, body: { content: string }) => ({
        ...replyFor(onboardingChannel, body.content),
        onboarding: body.content === "confirm" ? completed : review,
        workspace_changed: body.content === "confirm",
      }),
    );
    fake.managerWorkspace.mockResolvedValue(completedWorkspace());

    render(<ManagerWorkspace initialMeta={null} client={fake} />);

    expect(await screen.findByText("Review your workspace")).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await waitFor(() =>
      expect(fake.sendManagerMessage).toHaveBeenCalledWith(
        onboardingId,
        { content: "edit:workspace_name" },
        expect.any(String),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /Open workspace/ }));
    expect(await screen.findByText("Limited exploration mode")).toBeVisible();
    expect(screen.getByText(/Catalog indexing, model building/)).toBeVisible();
  });

  it("creates agents and restores a draft after switching conversations", async () => {
    const fake = fakeClient(
      completedWorkspace({
        catalog_index: {
          status: "ready",
          product_count: 40,
          indexed_product_count: 40,
          filename: "sample-catalog.csv",
        },
      }),
    );
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    expect(await screen.findByText("Good to see you.")).toBeVisible();

    fireEvent.click(screen.getAllByRole("button", { name: "Create agent" })[0]);
    fireEvent.change(screen.getByLabelText("Agent name"), {
      target: { value: "Seasonal launch" },
    });
    fireEvent.change(screen.getByLabelText("Purpose"), {
      target: { value: "Plan spring discovery" },
    });
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Create agent",
      }),
    );
    expect(
      await screen.findByRole("button", { name: "#seasonal-launch" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Message the commerce agent"), {
      target: { value: "Keep this draft" },
    });
    fireEvent.click(screen.getByRole("button", { name: "#search" }));
    expect(await screen.findByText("Welcome to #search")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "#seasonal-launch" }));
    expect(
      await screen.findByText("Welcome to #seasonal-launch"),
    ).toBeVisible();
    expect(screen.getByLabelText("Message the commerce agent")).toHaveValue(
      "Keep this draft",
    );
  });

  it("shows dynamic services in the status channel", async () => {
    const fake = fakeClient();
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#status" }));
    fireEvent.click(await screen.findByRole("button", { name: "Toggle service details" }));
    expect(
      await screen.findByLabelText("Live service status"),
    ).toHaveTextContent("Status endpoint responding");
    expect(screen.getByLabelText("Live service status")).toHaveTextContent(
      "Waiting for the shopper app",
    );
    expect(screen.getByLabelText("Live service status")).toHaveTextContent(
      "auto-check every 5 min",
    );
    expect(fake.managerStatus).toHaveBeenCalled();
  });

  it("shows explicit settings before manager-only workspace reset", async () => {
    const fake = fakeClient();
    render(<ManagerWorkspace initialMeta={null} client={fake} />);

    fireEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(
      screen.getByRole("dialog", { name: "Workspace settings" }),
    ).toHaveTextContent(
      "This local demo does not use a separate manager login.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Reset and clean up" }));
    expect(screen.getByText("Reset manager workspace?")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reset workspace" }));

    await waitFor(() => expect(fake.resetManagerWorkspace).toHaveBeenCalled());
    expect(
      await screen.findByText("What should I call this commerce workspace?"),
    ).toBeVisible();
  });

  it("clears one agent history after confirmation and retains long-term memory", async () => {
    const fake = fakeClient();
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    expect(await screen.findByText("Welcome to #search")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Agent actions" }));
    fireEvent.click(
      screen.getByRole("menuitem", { name: "Clear agent history" }),
    );

    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Store-level preferences and onboarding answers will be kept.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear history" }));

    expect(
      await screen.findByText("History cleared. Agent ready."),
    ).toBeVisible();
    expect(fake.clearManagerChannel).toHaveBeenCalledWith(
      searchId,
      expect.stringMatching(/^manager-channel-clear-/),
    );
    expect(screen.getByText(/Long-term preferences were kept/)).toBeVisible();
  });

  it("opens a durable one-level reply and runs it independently", async () => {
    const fake = fakeClient(
      completedWorkspace({
        catalog_index: {
          status: "ready",
          product_count: 40,
          indexed_product_count: 40,
          filename: "sample-catalog.csv",
        },
      }),
    );
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    expect(await screen.findByText("Welcome to #search")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Reply to assistant message" }),
    );

    const drawer = await screen.findByText("Original message");
    expect(drawer).toBeVisible();
    fireEvent.change(screen.getByLabelText("Reply to thread"), {
      target: { value: "Use a balanced popularity signal" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));
    expect(
      await screen.findByText("I prepared a reviewable discovery draft."),
    ).toBeVisible();
    expect(fake.sendManagerMessage).toHaveBeenCalledWith(
      replyId,
      { content: "Use a balanced popularity signal" },
      expect.stringMatching(/^manager-message-/),
    );
  });

  it("shows safe activity and data through the single right drawer", async () => {
    const searchDetail = detail(searchChannel);
    searchDetail.messages[0].steps = [
      {
        stage: "observe",
        title: "Inspect catalog readiness",
        detail: "No catalog rows were sent to the model.",
        status: "completed",
        tool: "data.inspect_onboarding",
      },
    ];
    searchDetail.memories = [
      {
        id: "30000000-0000-0000-0000-000000000001",
        tenant_id: tenantId,
        thread_id: null,
        layer: "long_term",
        title: "Concise summaries",
        content: "Prefer concise summaries",
        source: "explicit_manager",
        period_start: null,
        period_end: null,
        created_at: now,
      },
    ];
    const fake = fakeClient(
      completedWorkspace({
        catalog_index: {
          status: "ready",
          product_count: 40,
          indexed_product_count: 40,
          filename: "sample-catalog.csv",
        },
      }),
    );
    fake.managerThread.mockImplementation(async (id: string) =>
      id === searchId ? searchDetail : detail(onboardingChannel),
    );
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    fireEvent.click(screen.getByRole("button", { name: "Open details panel" }));
    expect(await screen.findByRole("tabpanel")).toHaveTextContent(
      "No source provided.",
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent(
      /Search index\s*Ready/,
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent("40 / 40");
    fireEvent.click(screen.getByRole("tab", { name: "Memory" }));
    expect(screen.getByText("Concise summaries")).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(
      within(screen.getByRole("tabpanel")).getByText(
        "Inspect catalog readiness",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("Operational summaries, not hidden reasoning"),
    ).toBeVisible();
  });

  it("keeps another channel usable while an agent run is pending and restores failures", async () => {
    const fake = fakeClient();
    let rejectSearch!: (reason: Error) => void;
    const searchTurn = new Promise<ManagerAgentReply>((_resolve, reject) => {
      rejectSearch = reject;
    });
    fake.sendManagerMessage.mockImplementation(
      async (id: string, body: { content: string }) => {
        if (id === searchId) return searchTurn;
        return replyFor(recommendationsChannel, body.content);
      },
    );
    render(<ManagerWorkspace initialMeta={null} client={fake} />);
    fireEvent.click(await screen.findByRole("button", { name: "#search" }));
    fireEvent.change(
      await screen.findByLabelText("Message the commerce agent"),
      {
        target: { value: "Improve search" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText("Improve search")).toBeVisible();
    expect(screen.getByText("Sending")).toBeVisible();
    expect(await screen.findByText("Search agent is working")).toBeVisible();
    expect(
      screen.getByText(/Waiting for the agent/),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "#recommendations" }));
    fireEvent.change(
      await screen.findByLabelText("Message the commerce agent"),
      {
        target: { value: "Improve recommendations" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(
      await screen.findByText("I prepared a reviewable discovery draft."),
    ).toBeVisible();

    rejectSearch(new Error("Model temporarily unavailable"));
    fireEvent.click(screen.getByRole("button", { name: "#search" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Message the commerce agent")).toHaveValue(
        "Improve search",
      ),
    );
    expect(screen.getByText("Model temporarily unavailable")).toBeVisible();
  });
});
