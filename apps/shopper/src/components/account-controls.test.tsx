import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpenCommerceApiError, type ShopperAccount } from "@open-commerce/sdk-typescript";
import { isSessionExpired, ShopperSessionErrors } from "@/lib/session-errors";
import { AccountControls } from "./account-controls";
const request = vi.hoisted(() => vi.fn());
vi.mock("@/lib/shopper-transport", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/shopper-transport")>();
  return { ...actual, useShopperTransport: (slug?: string) => {
    const transport = { ...actual.useShopperTransport(slug), request, forAccount: () => transport };
    return transport;
  } };
});
const guest: ShopperAccount = {
  id: "guest",
  username: "guest",
  display_name: "Guest",
  is_guest: true,
  memory_enabled: true,
  created_at: "2026-09-10T12:00:00Z",
};
const member: ShopperAccount = { ...guest, is_guest: false, display_name: "Shopper" };

function pendingRequest() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<unknown>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  request.mockReturnValueOnce(promise);
  return { resolve, reject };
}

beforeEach(() => request.mockReset());

describe("account session errors", () => {
  it.each([
    "Remember shopping preferences", "View active sessions", "Sign out everywhere", "Confirm deletion",
  ])("propagates protected %s expiry without a local error or follow-up", async (name) => {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    const onAccount = vi.fn();
    const onDeleted = vi.fn();
    request.mockRejectedValueOnce(failure);
    render(<ShopperSessionErrors.Provider value={handle}>
      <AccountControls account={member} onAccount={onAccount} onDeleted={onDeleted} onClose={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    if (name === "Confirm deletion") fireEvent.click(screen.getByText("Delete shopping data"));
    fireEvent.click(screen.getByRole(name === "Remember shopping preferences" ? "checkbox" : "button", { name }));
    await waitFor(() => expect(handle).toHaveBeenCalledExactlyOnceWith(failure));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onAccount).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("propagates an injected memory action's expiry", async () => {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    const onMemoryChange = vi.fn().mockRejectedValue(failure);
    render(<ShopperSessionErrors.Provider value={handle}>
      <AccountControls account={member} onAccount={vi.fn()} onDeleted={vi.fn()} onClose={vi.fn()} onMemoryChange={onMemoryChange} />
    </ShopperSessionErrors.Provider>);
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(handle).toHaveBeenCalledExactlyOnceWith(failure));
    expect(onMemoryChange).toHaveBeenCalledExactlyOnceWith(false);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });

  it.each([new Error("Connection unavailable"), new OpenCommerceApiError(403, null), new OpenCommerceApiError(500, null)])(
    "preserves ordinary protected-action errors: %s", async (failure) => {
      const handle = vi.fn(isSessionExpired);
      request.mockRejectedValueOnce(failure);
      render(<ShopperSessionErrors.Provider value={handle}>
        <AccountControls account={member} onAccount={vi.fn()} onDeleted={vi.fn()} onClose={vi.fn()} />
      </ShopperSessionErrors.Provider>);
      fireEvent.click(screen.getByRole("button", { name: "View active sessions" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(failure.message);
      expect(handle).toHaveBeenCalledExactlyOnceWith(failure);
      expect(request).toHaveBeenCalledTimes(1);
    },
  );

  it("keeps sign-in credential 401 local", async () => {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    request.mockRejectedValueOnce(failure);
    request.mockResolvedValueOnce({ account: guest });
    render(<ShopperSessionErrors.Provider value={handle}>
      <AccountControls account={guest} onAccount={vi.fn()} onDeleted={vi.fn()} onClose={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent(failure.message);
    expect(handle).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("delegates recovery before sending credentials and disables it during another action", () => {
    const onRecoveryStart = vi.fn();
    const props = { account: guest, onAccount: vi.fn(), onDeleted: vi.fn(), onClose: vi.fn(), onRecoveryStart };
    const view = render(<AccountControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Recover" }));
    expect(onRecoveryStart).toHaveBeenCalledOnce();
    expect(request).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Recovery code")).not.toBeInTheDocument();
    view.rerender(<AccountControls {...props} pending />);
    expect(screen.getByRole("button", { name: "Recover" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Recover" }));
    expect(onRecoveryStart).toHaveBeenCalledOnce();
    view.rerender(<AccountControls {...props} onRecoveryStart={undefined} />);
    expect(screen.queryByRole("button", { name: "Recover" })).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });

  it("propagates guest registration expiry because signup requires the guest session", async () => {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    request.mockRejectedValueOnce(failure);
    render(<ShopperSessionErrors.Provider value={handle}>
      <AccountControls account={guest} onAccount={vi.fn()} onDeleted={vi.fn()} onClose={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    await waitFor(() => expect(handle).toHaveBeenCalledExactlyOnceWith(failure));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("propagates authenticated cart-merge expiry only after the explicit choice", async () => {
    const failure = new OpenCommerceApiError(401, null);
    const handle = vi.fn(isSessionExpired);
    const onAccount = vi.fn();
    request.mockResolvedValueOnce({ account: guest, merge_token: "synthetic-grant", guest_cart_items: 1, account_cart_items: 1 });
    request.mockRejectedValueOnce(failure);
    request.mockRejectedValueOnce(failure);
    render(<ShopperSessionErrors.Provider value={handle}>
      <AccountControls account={guest} onAccount={onAccount} onDeleted={vi.fn()} onClose={vi.fn()} />
    </ShopperSessionErrors.Provider>);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    const choice = await screen.findByRole("button", { name: "Keep account cart (1 product)" });
    expect(request).toHaveBeenCalledTimes(1);
    fireEvent.click(choice);
    await waitFor(() => expect(handle).toHaveBeenCalledExactlyOnceWith(failure));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onAccount).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledTimes(3);
    expect(request).toHaveBeenLastCalledWith("/v1/shopper/me");
  });

  it.each(["replace provider", "unmount"])("ignores an old protected failure after %s", async (boundary) => {
    const oldHandle = vi.fn(isSessionExpired);
    const nextHandle = vi.fn(isSessionExpired);
    const props = { account: member, onAccount: vi.fn(), onDeleted: vi.fn(), onClose: vi.fn() };
    const pending = pendingRequest();
    const view = render(<ShopperSessionErrors.Provider value={oldHandle}><AccountControls {...props} /></ShopperSessionErrors.Provider>);
    fireEvent.click(screen.getByRole("checkbox"));
    if (boundary === "unmount") view.unmount();
    else view.rerender(<ShopperSessionErrors.Provider value={nextHandle}><AccountControls {...props} /></ShopperSessionErrors.Provider>);
    await act(async () => pending.reject(new OpenCommerceApiError(401, null)));
    expect(oldHandle).not.toHaveBeenCalled();
    expect(nextHandle).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
  });

  it.each(["Remember shopping preferences", "Confirm deletion"])("settles %s through the original parent after drawer close", async (name) => {
    const props = { account: member, onAccount: vi.fn(), onDeleted: vi.fn(), onClose: vi.fn(), onActionEnd: vi.fn() };
    const pending = pendingRequest();
    const view = render(<ShopperSessionErrors.Provider value={isSessionExpired}><AccountControls {...props} /></ShopperSessionErrors.Provider>);
    if (name === "Confirm deletion") fireEvent.click(screen.getByText("Delete shopping data"));
    fireEvent.click(screen.getByRole(name === "Remember shopping preferences" ? "checkbox" : "button", { name }));
    view.unmount();
    await act(async () => pending.resolve({ account: member }));
    expect(props.onAccount).toHaveBeenCalledTimes(name === "Remember shopping preferences" ? 1 : 0);
    expect(props.onDeleted).toHaveBeenCalledTimes(name === "Confirm deletion" ? 1 : 0);
    expect(props.onActionEnd).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledTimes(1);
  });
});

describe("guest continuity controls", () => {
  it("explains temporary memory and waits for committed settings", async () => {
    const onAccount = vi.fn();
    request.mockResolvedValue({ account: { ...guest, memory_enabled: false } });
    render(
      <AccountControls
        account={guest}
        onAccount={onAccount}
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    expect(
      screen.getByText("Temporary for this visit, up to 24 hours."),
    ).toBeVisible();
    expect(screen.getByRole("checkbox", { name: "Remember shopping preferences" }))
      .toHaveAccessibleDescription("Temporary for this visit, up to 24 hours.");
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    await waitFor(() =>
      expect(onAccount).toHaveBeenCalledWith({
        account: { ...guest, memory_enabled: false },
      }),
    );
    expect(request).toHaveBeenCalledWith("/v1/shopper/preferences", "PATCH", {
      enabled: false,
    });
  });
  it("asks which cart to retain instead of combining quantities", async () => {
    const onAccount = vi.fn();
    request.mockResolvedValueOnce({
      account: guest,
      merge_token: "synthetic-grant",
      guest_cart_items: 2,
      account_cart_items: 1,
      guest_cart_lines: [{ title: "Travel mug", variant_title: "Large", quantity: 2 }],
      account_cart_lines: [{ title: "Cotton throw", variant_title: "Blue", quantity: 1 }],
    });
    render(
      <AccountControls
        account={guest}
        onAccount={onAccount}
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Sign in" }),
    );
    expect(screen.getByText(/Signing in saves this visit's conversations/)).toBeVisible();
    expect(screen.getByText(/activity logs and personal monitoring rules are temporary/)).toBeVisible();
    expect(request).not.toHaveBeenCalledWith("/v1/shopper/auth/login", expect.anything(), expect.anything());
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "existing" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "synthetic-password" },
    });
    fireEvent.submit(screen.getByLabelText("Password").closest("form")!);
    expect(await screen.findByText("Which cart should we keep?")).toBeVisible();
    expect(screen.getByText(/will be discarded when you choose a cart/)).toBeVisible();
    expect(onAccount).not.toHaveBeenCalled();
    expect(screen.getByText(/Travel mug \(Large\)/)).toBeVisible();
    expect(screen.getByText(/Cotton throw \(Blue\)/)).toBeVisible();
    expect(screen.getByText(/cannot be undone/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Keep account cart (1 product)" })).toBeVisible();
    const guestChoice = screen.getByRole("button", { name: "Keep this visit's cart (2 products)" });
    const accountChoice = screen.getByRole("button", { name: "Keep account cart (1 product)" });
    expect(guestChoice).toHaveClass("account-command");
    expect(accountChoice.className).toBe(guestChoice.className);
    guestChoice.focus();
    expect(guestChoice).toHaveFocus();
    expect(onAccount).not.toHaveBeenCalled();
    let rejectMerge!: (reason: Error) => void;
    request.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectMerge = reject; }));
    fireEvent.click(screen.getByRole("button", { name: "Keep this visit's cart (2 products)" }));
    expect(screen.getByRole("status")).toHaveTextContent("Signing in and keeping your chosen cart");
    expect(screen.getByRole("button", { name: "Keep this visit's cart (2 products)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Keep account cart (1 product)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Back to sign in" })).toBeDisabled();
    expect(onAccount).not.toHaveBeenCalled();
    await act(async () => rejectMerge(new Error("Connection unavailable. Please try again.")));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Connection unavailable");
    expect(screen.getByRole("button", { name: "Keep this visit's cart (2 products)" })).toBeEnabled();
    request.mockResolvedValueOnce({
      account: { ...guest, id: "existing", is_guest: false },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Keep this visit's cart (2 products)" }),
    );
    await waitFor(() => expect(onAccount).toHaveBeenCalled());
    expect(request).toHaveBeenLastCalledWith("/v1/shopper/auth/merge", "POST", {
      token: "synthetic-grant",
      cart_choice: "keep_guest",
    });
  });
});

describe("account panel commands", () => {
  it("moves focus into the drawer and returns it to the opener on close", () => {
    render(<button>Open account</button>);
    const opener = screen.getByRole("button", { name: "Open account" });
    opener.focus();
    const drawer = render(<AccountControls account={member} onAccount={vi.fn()} onClose={vi.fn()} onDeleted={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Close account" })).toHaveFocus();
    drawer.unmount();
    expect(opener).toHaveFocus();
    expect(request).not.toHaveBeenCalled();
  });

  it("dismisses with Escape from a form control without submitting or changing data", () => {
    const onClose = vi.fn();
    const outerKeyDown = vi.fn();
    render(<div onKeyDown={outerKeyDown}>
      <AccountControls account={guest} onAccount={vi.fn()} onClose={onClose} onDeleted={vi.fn()} />
    </div>);
    const username = screen.getByLabelText("Username");
    username.focus();
    fireEvent.keyDown(username, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    expect(outerKeyDown).not.toHaveBeenCalled();
    expect(request).not.toHaveBeenCalled();
  });

  it("keeps the memory control focusable and preserves the committed setting on failure", async () => {
    const onAccount = vi.fn();
    const props = { account: member, onAccount, onClose: vi.fn(), onDeleted: vi.fn() };
    const { rerender } = render(<AccountControls {...props} />);
    const checkbox = screen.getByRole("checkbox", { name: "Remember shopping preferences" });
    expect(checkbox.closest("label")).toHaveClass("account-memory-toggle");
    expect(checkbox).toHaveAccessibleDescription(
      "Off disables both saving and recall. Existing memories stay until you delete them.",
    );
    checkbox.focus();
    expect(checkbox).toHaveFocus();
    expect(request).not.toHaveBeenCalled();

    const pending = pendingRequest();
    fireEvent.click(checkbox);
    expect(checkbox).toBeDisabled();
    expect(checkbox).toBeChecked();
    expect(onAccount).not.toHaveBeenCalled();
    await act(async () => pending.reject(new Error("Preferences could not be saved.")));
    expect(screen.getByRole("alert")).toHaveTextContent("Preferences could not be saved.");
    expect(checkbox).toBeEnabled();
    expect(checkbox).toBeChecked();
    expect(onAccount).not.toHaveBeenCalled();

    const retry = pendingRequest();
    fireEvent.click(checkbox);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    const result = { account: { ...member, memory_enabled: false } };
    await act(async () => retry.resolve(result));
    expect(onAccount).toHaveBeenCalledExactlyOnceWith(result);
    expect(request).toHaveBeenCalledTimes(2);
    expect(request).toHaveBeenLastCalledWith("/v1/shopper/preferences", "PATCH", { enabled: false });
    rerender(<AccountControls {...props} account={result.account} />);
    expect(checkbox).not.toBeChecked();
  });

  it.each([
    ["register", "Create account", "Save my progress"],
    ["login", "Sign in", "Sign in"],
  ] as const)("styles only the %s command and preserves its pending submission", async (mode, tab, name) => {
    const onAccount = vi.fn();
    const onClose = vi.fn();
    render(<AccountControls account={guest} onAccount={onAccount} onClose={onClose} onDeleted={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: tab }));
    const form = screen.getByLabelText("Username").closest("form")!;
    const command = form.querySelector<HTMLButtonElement>("button.account-command")!;
    expect(command).toHaveAccessibleName(name);
    expect(command.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("button", { name: "Close account" })).not.toHaveClass("account-command");
    for (const authTab of form.querySelectorAll(".auth-tabs button")) {
      expect(authTab).not.toHaveClass("account-command");
      expect(authTab).toHaveAttribute("type", "button");
    }
    command.focus();
    expect(command).toHaveFocus();
    expect(request).not.toHaveBeenCalled();
    if (mode === "register") {
      fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Shopper" } });
    }
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "shopper" } });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "synthetic-password" },
    });
    const pending = pendingRequest();
    fireEvent.submit(form);
    expect(command).toBeDisabled();
    expect(command).toHaveAccessibleName("Saving...");
    expect(onAccount).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledExactlyOnceWith(`/v1/shopper/auth/${mode}`, "POST", {
      username: "shopper",
      password: "synthetic-password",
      ...(mode === "register" ? { display_name: "Shopper" } : {}),
    });
    const result = { account: member, ...(mode !== "login" ? { recovery_code: "synthetic-new-code" } : {}) };
    await act(async () => pending.resolve(result));
    expect(command).toBeEnabled();
    expect(onAccount).toHaveBeenCalledExactlyOnceWith(result);
    if (mode !== "login") {
      const acknowledge = screen.getByRole("button", { name: "I have stored it" });
      expect(acknowledge).toHaveClass("account-command");
      expect(acknowledge.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
      acknowledge.focus();
      expect(acknowledge).toHaveFocus();
      fireEvent.click(acknowledge);
      expect(screen.queryByText("synthetic-new-code")).not.toBeInTheDocument();
      expect(request).toHaveBeenCalledTimes(1);
    }
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it.each([
    ["View active sessions", ["/v1/shopper/auth/sessions"]],
    ["Sign out everywhere", ["/v1/shopper/auth/sessions", "DELETE"]],
  ] as const)("keeps %s pending and exposes failure without changing the account", async (name, args) => {
    const onAccount = vi.fn();
    const onDeleted = vi.fn();
    render(<AccountControls account={member} onAccount={onAccount} onClose={vi.fn()} onDeleted={onDeleted} />);
    const command = screen.getByRole("button", { name });
    expect(command).toHaveClass("account-command");
    expect(command.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    command.focus();
    expect(command).toHaveFocus();
    expect(request).not.toHaveBeenCalled();
    const pending = pendingRequest();
    fireEvent.click(command);
    expect(screen.getByRole("button", { name: "View active sessions" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sign out everywhere" })).toBeDisabled();
    expect(request).toHaveBeenCalledExactlyOnceWith(...args);
    await act(async () => pending.reject(new Error("Session request unavailable.")));
    expect(screen.getByRole("alert")).toHaveTextContent("Session request unavailable.");
    expect(command).toBeEnabled();
    expect(onAccount).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("keeps deletion a separate confirmation and leaves failed deletions retryable", async () => {
    const onDeleted = vi.fn();
    render(<AccountControls account={member} onAccount={vi.fn()} onClose={vi.fn()} onDeleted={onDeleted} />);
    const disclose = screen.getByRole("button", { name: "Delete shopping data" });
    expect(disclose).toHaveClass("account-command");
    expect(disclose.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(disclose).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(disclose);
    expect(disclose).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Demo checkout audit records are retained/)).toBeVisible();
    fireEvent.click(disclose);
    expect(screen.queryByRole("button", { name: "Confirm deletion" })).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
    fireEvent.click(disclose);
    const confirm = screen.getByRole("button", { name: "Confirm deletion" });
    expect(confirm).toHaveClass("account-command");
    expect(confirm.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    confirm.focus();
    expect(confirm).toHaveFocus();
    expect(request).not.toHaveBeenCalled();
    const pending = pendingRequest();
    fireEvent.click(confirm);
    expect(confirm).toBeDisabled();
    expect(disclose).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Deleting shopping data...");
    fireEvent.click(disclose);
    expect(disclose).toHaveAttribute("aria-expanded", "true");
    expect(onDeleted).not.toHaveBeenCalled();
    fireEvent.click(confirm);
    expect(request).toHaveBeenCalledExactlyOnceWith("/v1/shopper/shopping-data", "DELETE");
    await act(async () => pending.reject(new Error("Deletion unavailable.")));
    expect(screen.getByRole("alert")).toHaveTextContent("Deletion unavailable.");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(disclose).toBeEnabled();
    expect(confirm).toBeEnabled();
    expect(onDeleted).not.toHaveBeenCalled();
    const retry = pendingRequest();
    fireEvent.click(confirm);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => retry.resolve(undefined));
    expect(request).toHaveBeenCalledTimes(2);
    expect(onDeleted).toHaveBeenCalledOnce();
    expect(disclose).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Confirm deletion" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Shopping data deleted. Demo checkout audit records are retained.");
    fireEvent.click(disclose);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(2);
  });
});
