import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionRecovery, SessionRecoveryError, type SessionRecoveryProps } from "./session-recovery";

afterEach(cleanup);

function callbacks() {
  return {
    onSignIn: vi.fn<SessionRecoveryProps["onSignIn"]>().mockResolvedValue(undefined),
    onCheckSession: vi.fn<SessionRecoveryProps["onCheckSession"]>().mockResolvedValue(undefined),
    onStartGuest: vi.fn<NonNullable<SessionRecoveryProps["onStartGuest"]>>().mockResolvedValue(undefined),
  };
}

function deferred() {
  let resolve!: () => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<void>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function fillCredentials() {
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "synthetic-shopper" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-password" } });
}

describe("SessionRecovery", () => {
  it.each([true, false])("requested recovery never falls through to sign-in (available=%s)", async (available) => {
    const handlers = callbacks();
    const onRecover = vi.fn().mockResolvedValue(undefined);
    render(<SessionRecovery guest reason="requested" {...handlers} onRecover={available ? onRecover : undefined} />);
    expect(screen.getByRole("heading", { name: "Recover your shopping account" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Back to sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start a new guest visit" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "synthetic-shopper" } });
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "synthetic-code" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "synthetic-password" } });
    await act(async () => fireEvent.submit(screen.getByRole("form", { name: "Recover account" })));
    expect(onRecover).toHaveBeenCalledTimes(available ? 1 : 0);
    for (const callback of Object.values(handlers)) expect(callback).not.toHaveBeenCalled();
  });

  it("offers existing account recovery with constrained fields and serializes duplicate submissions", async () => {
    const handlers = callbacks();
    const pending = deferred();
    const onRecover = vi.fn().mockReturnValue(pending.promise);
    render(<SessionRecovery guest={false} {...handlers} onRecover={onRecover} />);
    fireEvent.click(screen.getByRole("button", { name: "Use a recovery code" }));
    const password = screen.getByLabelText("New password");
    expect(password).toHaveAttribute("minlength", "10");
    expect(password).toHaveAttribute("maxlength", "128");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    expect(password).toHaveAccessibleDescription("Use 10 to 128 characters for your new password.");
    expect(screen.getByLabelText("Recovery code")).toHaveAttribute("type", "password");
    const form = screen.getByRole("form", { name: "Recover account" });
    fireEvent.submit(form);
    expect(onRecover).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "synthetic-shopper" } });
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "synthetic-code" } });
    fireEvent.change(password, { target: { value: "synthetic-password" } });
    act(() => { fireEvent.submit(form); fireEvent.submit(form); });
    expect(onRecover).toHaveBeenCalledExactlyOnceWith({ username: "synthetic-shopper", code: "synthetic-code", password: "synthetic-password" });
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
    await act(async () => pending.resolve());
    expect(password).toHaveValue("");
    expect(screen.getByLabelText("Recovery code")).toHaveValue("");
    for (const callback of Object.values(handlers)) expect(callback).not.toHaveBeenCalled();
  });

  it("shows only verified replacement codes and focuses the receipt without auto-continuing", () => {
    const handlers = callbacks();
    const onAcknowledgeRecovery = vi.fn();
    const view = render(<SessionRecovery guest={false} {...handlers} recoveryReceipt={{ code: "synthetic-replacement", verified: false }} onAcknowledgeRecovery={onAcknowledgeRecovery} />);
    expect(screen.queryByText("synthetic-replacement")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Check your recovered session" })).toHaveFocus();
    view.rerender(<SessionRecovery guest={false} {...handlers} recoveryReceipt={{ code: "synthetic-replacement", verified: true }} onAcknowledgeRecovery={onAcknowledgeRecovery} />);
    expect(screen.getByLabelText("Replacement recovery code")).toHaveTextContent("synthetic-replacement");
    expect(screen.getByRole("heading", { name: "Save your replacement recovery code" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Check session" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(onAcknowledgeRecovery).not.toHaveBeenCalled();
  });

  it.each([new Error("guest_conflict"), { reason: "guest_conflict" }, new SessionRecoveryError("guest_conflict")])("uses only the finite local conflict type, not message matching (%s)", async (failure) => {
    const handlers = callbacks();
    handlers.onStartGuest.mockRejectedValueOnce(failure);
    render(<SessionRecovery guest {...handlers} />);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" })));
    expect(screen.getByRole("alert")).toHaveTextContent(failure instanceof SessionRecoveryError
      ? "No new visit was confirmed. Choose Check session" : "We couldn't start a new guest visit. Please try again.");
    expect(handlers.onCheckSession).not.toHaveBeenCalled();
  });

  it("focuses the expiry title on mount and exposes only public identity", () => {
    const handlers = callbacks();
    render(<StrictMode><SessionRecovery storeName="Trail & Table" guest={false} {...handlers} /></StrictMode>);

    const title = screen.getByRole("heading", { level: 1, name: "Your shopping session expired" });
    expect(title).toHaveFocus();
    expect(title).toHaveAccessibleDescription("Your session may have expired or changed in another tab. Sign in to return to your account.");
    expect(screen.getByRole("main")).toHaveAccessibleName("Your shopping session expired");
    expect(screen.getByText("GoodAgent")).toBeVisible();
    expect(screen.getByText("Trail & Table")).toBeVisible();
    expect(screen.queryByText(/register|create an account/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    for (const callback of Object.values(handlers)) expect(callback).not.toHaveBeenCalled();
  });

  it("submits the labeled sign-in fields unchanged and clears the password after success", async () => {
    const handlers = callbacks();
    render(<SessionRecovery guest={false} {...handlers} />);
    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Username")).toBeRequired();
    expect(screen.getByLabelText("Password")).toBeRequired();

    fillCredentials();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: " synthetic-password " } });
    await act(async () => fireEvent.submit(screen.getByRole("form", { name: "Sign in" })));

    expect(handlers.onSignIn).toHaveBeenCalledExactlyOnceWith({
      username: "synthetic-shopper", password: " synthetic-password ",
    });
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByLabelText("Username")).toHaveValue("synthetic-shopper");
    expect(handlers.onCheckSession).not.toHaveBeenCalled();
    expect(handlers.onStartGuest).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { level: 1 })).toBeVisible();
  });

  it("does not submit incomplete credentials", () => {
    const handlers = callbacks();
    render(<SessionRecovery guest={false} {...handlers} />);
    fireEvent.submit(screen.getByRole("form", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "synthetic-shopper" } });
    fireEvent.submit(screen.getByRole("form", { name: "Sign in" }));
    expect(handlers.onSignIn).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("retains failed sign-in fields, announces a safe error and allows an explicit retry", async () => {
    const handlers = callbacks();
    handlers.onSignIn.mockRejectedValueOnce(new Error("request included synthetic-password"));
    render(<SessionRecovery guest={false} {...handlers} />);
    fillCredentials();
    await act(async () => fireEvent.submit(screen.getByRole("form", { name: "Sign in" })));

    expect(screen.getByRole("alert")).toHaveTextContent("We couldn't sign you in. Check your details and try again.");
    expect(screen.queryByText("request included synthetic-password")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveValue("synthetic-shopper");
    expect(screen.getByLabelText("Password")).toHaveValue("synthetic-password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
    expect(handlers.onSignIn).toHaveBeenCalledOnce();

    const retry = deferred();
    handlers.onSignIn.mockReturnValueOnce(retry.promise);
    fireEvent.submit(screen.getByRole("form", { name: "Sign in" }));
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
    await act(async () => retry.resolve());
    expect(handlers.onSignIn).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it.each([
    ["onSignIn", "Sign in", "Signing in..."],
    ["onCheckSession", "Check session", "Checking session..."],
    ["onStartGuest", "Start a new guest visit", "Starting a new guest visit..."],
  ] as const)("serializes %s with every action, even before React renders busy state", async (key, label, message) => {
    const handlers = callbacks();
    const pending = deferred();
    handlers[key].mockReturnValueOnce(pending.promise);
    render(<SessionRecovery guest {...handlers} />);
    fillCredentials();
    const form = screen.getByRole("form", { name: "Sign in" });
    const buttons = screen.getAllByRole("button");
    const selected = screen.getByRole("button", { name: label });

    act(() => {
      fireEvent.click(selected);
      for (const button of buttons) fireEvent.click(button);
      fireEvent.submit(form);
      fireEvent.submit(form);
    });

    expect(handlers[key]).toHaveBeenCalledOnce();
    for (const [name, callback] of Object.entries(handlers)) {
      if (name !== key) expect(callback).not.toHaveBeenCalled();
    }
    for (const button of buttons) {
      expect(button).toBeDisabled();
      expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    }
    expect(selected).toHaveAccessibleName(label);
    expect(screen.getByLabelText("Username")).toBeDisabled();
    expect(screen.getByLabelText("Password")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(message);

    await act(async () => pending.resolve());
    for (const button of buttons) expect(button).toBeEnabled();
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it.each([
    ["onCheckSession", "Check session", "Your session could not be restored. Try again or sign in."],
    ["onStartGuest", "Start a new guest visit", "We couldn't start a new guest visit. Please try again."],
  ] as const)("keeps %s failure retryable without submitting credentials", async (key, label, message) => {
    const handlers = callbacks();
    const pending = deferred();
    handlers[key].mockReturnValueOnce(pending.promise);
    render(<SessionRecovery guest {...handlers} />);

    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(handlers[key]).toHaveBeenCalledExactlyOnceWith();
    await act(async () => pending.reject({ sensitive: "synthetic-request-detail" }));
    expect(screen.getByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByText("synthetic-request-detail")).not.toBeInTheDocument();
    for (const button of screen.getAllByRole("button")) expect(button).toBeEnabled();

    await act(async () => fireEvent.click(screen.getByRole("button", { name: label })));
    expect(handlers[key]).toHaveBeenCalledTimes(2);
    expect(handlers.onSignIn).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
  });

  it.each([true, false])("offers a new guest visit only as an explicit choice (guest=%s)", async (guest) => {
    const handlers = callbacks();
    render(<SessionRecovery guest={guest} {...handlers} />);
    expect(screen.getByText(guest ? /Your guest visit was temporary/ : /Your session may have expired/)).toBeVisible();
    const start = screen.getByRole("button", { name: "Start a new guest visit" });
    expect(start).toHaveAttribute("type", "button");
    expect(start).toHaveAccessibleDescription("A new guest visit starts fresh. Progress from the expired visit, including unsent messages, won't transfer.");
    expect(handlers.onStartGuest).not.toHaveBeenCalled();

    await act(async () => fireEvent.click(start));
    expect(handlers.onStartGuest).toHaveBeenCalledExactlyOnceWith();
    expect(handlers.onSignIn).not.toHaveBeenCalled();
    expect(handlers.onCheckSession).not.toHaveBeenCalled();
  });

  it.each([true, false])("omits the guest action and notice without its callback (guest=%s)", (guest) => {
    const { onSignIn, onCheckSession } = callbacks();
    render(<SessionRecovery guest={guest} onSignIn={onSignIn} onCheckSession={onCheckSession} />);
    expect(screen.queryByRole("button", { name: "Start a new guest visit" })).not.toBeInTheDocument();
    expect(screen.queryByText(/A new guest visit starts fresh/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("does not move focus again on ordinary parent rerenders or retain fields after unmount", () => {
    const handlers = callbacks();
    const view = render(<SessionRecovery guest={false} {...handlers} />);
    fillCredentials();
    const username = screen.getByLabelText("Username");
    username.focus();
    view.rerender(<SessionRecovery guest={false} storeName="Trail & Table" {...handlers} />);
    expect(username).toHaveFocus();

    view.unmount();
    render(<SessionRecovery guest={false} {...handlers} />);
    expect(screen.getByLabelText("Username")).toHaveValue("");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });
});
