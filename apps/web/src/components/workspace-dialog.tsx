"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";
import styles from "./manager-workspace.module.css";

export function WorkspaceDialog({ labelledBy, pending = false, onDismiss, children }: {
  labelledBy: string;
  pending?: boolean;
  onDismiss: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const backdropPress = useRef(false);

  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (!element.open) element.showModal();
    element.querySelector<HTMLElement>("[data-dialog-initial]")?.focus({ preventScroll: true });
    // The workspace owns return focus, including transitions to another dialog/view.
    return () => { if (element.open) element.close(); };
  }, []);

  useLayoutEffect(() => {
    const element = dialog.current;
    if (pending && element && (!element.contains(document.activeElement)
      || document.activeElement?.matches(":disabled"))) {
      element.querySelector<HTMLElement>("[data-dialog-heading]")?.focus({ preventScroll: true });
    }
  }, [pending]);

  return <dialog ref={dialog} className={styles.modalBackdrop} aria-labelledby={labelledBy}
    aria-modal="true" aria-busy={pending || undefined}
    onCancel={(event) => {
      event.preventDefault();
      if (!pending) onDismiss();
    }}
    onMouseDown={(event) => { backdropPress.current = event.target === event.currentTarget; }}
    onClick={(event) => {
      if (backdropPress.current && event.target === event.currentTarget && !pending) onDismiss();
      backdropPress.current = false;
    }}>
    {children}
  </dialog>;
}

export function focusWorkspaceTarget(root: HTMLElement | null, preferred: HTMLElement | null) {
  if (!root?.isConnected || document.querySelector("dialog[open]")) return;
  let usable = !!preferred?.isConnected && root.contains(preferred)
    && !preferred.closest("[hidden], [inert], :disabled");
  for (let node = preferred; usable && node; node = node.parentElement) {
    const style = window.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") usable = false;
  }
  const target = usable ? preferred : root.querySelector<HTMLElement>("[data-workspace-focus]") ?? root;
  target?.focus({ preventScroll: true });
}
