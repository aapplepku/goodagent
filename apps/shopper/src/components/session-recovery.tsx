"use client";

import type { ShopperLoginRequest, ShopperRecovery } from "@open-commerce/sdk-typescript";
import { ArrowRight, LoaderCircle, LogIn, RefreshCw, Store } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import styles from "./session-recovery.module.css";

export type SessionRecoveryProps = {
  storeName?: string;
  guest: boolean;
  reason?: "expired" | "requested";
  onSignIn: (credentials: ShopperLoginRequest) => Promise<void>;
  onCheckSession: () => Promise<void>;
  onStartGuest?: () => Promise<void>;
  onRecover?: (credentials: ShopperRecovery) => Promise<void>;
  recoveryReceipt?: { code: string | null; verified: boolean } | null;
  onVerifyRecovery?: () => Promise<void>;
  onAcknowledgeRecovery?: () => Promise<void>;
};

export class SessionRecoveryError extends Error {
  constructor(readonly reason: "guest_conflict" | "identity_changed" | "verification_pending") {
    super(reason);
  }
}

const reasonMessages: Record<SessionRecoveryError["reason"], string> = {
  guest_conflict: "We couldn't start a new guest visit. No new visit was confirmed. Choose Check session to continue a visit opened elsewhere.",
  identity_changed: "The recovered session changed. Its replacement code is no longer shown. Check session or sign in explicitly.",
  verification_pending: "Recovery returned a response, but its session could not be verified. Choose Check recovered session; recovery will not be resubmitted.",
};

type RecoveryAction = "signIn" | "checkSession" | "startGuest" | "recoverAccount" | "verifyRecovery" | "acknowledgeRecovery";

const pendingMessages: Record<RecoveryAction, string> = {
  signIn: "Signing in...",
  checkSession: "Checking session...",
  startGuest: "Starting a new guest visit...",
  recoverAccount: "Recovering account...",
  verifyRecovery: "Checking recovered session...",
  acknowledgeRecovery: "Checking recovered session...",
};

const errorMessages: Record<RecoveryAction, string> = {
  signIn: "We couldn't sign you in. Check your details and try again.",
  checkSession: "Your session could not be restored. Try again or sign in.",
  startGuest: "We couldn't start a new guest visit. Please try again.",
  recoverAccount: "Recovery could not be confirmed. It may have completed. Check session or sign in with your chosen new password before submitting a recovery code again.",
  verifyRecovery: "We couldn't verify the recovered session. Check it again here; recovery will not be resubmitted.",
  acknowledgeRecovery: "We couldn't verify the recovered session. Keep this receipt and check again; continuing will not resubmit recovery.",
};

/**
 * Render in place of private shopper views after session expiry. The parent owns
 * server-verified identity and restores unsent text only for the same account and
 * store. Callbacks reject on failure; this view never restores private state.
 */
