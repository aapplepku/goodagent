import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceDialog, focusWorkspaceTarget } from "@/components/workspace-dialog";

const original = Object.getOwnPropertyDescriptors(HTMLDialogElement.prototype);
const showModal = vi.fn(function (this: HTMLDialogElement) { this.setAttribute("open", ""); });
const close = vi.fn(function (this: HTMLDialogElement) { this.removeAttribute("open"); });
beforeEach(() => {
  // Lifecycle only: JSDOM does not provide native inertness, focus trapping or cancel keys.
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: showModal },
    close: { configurable: true, value: close },
  });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });
afterAll(() => {
  for (const name of ["showModal", "close"]) {
    if (original[name]) Object.defineProperty(HTMLDialogElement.prototype, name, original[name]);
    else Reflect.deleteProperty(HTMLDialogElement.prototype, name);
  }
});

function content(pending = false) {
  return <section>
    <h2 id="test-dialog" data-dialog-heading tabIndex={-1}>Test dialog</h2>
    <button data-dialog-initial disabled={pending}>Safe control</button>
  </section>;
}

describe("Native workspace dialog lifecycle", () => {
  it("opens safely under StrictMode and never treats cleanup as user dismissal", () => {
    const dismiss = vi.fn();
    const view = render(<StrictMode><WorkspaceDialog labelledBy="test-dialog" onDismiss={dismiss}>
      {content()}
    </WorkspaceDialog></StrictMode>);
    expect(showModal).toHaveBeenCalledTimes(2);
    expect(close).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button")).toHaveFocus();
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
    view.unmount();
    expect(close).toHaveBeenCalledTimes(2);
    expect(dismiss).not.toHaveBeenCalled();
  });

  it("prevents native cancellation while busy and keeps focus on a safe internal heading", () => {
    const dismiss = vi.fn();
    const view = render(<WorkspaceDialog labelledBy="test-dialog" onDismiss={dismiss}>{content()}</WorkspaceDialog>);
    const dialog = screen.getByRole("dialog");
    expect(fireEvent(dialog, new Event("cancel", { cancelable: true }))).toBe(false);
    expect(dismiss).toHaveBeenCalledTimes(1);
    view.rerender(<WorkspaceDialog labelledBy="test-dialog" pending onDismiss={dismiss}>{content(true)}</WorkspaceDialog>);
    expect(screen.getByRole("heading")).toHaveFocus();
    expect(fireEvent(dialog, new Event("cancel", { cancelable: true }))).toBe(false);
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(showModal).toHaveBeenCalledTimes(1);
  });

  it("dismisses only an idle backdrop interaction begun outside the panel", () => {
    const dismiss = vi.fn();
    const view = render(<WorkspaceDialog labelledBy="test-dialog" onDismiss={dismiss}>{content()}</WorkspaceDialog>);
    const dialog = screen.getByRole("dialog");
    fireEvent.mouseDown(screen.getByRole("button"));
    fireEvent.click(dialog);
    expect(dismiss).not.toHaveBeenCalled();
    fireEvent.mouseDown(dialog); fireEvent.click(dialog);
    expect(dismiss).toHaveBeenCalledTimes(1);
    view.rerender(<WorkspaceDialog labelledBy="test-dialog" pending onDismiss={dismiss}>{content(true)}</WorkspaceDialog>);
    fireEvent.mouseDown(dialog); fireEvent.click(dialog);
    expect(dismiss).toHaveBeenCalledTimes(1);
  });

  it("restores a usable local trigger, falling back for hidden, disabled or foreign targets", () => {
    render(<><button>Other workspace</button><main data-testid="workspace">
      <h1 data-workspace-focus tabIndex={-1}>Current view</h1>
      <button>Local trigger</button><div style={{ display: "none" }}><button>Hidden trigger</button></div>
      <button disabled>Disabled trigger</button>
    </main></>);
    const root = screen.getByTestId("workspace");
    const local = screen.getByRole("button", { name: "Local trigger" });
    focusWorkspaceTarget(root, local); expect(local).toHaveFocus();
    for (const target of [
      screen.getByText("Hidden trigger"), screen.getByText("Disabled trigger"),
      screen.getByText("Other workspace"), null,
    ]) {
      focusWorkspaceTarget(root, target);
      expect(screen.getByRole("heading")).toHaveFocus();
    }
  });

  it("does not restore into a removed workspace or behind another open dialog", () => {
    const view = render(<main data-testid="workspace"><button>Trigger</button></main>);
    const root = screen.getByTestId("workspace");
    const trigger = screen.getByRole("button");
    view.unmount();
    render(<WorkspaceDialog labelledBy="test-dialog" onDismiss={vi.fn()}>{content()}</WorkspaceDialog>);
    focusWorkspaceTarget(root, trigger);
    expect(screen.getByRole("button")).toHaveFocus();
    const otherRoot = document.createElement("main");
    const otherButton = document.createElement("button");
    otherRoot.append(otherButton); document.body.append(otherRoot);
    focusWorkspaceTarget(otherRoot, otherButton);
    expect(screen.getByRole("button", { name: "Safe control" })).toHaveFocus();
    otherRoot.remove();
  });
});
