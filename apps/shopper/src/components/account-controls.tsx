"use client";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  Check,
  KeyRound,
  LogIn,
  LogOut,
  Monitor,
  ShoppingCart,
  Trash2,
  UserRoundPlus,
  X,
} from "lucide-react";
import type {
  ShopperAccount,
  ShopperAuthResponse,
  ContinuityResponse,
  SessionList,
} from "@open-commerce/sdk-typescript";
import { useShopperTransport } from "@/lib/shopper-transport";
import { isSessionExpired, useShopperSessionError } from "@/lib/session-errors";

export function AccountControls({
  account,
  onAccount,
  onClose,
  onDeleted,
  memoryUpdating = false,
  memoryUncertain = false,
  onMemoryChange,
  pending = false,
  onActionStart,
  onActionEnd,
  onRecoveryStart,
}: {
  account: ShopperAccount;
  onAccount: (value: ShopperAuthResponse) => void;
  onClose: () => void;
  onDeleted: () => void;
  memoryUpdating?: boolean;
  memoryUncertain?: boolean;
  onMemoryChange?: (enabled: boolean) => Promise<void>;
  pending?: boolean;
  onActionStart?: () => boolean;
  onActionEnd?: () => void;
  onRecoveryStart?: () => void;
}) {
  const handleSessionError = useShopperSessionError();
  const parentTransport = useShopperTransport();
  const transport = useMemo(() => parentTransport.forAccount(account.id), [parentTransport, account.id]);
  const shopperRequest = transport.request;
  const [mode, setMode] = useState<"register" | "login">(
    "register",
  );
  const [error, setError] = useState("");
  const [localBusy, setBusy] = useState(false);
  const busy = localBusy || memoryUpdating || pending;
  const [merge, setMerge] = useState<ContinuityResponse | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionList | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deletionPhase, setDeletionPhase] = useState<"idle" | "pending" | "complete">("idle");
  const closeButton = useRef<HTMLButtonElement>(null);
  const memoryCheckbox = useRef<HTMLInputElement>(null);
  const memoryDescriptionId = useId();
  const generation = useRef(0);

  useEffect(() => {
    setBusy(false);
    return () => { generation.current += 1; };
  }, [account.id, handleSessionError]);

  useEffect(() => {
    if (memoryCheckbox.current) memoryCheckbox.current.indeterminate = memoryUncertain;
  }, [memoryUncertain]);

  useEffect(() => {
    const opener = document.activeElement;
    closeButton.current?.focus();
    return () => {
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);

  async function action(work: (isCurrent: () => boolean) => Promise<void>, credential: false | "login" = false) {
    if (busy || (onActionStart && !onActionStart())) return;
    const epoch = generation.current;
    const isCurrent = () => epoch === generation.current;
    setBusy(true);
    setError("");
    try {
      await work(isCurrent);
    } catch (e) {
      if (!isCurrent()) return;
      if (!credential && handleSessionError(e)) return;
      if (credential === "login" && isSessionExpired(e)) {
        // Credential/grant failures and changed-cookie denials share a 401 envelope.
        // Check the original guest, never discover/adopt the replacement account.
        try {
          await shopperRequest("/v1/shopper/me");
        } catch (identityError) {
          if (isCurrent() && handleSessionError(identityError)) return;
        }
        if (!isCurrent()) return;
      }
      setDeletionPhase((phase) => phase === "pending" ? "idle" : phase);
      setError((e as Error).message);
    } finally {
      if (isCurrent()) setBusy(false);
      // The parent binds completion to the issuing session, including drawer close.
      onActionEnd?.();
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    await action(async (isCurrent) => {
      const result = await shopperRequest<ContinuityResponse>(
        `/v1/shopper/auth/${mode}`,
        "POST",
        body,
      );
      if (result.merge_token) {
        if (isCurrent()) setMerge(result);
      }
      else {
        onAccount(result);
        if (isCurrent()) setCode(result.recovery_code ?? null);
      }
    }, mode === "register" ? false : mode);
  }
  return (
    <aside
      className="memory-drawer account-controls"
      aria-label="Shopping account"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <header>
        <strong>
          {account.is_guest ? "Save your progress" : "Your account"}
        </strong>
        <button
          ref={closeButton}
          title="Close account"
          aria-label="Close account"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      {error && <p className="account-error" role="alert">{error}</p>}
      {code && (
        <section>
          <h3>One-time recovery code</h3>
          <p>
            Store it privately. It can be used once to recover this account.
          </p>
          <code>{code}</code>
          <button className="account-command" onClick={() => setCode(null)}>
            <Check size={18} aria-hidden="true" />
            <span>I have stored it</span>
          </button>
        </section>
      )}
      {merge ? (
        <section className="cart-continuity">
          <h3>Which cart should we keep?</h3>
          <p>
            Your conversation will be preserved. Quantities will not be
            combined. The other cart will be discarded; this cannot be undone.
          </p>
          <p>
            This visit's activity logs and personal monitoring rules are temporary
            and will be discarded when you choose a cart and finish signing in.
            {" "}Demo orders from this guest visit do not transfer to an existing account.
          </p>
          {([
            ["This visit", merge.guest_cart_lines],
            ["Account cart", merge.account_cart_lines],
          ] as const).map(([label, lines]) => (
            <div key={label}>
              <h4>{label}</h4>
              <ul>{lines?.map((line, index) => (
                <li key={index}>
                  {line.title}{line.variant_title && line.variant_title !== line.title ? ` (${line.variant_title})` : ""} &times; {line.quantity}
                </li>
              ))}</ul>
            </div>
          ))}
          {(["keep_guest", "keep_account"] as const).map((choice) => (
            <button
              key={choice}
              className="account-command"
              disabled={busy}
              onClick={() =>
                void action(async (isCurrent) => {
                  const result = await shopperRequest<ContinuityResponse>(
                    "/v1/shopper/auth/merge",
                    "POST",
                    { token: merge.merge_token, cart_choice: choice },
                  );
                  onAccount(result);
                  if (isCurrent()) setMerge(null);
                }, "login")
              }
            >
              <ShoppingCart size={18} aria-hidden="true" />
              <span>{choice === "keep_guest"
                ? `Keep this visit's cart (${merge.guest_cart_items} ${merge.guest_cart_items === 1 ? "product" : "products"})`
                : `Keep account cart (${merge.account_cart_items} ${merge.account_cart_items === 1 ? "product" : "products"})`}</span>
            </button>
          ))}
          <button className="account-command cart-continuity-back" disabled={busy} onClick={() => { setMerge(null); setError(""); }}>
            <ArrowLeft size={18} aria-hidden="true" />
            <span>Back to sign in</span>
          </button>
          {busy && <p role="status">Signing in and keeping your chosen cart...</p>}
        </section>
      ) : account.is_guest ? (
        <form onSubmit={(e) => void submit(e)}>
          <p>
            Continue shopping now. An account keeps your conversations, cart,
            and saved preferences across visits.
          </p>
          <div className="auth-tabs">
            {(["register", "login"] as const).map((value) => (
              <button
                key={value}
                type="button"
                disabled={busy}
                onClick={() => setMode(value)}
                data-active={mode === value}
              >
                {value === "register"
                  ? "Create account"
                  : "Sign in"}
              </button>
            ))}
            {onRecoveryStart && <button type="button" disabled={busy} onClick={onRecoveryStart}>
              <KeyRound size={16} aria-hidden="true" /> Recover
            </button>}
          </div>
          {mode === "login" && (
            <p>
              Signing in saves this visit's conversations and preferences to your
              account. If both carts contain items, you will choose which cart to keep.
              {" "}This visit's activity logs and personal monitoring rules are temporary
              and will be discarded when sign-in is completed.
              {" "}Demo orders from this guest visit do not transfer to an existing account.
            </p>
          )}
          {mode === "register" && (
            <label>
              Display name
              <input name="display_name" required maxLength={80} />
            </label>
          )}
          <label>
            Username
            <input
              name="username"
              required
              minLength={3}
              maxLength={40}
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              required
              type="password"
              minLength={mode === "login" ? 1 : 10}
              maxLength={128}
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
            />
          </label>
          {mode === "register" && (
            <p>
              Clearly stated shopping preferences are saved automatically. You
              can turn memory off or delete it anytime.
            </p>
          )}
          <button className="account-command" disabled={busy}>
            {mode === "register" ? (
              <UserRoundPlus size={18} aria-hidden="true" />
            ) : (
              <LogIn size={18} aria-hidden="true" />
            )}
            <span>{busy
              ? "Saving..."
              : mode === "register"
                ? "Save my progress"
                : "Sign in"}</span>
          </button>
        </form>
      ) : (
        <section>
          <p>Signed in as {account.display_name}</p>
          <button
            className="account-command"
            disabled={busy}
            onClick={() =>
              void action(async (isCurrent) => {
                const result = await shopperRequest<SessionList>("/v1/shopper/auth/sessions");
                if (isCurrent()) setSessions(result);
              })
            }
          >
            <Monitor size={18} aria-hidden="true" />
            <span>View active sessions</span>
          </button>
          {sessions?.items.map((item) => (
            <p key={item.id}>
              {item.current ? "This device" : "Another session"} ·{" "}
              {new Date(item.created_at).toLocaleString()}
            </p>
          ))}
          <button
            className="account-command"
            disabled={busy}
            onClick={() =>
              void action(async (isCurrent) => {
                await shopperRequest("/v1/shopper/auth/sessions", "DELETE");
                if (isCurrent()) location.reload();
              })
            }
          >
            <LogOut size={18} aria-hidden="true" />
            <span>Sign out everywhere</span>
          </button>
        </section>
      )}
      <section className="account-memory">
        <label className="account-memory-toggle">
          <input
            ref={memoryCheckbox}
            type="checkbox"
            aria-describedby={memoryDescriptionId}
            checked={account.memory_enabled !== false}
            disabled={busy}
            onChange={(e) => {
              const enabled = e.target.checked;
              void action(async () => {
                if (onMemoryChange) await onMemoryChange(enabled);
                else {
                  const result = await shopperRequest<ShopperAuthResponse>(
                    "/v1/shopper/preferences", "PATCH", { enabled },
                  );
                  onAccount(result);
                }
              });
            }}
          />
          <span>Remember shopping preferences</span>
        </label>
        <p id={memoryDescriptionId}>
          {account.is_guest
            ? "Temporary for this visit, up to 24 hours."
            : "Off disables both saving and recall. Existing memories stay until you delete them."}
        </p>
      </section>
      <section>
        <button className="account-command" aria-expanded={deleting} disabled={busy} onClick={() => {
          setDeleting(!deleting);
          setDeletionPhase("idle");
        }}>
          <Trash2 size={18} aria-hidden="true" />
          <span>Delete shopping data</span>
        </button>
        {deleting && (
          <>
            <p>
              This deletes conversations, saved preferences, personal activity,
              and personal monitors. Demo checkout audit records are retained.
            </p>
            <button
              className="account-command"
              disabled={busy}
              onClick={() =>
                void action(async (isCurrent) => {
                  setDeletionPhase("pending");
                  await shopperRequest("/v1/shopper/shopping-data", "DELETE");
                  if (isCurrent()) {
                    setDeleting(false);
                    setDeletionPhase("complete");
                  }
                  onDeleted();
                })
              }
            >
              <Trash2 size={18} aria-hidden="true" />
              <span>Confirm deletion</span>
            </button>
          </>
        )}
        {deletionPhase === "pending" && <p role="status">Deleting shopping data...</p>}
        {deletionPhase === "complete" && <p role="status">Shopping data deleted. Demo checkout audit records are retained.</p>}
      </section>
    </aside>
  );
}