export function SessionRecovery({
  storeName,
  guest,
  reason = "expired",
  onSignIn,
  onCheckSession,
  onStartGuest,
  onRecover,
  recoveryReceipt,
  onVerifyRecovery,
  onAcknowledgeRecovery,
}: SessionRecoveryProps) {
  const id = useId();
  const title = useRef<HTMLHeadingElement>(null);
  const inFlight = useRef(false);
  const lifecycle = useRef(0);
  const receiptTitle = useRef<HTMLHeadingElement>(null);
  const [usingCode, setUsingCode] = useState(reason === "requested");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<RecoveryAction | null>(null);
  const [error, setError] = useState("");
  const busy = pending !== null;
  const recoveryForm = reason === "requested" || usingCode;

  useEffect(() => {
    title.current?.focus();
    return () => { lifecycle.current += 1; };
  }, []);

  const hasReceipt = Boolean(recoveryReceipt);
  useEffect(() => {
    if (hasReceipt) {
      setPassword("");
      setCode("");
      receiptTitle.current?.focus();
    }
  }, [hasReceipt, recoveryReceipt?.verified]);

  async function recover(action: RecoveryAction, work: () => Promise<void>) {
    // State alone does not block a second event before React commits the update.
    if (inFlight.current) return;
    const generation = lifecycle.current;
    inFlight.current = true;
    setPending(action);
    setError("");
    try {
      await work();
      if (generation !== lifecycle.current) return;
      setPassword("");
      setCode("");
    } catch (cause) {
      if (generation !== lifecycle.current) return;
      // Callback errors can contain request details; expose only local copy.
      setError(cause instanceof SessionRecoveryError
        ? reasonMessages[cause.reason]
        : errorMessages[action]);
    } finally {
      if (generation === lifecycle.current) {
        inFlight.current = false;
        setPending(null);
      }
    }
  }

  function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || !event.currentTarget.reportValidity()) return;
    if (recoveryForm) {
      if (onRecover) void recover("recoverAccount", () => onRecover({ username, code, password }));
    } else void recover("signIn", () => onSignIn({ username, password }));
  }

  return (
    <main className={styles.screen} aria-labelledby={`${id}-title`}>
      <header className={styles.brand}>
        <span className={styles.brandName}>
          <Store size={22} aria-hidden="true" />
          GoodAgent
        </span>
        {storeName && <span className={styles.storeName}>{storeName}</span>}
      </header>

      <section className={styles.content} aria-labelledby={`${id}-title`}>
        <h1
          className={styles.title}
          id={`${id}-title`}
          ref={title}
          tabIndex={-1}
          aria-describedby={`${id}-explanation`}
        >
          {reason === "requested" ? "Recover your shopping account" : "Your shopping session expired"}
        </h1>
        <p className={styles.explanation} id={`${id}-explanation`}>
          {reason === "requested"
            ? "Use your one-time recovery code to access an existing account. This does not transfer this guest visit's conversations or cart to that account."
            : guest
            ? "Your guest visit was temporary. Sign in to an existing account to access its saved shopping data."
            : "Your session may have expired or changed in another tab. Sign in to return to your account."}
        </p>

        <div className={styles.actions} aria-busy={busy}>
          {recoveryReceipt ? <section className={styles.receipt} aria-label="Account recovery receipt">
            <h2 ref={receiptTitle} tabIndex={-1}>
              {!recoveryReceipt.verified ? "Check your recovered session"
                : recoveryReceipt.code ? "Save your replacement recovery code" : "Replacement recovery code unavailable"}
            </h2>
            {!recoveryReceipt.verified ? <>
              <p className={styles.note}>Recovery returned a response. Verify this same account before viewing its replacement code. This check does not submit recovery again.</p>
              <button className={styles.secondary} disabled={busy} onClick={() => onVerifyRecovery && void recover("verifyRecovery", onVerifyRecovery)}>
                <RefreshCw size={18} aria-hidden="true" /> Check recovered session
              </button>
            </> : <>
              {recoveryReceipt.code ? <>
                <p className={styles.note}>Store it privately before continuing. It replaces the code you used and can recover this account once. It is not saved in this browser; reloading or leaving this page loses it.</p>
                <output className={styles.code} aria-label="Replacement recovery code">{recoveryReceipt.code}</output>
              </> : <p className={styles.note}>The recovery response did not include a replacement code. Your session was verified, but no code was delivered here. Do not resubmit the code you used.</p>}
              <button className={styles.primary} disabled={busy} onClick={() => onAcknowledgeRecovery && void recover("acknowledgeRecovery", onAcknowledgeRecovery)}>
                <ArrowRight size={18} aria-hidden="true" />
                {recoveryReceipt.code ? "I stored it privately; continue" : "Continue without a replacement code"}
              </button>
            </>}
          </section> : <>
          <form className={styles.form} aria-label={recoveryForm ? "Recover account" : "Sign in"} onSubmit={signIn}>
            <label className={styles.field} htmlFor={`${id}-username`}>
              Username
              <input
                id={`${id}-username`}
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                required
                disabled={busy}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            {recoveryForm && <label className={styles.field} htmlFor={`${id}-code`}>
              Recovery code
              <input id={`${id}-code`} name="code" type="password" autoComplete="off" autoCapitalize="none" spellCheck={false}
                required disabled={busy} value={code} onChange={(event) => setCode(event.target.value)} />
            </label>}
            <label className={styles.field} htmlFor={`${id}-password`}>
              {recoveryForm ? "New password" : "Password"}
              <input
                id={`${id}-password`}
                name="password"
                type="password"
                autoComplete={recoveryForm ? "new-password" : "current-password"}
                minLength={recoveryForm ? 10 : 1}
                maxLength={128}
                aria-describedby={recoveryForm ? `${id}-password-guidance` : undefined}
                required
                disabled={busy}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {recoveryForm && <p className={styles.note} id={`${id}-password-guidance`}>Use 10 to 128 characters for your new password.</p>}
            <button className={styles.primary} type="submit" disabled={busy || (recoveryForm && !onRecover)}>
              {pending === "signIn" || pending === "recoverAccount"
                ? <LoaderCircle size={18} aria-hidden="true" />
                : <LogIn size={18} aria-hidden="true" />}
              <span>{recoveryForm ? "Recover account" : "Sign in"}</span>
            </button>
          </form>
          {onRecover && reason !== "requested" && <button className={styles.secondary} type="button" disabled={busy} onClick={() => {
            setUsingCode(!usingCode); setPassword(""); setCode(""); setError("");
          }}>{usingCode ? "Back to sign in" : "Use a recovery code"}</button>}

          <div className={styles.check}>
            <p className={styles.note} id={`${id}-check-notice`}>
              {reason === "requested" ? "Not ready to recover? Check the current session and return to shopping." : "Opened a visit or signed in in another tab?"}
            </p>
            <button
              className={styles.secondary}
              type="button"
              disabled={busy}
              aria-describedby={`${id}-check-notice`}
              onClick={() => void recover("checkSession", onCheckSession)}
            >
              {pending === "checkSession"
                ? <LoaderCircle size={18} aria-hidden="true" />
                : <RefreshCw size={18} aria-hidden="true" />}
              <span>{reason === "requested" ? "Return to current visit" : "Check session"}</span>
            </button>
          </div>

          {onStartGuest && reason !== "requested" && (
            <div className={styles.guest}>
              <p className={styles.note} id={`${id}-guest-notice`}>
                A new guest visit starts fresh. Progress from the expired visit,
                including unsent messages, won&apos;t transfer.
              </p>
              <button
                className={styles.secondary}
                type="button"
                disabled={busy}
                aria-describedby={`${id}-guest-notice`}
                onClick={() => void recover("startGuest", onStartGuest)}
              >
                {pending === "startGuest"
                  ? <LoaderCircle size={18} aria-hidden="true" />
                  : <ArrowRight size={18} aria-hidden="true" />}
                <span>Start a new guest visit</span>
              </button>
            </div>
          )}
          </>}
        </div>

        <div className={styles.feedback}>
          <p className={styles.error} role="alert" aria-atomic="true">{error}</p>
          <p className={styles.note} role="status" aria-atomic="true">
            {pending ? pendingMessages[pending] : ""}
          </p>
        </div>
      </section>
    </main>
  );
}
