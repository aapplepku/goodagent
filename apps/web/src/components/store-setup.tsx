"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import type {
  ImportConfirmRequest,
  ImportReview,
  OwnerAuthResponse,
  SetupStatus,
  StoreReadiness,
  StoreProfile,
  StoreProfileUpdate,
  StoreMeasurements,
} from "@open-commerce/sdk-typescript";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Circle,
  ExternalLink,
  LogOut,
  RefreshCw,
  Settings2,
  Upload,
  X,
} from "lucide-react";
import styles from "./store-setup.module.css";
import { StoreNavigationContext } from "./store-navigation";
import { CatalogIndexProgress } from "./catalog-index-progress";
import { createMerchantTransport, type MerchantRequest, type MerchantTransport } from "@/lib/api";
import { MerchantTransportContext, useMerchantTransport } from "@/lib/merchant-transport";
import { MerchantDisplayProvider, useMerchantDisplay } from "@/lib/merchant-display";
import { MerchantStoreIdentity } from "./merchant-store-identity";

type OwnerSession = { identity: OwnerAuthResponse; transport: MerchantTransport; key: number; isActive: () => boolean };
type SetupSnapshot = { state: StoreReadiness; review: ImportReview | null };
type ImportConfirmation = { importId: string; body: ImportConfirmRequest; key: string };

function selectedCatalog(snapshot: SetupSnapshot | null) {
  const review = snapshot?.review;
  return review?.status === "confirmed" && review.id === snapshot?.state.latest_import_id &&
    review.catalog_id && review.catalog_id === snapshot.state.indexing.catalog_id &&
    review.indexing?.catalog_id === review.catalog_id ? review.catalog_id : null;
}

export function StoreAccess({ children, initialView = "setup" }: {
  children: ReactNode;
  initialView?: "setup" | "workspace";
}) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [session, setSession] = useState<OwnerSession | null>(null);
  const owner = session?.identity;
  const mounted = useRef(false);
  const generation = useRef(0);
  const base = useMemo(() => createMerchantTransport({ isActive: () => mounted.current }), []);
  const [expired, setExpired] = useState(false);
  const [view, setView] = useState(initialView);
  const [setupStage, setSetupStage] = useState<number | undefined>();
  const [checked, setChecked] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const [error, setError] = useState("");
  function endSession(key: number, sessionExpired = false) {
    if (!mounted.current || generation.current !== key) return;
    generation.current += 1;
    setSession(null);
    setExpired(sessionExpired);
    setSigningOut(false);
    setLogoutError("");
  }
  function acceptOwner(identity: OwnerAuthResponse) {
    if (!mounted.current) return;
    const key = ++generation.current;
    const isActive = () => mounted.current && generation.current === key;
    const transport = createMerchantTransport({
      binding: { ownerId: identity.user_id, storeId: identity.store.id },
      isActive,
      onSessionExpired: () => endSession(key, true),
    });
    setSession({ identity, transport, key, isActive });
    setExpired(false);
    setLogoutError("");
    setSetupStage(undefined);
    setView(identity.store.sharing_enabled ? "workspace" : initialView);
    setStatus((current) => current && { ...current, setup_required: false });
  }
  useEffect(() => {
    let active = true;
    mounted.current = true;
    setChecked(false);
    setError("");
    void base.request<SetupStatus>("/v1/merchant/auth/status")
      .then(async (next) => {
        if (!active) return;
        setStatus(next);
        if (next.profile !== "legacy_demo") {
          try {
            const identity = await base.request<OwnerAuthResponse>(
              "/v1/merchant/auth/me",
            );
            if (!active) return;
            acceptOwner(identity);
          } catch (cause) {
            if (!(cause instanceof OpenCommerceApiError && cause.status === 401)) throw cause;
            if (active) setSession(null);
          }
        }
      })
      .catch((e: Error) => active && setError(e.message))
      .finally(() => active && setChecked(true));
    return () => { active = false; mounted.current = false; generation.current += 1; };
  }, [attempt]);
  async function logout() {
    if (!session || signingOut) return;
    setSigningOut(true);
    setLogoutError("");
    try {
      await session.transport.request("/v1/merchant/auth/logout", "POST");
      endSession(session.key);
    } catch {
      if (generation.current === session.key)
        setLogoutError("Sign-out not confirmed. Your session may still be active. Please retry.");
    } finally {
      if (generation.current === session.key) setSigningOut(false);
    }
  }
  if (status?.profile === "legacy_demo") return children;
  if (!checked || !status || error)
    return (
      <main className={styles.shell}>
        <p role={error ? "alert" : "status"}>{error || "Opening your store..."}</p>
        {error && (
          <button onClick={() => setAttempt((value) => value + 1)}>
            <RefreshCw size={16} />
            Retry
          </button>
        )}
      </main>
    );
  if (!owner || !session) return <OwnerSignIn status={status} expired={expired} request={base.request} onDone={acceptOwner} />;
  return <MerchantTransportContext.Provider key={session.key} value={session.transport}>
    <MerchantDisplayProvider initialStore={owner.store} isActive={session.isActive}>
    <StoreNavigationContext.Provider value={{
      openProducts: () => { setSetupStage(0); setView("setup"); },
      onSessionExpired: () => endSession(session.key, true),
    }}>
    {view === "workspace" ? (
      <div className={styles.workspace}>
        <div className={styles.workspaceBar}>
          <MerchantStoreIdentity compact />
          <button aria-label="Store setup & sharing" title="Store setup & sharing"
            onClick={() => { setSetupStage(undefined); setView("setup"); }}>
            <Settings2 size={18} /><span>Store setup & sharing</span>
          </button>
          <button
            aria-label="Sign out" title="Sign out"
            disabled={signingOut}
            onClick={() => void logout()}
          >
            <LogOut size={15} />
            <span>Sign out</span>
          </button>
        </div>
        {logoutError && <div role="alert" className={styles.workspaceError}>
          <span>{logoutError}</span>
          <button aria-label="Dismiss sign-out notice" title="Dismiss" onClick={() => setLogoutError("")}>
            <X size={16} />
          </button>
        </div>}
        {children}
      </div>
    ) : (
    <StoreSetup
      owner={owner}
      initialStage={setupStage}
      onWorkspace={() => setView("workspace")}
      onLogout={() => endSession(session.key)}
      onRecoveryAcknowledged={() => setSession((current) => current?.key === session.key
        ? { ...current, identity: { ...current.identity, recovery_code: null } } : current)}
    />
    )}
    </StoreNavigationContext.Provider>
    </MerchantDisplayProvider>
  </MerchantTransportContext.Provider>;
}

function OwnerSignIn({
  status,
  onDone,
  request: storeRequest,
  expired,
}: {
  status: SetupStatus;
  onDone: (value: OwnerAuthResponse) => void;
  request: MerchantRequest;
  expired: boolean;
}) {
  const [recovery, setRecovery] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const active = useRef(false);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    active.current = true;
    if (expired) title.current?.focus();
    return () => { active.current = false; };
  }, [expired]);
  async function authenticate(work: () => Promise<OwnerAuthResponse>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const identity = await work();
      if (active.current) onDone(identity);
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      inFlight.current = false;
      if (active.current) setBusy(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const values = Object.fromEntries(form);
    await authenticate(() => storeRequest<OwnerAuthResponse>(
          `/v1/merchant/auth/${status.setup_required ? "setup" : recovery ? "recover" : "login"}`,
          "POST",
          values,
        ));
  }
  return (
    <main className={styles.shell}>
      <header className={styles.brand}>GoodAgent</header>
      <section className={styles.auth} aria-labelledby="owner-session-title" aria-busy={busy}>
        <h1 id="owner-session-title" ref={title} tabIndex={-1}>
          {expired && !recovery ? "Your store session expired" : status.setup_required
            ? "Make it your store"
            : recovery
              ? "Recover your account"
              : "Welcome back"}
        </h1>
        {expired && <>
          <p>Your session may have expired or changed in another tab. Sign in or check the current session to continue.</p>
          <div className={styles.actions}>
            <button type="button" disabled={busy}
              onClick={() => void authenticate(() => storeRequest<OwnerAuthResponse>("/v1/merchant/auth/me"))}>
              <RefreshCw size={16} /> Check session
            </button>
          </div>
        </>}
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {status.login_method === "oidc" ? (
          <button
            className={styles.primary}
            disabled={busy}
            onClick={() =>
              location.assign("/api/runtime/v1/merchant/auth/oidc/start")
            }
          >
            Continue with your sign-in provider <ArrowRight size={16} />
          </button>
        ) : (
          <form onSubmit={(e) => void submit(e)}>
            {status.setup_required && (
              <>
                <label>
                  Store name
                  <input name="name" required maxLength={120} autoFocus />
                </label>
                <label>
                  Instance setup token
                  <input
                    name="bootstrap_token"
                    type="password"
                    required
                    autoComplete="off"
                  />
                </label>
                <small>
                  Use the one-time token issued from your instance console.
                </small>
              </>
            )}
            <label>
              Username
              <input
                name="username"
                required
                autoComplete="username"
                minLength={3}
                maxLength={80}
              />
            </label>
            {recovery && (
              <label>
                Single-use recovery code
                <input
                  name="recovery_code"
                  type="password"
                  required
                  autoComplete="off"
                />
              </label>
            )}
            <label>
              {recovery ? "New password" : "Password"}
              <input
                name="password"
                type="password"
                required
                minLength={status.setup_required || recovery ? 12 : 1}
                maxLength={128}
                autoComplete={
                  status.setup_required || recovery
                    ? "new-password"
                    : "current-password"
                }
              />
            </label>
            <button className={styles.primary} disabled={busy}>
              {busy
                ? "Checking..."
                : status.setup_required
                  ? "Create my store"
                  : recovery
                    ? "Recover account"
                    : "Sign in"}
              <ArrowRight size={16} />
            </button>
            {!status.setup_required && (
              <button type="button" disabled={busy} onClick={() => setRecovery(!recovery)}>
                {recovery ? "Back to sign in" : "Use a recovery code"}
              </button>
            )}
          </form>
        )}
      </section>
    </main>
  );
}

const fields = [
  "product_id",
  "title",
  "price",
  "currency",
  "description",
  "category",
  "brand",
  "variant_id",
  "sku",
  "inventory_quantity",
  "image_url",
];
const readinessNames: Record<string, string> = {
  catalog_verified: "Products verified",
  images_reviewed: "Images reviewed",
  search_tested: "Shopper search tested",
  ai_verified: "AI connection verified",
  demo_checkout_acknowledged: "Demo checkout acknowledged",
  sharing_enabled: "Store link enabled",
};
const monitoringPresets = {
  failed_imports: "Failed imports",
  unavailable_ai: "Failed AI connection checks",
  empty_results: "Empty search results",
} as const;

function StoreSetup({
  owner,
  initialStage,
  onWorkspace,
  onLogout,
  onRecoveryAcknowledged,
}: {
  owner: OwnerAuthResponse;
  initialStage?: number;
  onWorkspace: () => void;
  onLogout: () => void;
  onRecoveryAcknowledged: () => void;
}) {
  const transport = useMerchantTransport();
  const display = useMerchantDisplay();
  const storeRequest = transport.request;
  const [snapshot, setSnapshot] = useState<SetupSnapshot | null>(null);
  const state = snapshot?.state ?? null;
  const review = snapshot?.review ?? null;
  const snapshotCurrent = useRef<SetupSnapshot | null>(null);
  const refreshGeneration = useRef(0);
  const active = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const [snapshotFresh, setSnapshotFresh] = useState(false);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [currency, setCurrency] = useState("");
  const [stage, setStage] = useState(initialStage ?? 0);
  const stageRestored = useRef(initialStage !== undefined);
  const refreshInFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [images, setImages] = useState(false);
  const confirmation = useRef<ImportConfirmation | null>(null);
  const [reviewConflict, setReviewConflict] = useState(false);
  const [demo, setDemo] = useState(false);
  const recoveryCode = owner.recovery_code;
  const [metrics, setMetrics] = useState<StoreMeasurements | null>(null);
  const [metricsError, setMetricsError] = useState(false);
  const catalog = selectedCatalog(snapshot);
  const matchedReview = Boolean(review && review.id === state?.latest_import_id);
  const count = state?.indexing.product_count ?? 0;
  const verified = Boolean(catalog && state?.checklist.catalog_verified &&
    state.indexing.status === "ready" && review?.indexing?.status === "ready" && count > 0 &&
    state.indexing.indexed_product_count === count && review.indexing.product_count === count &&
    review.indexing.indexed_product_count === count);
  const candidateAvailable = Boolean(catalog && snapshotFresh && !refreshing);
  const publishedCurrent = Boolean(
    state?.store.sharing_enabled && state.indexing.catalog_id &&
    state.store.published_catalog_id === state.indexing.catalog_id
  );
  const mappingChanged = Boolean(review && (
    Object.keys({ ...mapping, ...review.mapping }).some(
      (field) => (mapping[field] || "") !== (review.mapping[field] || ""),
    ) || currency !== (review.currency ?? "")
  ));
  const needsReview = reviewConflict || Boolean(review &&
    !["confirmed", "cancelled"].includes(review.status) && !review.review_fingerprint);
  async function refreshMetrics() {
    try {
      setMetrics(await storeRequest<StoreMeasurements>("/v1/merchant/store/measurements"));
      setMetricsError(false);
    } catch {
      setMetricsError(true);
    }
  }
  async function refresh({ preserveEdits = false, resume = false } = {}) {
    const request = ++refreshGeneration.current;
    const acceptDisplay = display?.captureRead();
    setRefreshing(true);
    setSnapshotFresh(false);
    try {
      const next = await storeRequest<StoreReadiness>("/v1/merchant/store");
      if (!active.current || request !== refreshGeneration.current) return;
      acceptDisplay?.(next.store);
      const data = next.latest_import_id
        ? await storeRequest<ImportReview>(`/v1/merchant/imports/${next.latest_import_id}`) : null;
      if (!active.current || request !== refreshGeneration.current) return;
      // Readiness and its exact import become visible together, never as independent snapshots.
      const updated = { state: next, review: data };
      const previous = snapshotCurrent.current;
      if (previous?.review?.id !== data?.id || selectedCatalog(previous) !== selectedCatalog(updated)) {
        setImages(false);
        setDemo(false);
      }
      snapshotCurrent.current = updated;
      setSnapshot(updated);
      setSnapshotFresh(true);
      if (!preserveEdits || previous?.review?.id !== data?.id) {
        setMapping(data?.mapping ?? {});
        setCurrency(data?.currency ?? "");
      }
      if (!stageRestored.current || resume) {
        stageRestored.current = true;
        setStage(data?.status === "review" || data?.status === "mapping" ? 0 :
          data?.status === "confirmed" && next.indexing.status !== "ready" ? 1 :
          next.store.sharing_enabled ? 2 : data?.status === "confirmed" ? 1 : 0);
      }
      return updated;
    } catch (cause) {
      if (active.current && request === refreshGeneration.current) throw cause;
    } finally {
      if (active.current && request === refreshGeneration.current) setRefreshing(false);
    }
  }
  useEffect(() => {
    active.current = true;
    void refresh().catch((e: Error) => setError(e.message));
    void refreshMetrics();
    return () => { active.current = false; refreshGeneration.current += 1; };
  }, []);
  useEffect(() => {
    if (
      review?.status !== "confirmed" ||
      (["ready", "failed"].includes(review.indexing?.status ?? "") &&
        ["ready", "failed"].includes(state?.indexing.status ?? ""))
    )
      return;
    const timer = setInterval(() => {
      if (refreshInFlight.current) return;
      refreshInFlight.current = true;
      void refresh().catch((e: Error) => setError(e.message))
        .finally(() => { refreshInFlight.current = false; });
    }, 2000);
    return () => clearInterval(timer);
  }, [review?.status, review?.indexing?.status, state?.indexing.status]);
  useEffect(() => {
    // Keep the candidate coherent on return from preview without overwriting draft mapping.
    if (stage === 0) return;
    const onFocus = () => {
      void refresh({ preserveEdits: true })
        .catch(() => { if (active.current) setError("Could not refresh readiness. Please retry."); });
    };
    window.addEventListener("focus", onFocus);
    return () => { window.removeEventListener("focus", onFocus); };
  }, [stage]);
  async function action(work: () => Promise<unknown>) {
    refreshGeneration.current += 1;
    setRefreshing(false);
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    if (file.size > 20 * 1024 * 1024)
      throw new Error("Choose a CSV no larger than 20 MiB.");
    await transport.upload(`/v1/merchant/imports/upload?filename=${encodeURIComponent(file.name)}`, file);
    await refresh();
  }
  async function confirmProducts() {
    if (!review?.review_fingerprint || !matchedReview || refreshing || !snapshotFresh ||
      needsReview || mappingChanged || review.errors?.length || review.status !== "review") return;
    const prior = confirmation.current;
    const sent = prior?.importId === review.id &&
      prior.body.expected_review_fingerprint === review.review_fingerprint ? prior : {
        importId: review.id,
        body: { expected_review_fingerprint: review.review_fingerprint },
        key: crypto.randomUUID(),
      };
    confirmation.current = sent;
    try {
      const result = await storeRequest<ImportReview>(
        `/v1/merchant/imports/${sent.importId}/confirm`, "POST", sent.body, sent.key,
      );
      if (!result || result.id !== sent.importId || result.status !== "confirmed" ||
        result.review_fingerprint !== sent.body.expected_review_fingerprint)
        throw new Error("Confirmation response unavailable. Retry confirmation.");
    } catch (cause) {
      if (active.current && cause instanceof OpenCommerceApiError && cause.status === 409) {
        setReviewConflict(true);
        setStage(0);
      }
      throw cause;
    }
    const next = await refresh();
    if (!next) return;
    confirmation.current = null;
    if (next.review?.id === sent.importId && next.review.status === "confirmed") setStage(1);
  }
  async function reviewLatestMapping() {
    const next = await refresh();
    if (!next) return;
    confirmation.current = null;
    setReviewConflict(false);
    setStage(0);
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: StoreProfileUpdate = {
      name: String(form.get("name")),
      description: String(form.get("description")),
      goal: String(form.get("goal")) || "Help shoppers find suitable products",
      currency: (state?.store.currency ??
        "USD") as StoreProfileUpdate["currency"],
    };
    await action(async () => {
      const updated = await storeRequest<StoreProfile>("/v1/merchant/store", "PATCH", payload);
      display?.acceptProfile(updated);
      await refresh();
    });
  }
  async function preview() {
    if (!candidateAvailable || !verified || !catalog) return;
    const result = await storeRequest<{ token: string; store_slug: string }>(
      "/v1/merchant/store/preview",
      "POST",
      { catalog_id: catalog },
    );
    // A fragment keeps the one-use preview grant out of server access logs and referrers.
    window.open(
      `/manager/preview?store=${encodeURIComponent(result.store_slug)}#preview=${encodeURIComponent(result.token)}`,
      "_blank",
      "noopener,noreferrer",
    );
  }
  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <span className={styles.brand}>GoodAgent</span>
        <div>
          <button onClick={onWorkspace}>
            Open workspace <ArrowRight size={15} />
          </button>
          <button
            aria-label="Sign out"
            title="Sign out"
            onClick={() =>
              void action(async () => {
                await storeRequest("/v1/merchant/auth/logout", "POST");
                onLogout();
              })
            }
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>
      <nav className={styles.steps} aria-label="Store setup">
        {["Products", "Preview", "Ready to share"].map((name, index) => (
          <button
            key={name}
            aria-current={index === stage ? "step" : undefined}
            onClick={() => { stageRestored.current = true; setStage(index); }}
          >
            <span>{index + 1}</span>
            {name}
          </button>
        ))}
      </nav>
      {recoveryCode && (
        <section className={styles.warning}>
          <strong>Your one-time recovery code</strong>
          <p>
            Keep this somewhere private. It is only shown now and can be used
            once.
          </p>
          <code>{recoveryCode}</code>
          <button onClick={onRecoveryAcknowledged}>
            I have stored it privately <Check size={15} />
          </button>
        </section>
      )}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {(needsReview || (review && !snapshotFresh)) && (
        <div className={styles.recoveryActions}>
          <button disabled={busy || refreshing} onClick={() => void action(reviewLatestMapping)}>
            Review latest mapping <RefreshCw size={16} />
          </button>
        </div>
      )}
      {!state ? (
        <p role="status">Loading setup...</p>
      ) : (
        <div className={styles.content}>
          {(stage === 1 || stage === 2) && <section aria-label="Selected catalog">
            <div className={styles.sectionHeader}>
              <h2>{matchedReview ? review!.filename : "No catalog selected"}</h2>
              <button disabled={busy || refreshing} onClick={() => void action(refresh)}
                aria-label="Refresh setup" title="Refresh setup"><RefreshCw size={17} /></button>
            </div>
            {catalog && <p>Catalog version: <code>{catalog}</code></p>}
            {(refreshing || !snapshotFresh || !catalog) && <div role="status">
              <p>{refreshing ? "Checking the selected catalog..." :
                review?.status === "review" || review?.status === "mapping"
                  ? "Review and confirm these products before previewing or sharing."
                  : "Catalog selection is not ready. Refresh setup or review your products."}</p>
              <button onClick={() => setStage(0)}>Review products <ArrowLeft size={16} /></button>
            </div>}
          </section>}
          {stage === 0 && (
            <>
              <h1>{review?.status === "review" ? "Review your products" : "Bring your products"}</h1>
              <details className={styles.sourceDetails} open={review?.status !== "review"}>
                <summary>Store details and catalog source</summary>
              <section>
                <form
                  onSubmit={(e) => void saveProfile(e)}
                  className={styles.profile}
                >
                  <label>
                    Store name
                    <input
                      name="name"
                      defaultValue={state.store.name}
                      required
                      maxLength={120}
                    />
                  </label>
                  <label>
                    Short description
                    <input
                      name="description"
                      defaultValue={state.store.description}
                      maxLength={500}
                    />
                  </label>
                  <label>
                    Business goal <small>Optional</small>
                    <input
                      name="goal"
                      defaultValue={state.store.goal}
                      maxLength={300}
                    />
                  </label>
                  <button disabled={busy}>
                    Save details <Check size={16} />
                  </button>
                </form>
              </section>
              <section className={styles.upload}>
                <label className={styles.primary}>
                  <Upload size={18} />
                  Upload catalog CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    disabled={busy}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void action(() => upload(file));
                      e.target.value = "";
                    }}
                  />
                </label>
                <button
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await storeRequest("/v1/merchant/imports/sample", "POST");
                      await refresh();
                    })
                  }
                >
                  Use sample products
                </button>
                <button onClick={onWorkspace}>Explore without data</button>
                <small>
                  Up to 20 MiB, 10,000 rows, and 64 columns. Generic and Shopify
                  CSV exports.
                </small>
              </section>
              </details>
              {review && (
                <section>
                  <div className={styles.sectionHeader}>
                    <h2>{review.filename}</h2>
                    <span>
                      {review.row_count} rows · {review.product_count ?? 0}{" "}
                      products
                    </span>
                  </div>
                  {review.sample_data && <p>Amazon Berkeley Objects sample, CC BY 4.0. Prices, stock and engagement are synthetic, not current offers.</p>}
                  {review.status === "review" && (
                    <p role="status">
                      {mappingChanged
                        ? "Mapping changes need validation."
                        : review.errors?.length
                          ? "Correct the validation errors before confirming products."
                        : `${review.product_count ?? 0} products ready to import. Awaiting your confirmation.`}
                    </p>
                  )}
                  {review.errors?.map((issue, i) => (
                    <p className={styles.error} key={i}>
                      Row {issue.row}: {issue.message}
                    </p>
                  ))}
                  {review.warnings?.map((warning, i) => (
                    <p key={i}>{warning}</p>
                  ))}
                  {!!review.products?.length && (
                    <div className={styles.table}>
                      <table>
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>Variants</th>
                            <th>Price</th>
                          </tr>
                        </thead>
                        <tbody>
                          {review.products.map((product) => (
                            <tr key={product.source_product_id}>
                              <td>{product.title}</td>
                              <td>{product.variants.length}</td>
                              <td>
                                {product.variants[0]?.currency}{" "}
                                {(
                                  (product.variants[0]?.price_minor ?? 0) / 100
                                ).toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {!["confirmed", "cancelled"].includes(review.status) && (
                    <>
                      <details key={review.id} className={styles.sourceDetails} open={Boolean(review.errors?.length)}>
                        <summary>Edit field mapping and currency</summary>
                      <div className={styles.mappings}>
                        {fields.map((field) => (
                          <label key={field}>
                            {field.replaceAll("_", " ")}
                            <select
                              value={mapping[field] ?? ""}
                              onChange={(e) =>
                                setMapping({
                                  ...mapping,
                                  [field]: e.target.value,
                                })
                              }
                            >
                              <option value="">Not mapped</option>
                              {review.columns.map((column) => (
                                <option key={column}>{column}</option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                      <label>
                        Price currency
                        <select
                          value={currency}
                          onChange={(e) => setCurrency(e.target.value)}
                        >
                          <option value="">Use mapped currency column</option>
                          {["USD", "EUR", "GBP", "CAD", "AUD"].map((value) => (
                            <option key={value}>{value}</option>
                          ))}
                        </select>
                      </label>
                        <button
                          disabled={busy || refreshing || !snapshotFresh || !matchedReview || needsReview}
                          onClick={() =>
                            void action(async () => {
                              if (!matchedReview || refreshing || !snapshotFresh || needsReview) return;
                              const request = refreshGeneration.current;
                              const next = await storeRequest<ImportReview>(
                                `/v1/merchant/imports/${review.id}/mapping`,
                                "PUT",
                                {
                                  mapping: Object.fromEntries(
                                    Object.entries(mapping).filter(
                                      ([, value]) => value,
                                    ),
                                  ),
                                  currency: currency || null,
                                },
                              );
                              if (!active.current || request !== refreshGeneration.current ||
                                snapshotCurrent.current?.review?.id !== next.id) return;
                              const updated = { ...snapshotCurrent.current, review: next };
                              snapshotCurrent.current = updated;
                              setSnapshot(updated);
                              setMapping(next.mapping);
                              setCurrency(next.currency ?? "");
                            })
                          }
                        >
                          Validate mapping <RefreshCw size={16} />
                        </button>
                      </details>
                      <div className={styles.actions}>
                        <button
                          className={styles.primary}
                          disabled={
                            busy ||
                            refreshing ||
                            !snapshotFresh ||
                            !matchedReview ||
                            needsReview ||
                            mappingChanged ||
                            Boolean(review.errors?.length) ||
                            review.status !== "review"
                          }
                          onClick={() => void action(confirmProducts)}
                        >
                          Confirm products <Check size={16} />
                        </button>
                        <button
                          title="Cancel import"
                          aria-label="Cancel import"
                          disabled={busy || refreshing || !snapshotFresh || !matchedReview}
                          onClick={() => {
                            if (!matchedReview || refreshing || !snapshotFresh) return;
                            if (!window.confirm(`Cancel ${review.filename}? This discards this import's review. Your published products will not change.`)) return;
                            void action(async () => {
                              await storeRequest(
                                `/v1/merchant/imports/${review.id}/cancel`,
                                "POST",
                              );
                              await refresh({ resume: true });
                            });
                          }}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    </>
                  )}

                </section>
              )}
            </>
          )}
          {stage === 1 && (
            <section>
              <h1>Try your store privately</h1>
              {catalog && <CatalogIndexProgress index={{ ...state.indexing, filename: null }} />}
              <button
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    const check = await storeRequest<{
                      detail: string;
                      connected: boolean;
                    }>("/v1/merchant/store/check-ai", "POST");
                    await refresh();
                    if (!check.connected) setError(check.detail);
                  })
                }
              >
                Check AI connection <RefreshCw size={16} />
              </button>
              <p>
                {verified
                  ? `${state.indexing.product_count} products verified. Your current shared catalog is unchanged.`
                  : catalog ? `Catalog status: ${(state.indexing.status ?? "not configured").replaceAll("_", " ")}`
                    : "No verified catalog selected."}
              </p>
              {catalog && state.image_failures > 0 && (
                <details className={styles.warning}>
                  <summary>
                  {state.image_failures} images could not be loaded. Products
                  remain available without them.
                  </summary>
                  <ul>
                    {state.image_issues?.map((issue) => (
                      <li key={issue.product_id}>
                        <strong>{issue.title}</strong> ({issue.product_id}): {issue.next_action}
                      </li>
                    ))}
                  </ul>
                  {state.image_issues_truncated && <p>Showing the first 100 affected products.</p>}
                </details>
              )}
              <div className={styles.actions}>
                <button
                  className={styles.primary}
                  disabled={busy || !candidateAvailable || !verified}
                  onClick={() => void action(preview)}
                >
                  Open shopper preview <ExternalLink size={17} />
                </button>
                {catalog && review && state.indexing.status === "failed" && review.indexing?.status === "failed" && (
                  <button
                    disabled={busy || !candidateAvailable}
                    onClick={() =>
                      void action(async () => {
                        if (!candidateAvailable) return;
                        await storeRequest(
                          `/v1/merchant/imports/${review.id}/retry`,
                          "POST",
                        );
                        await refresh();
                      })
                    }
                  >
                    Retry indexing
                  </button>
                )}
              </div>
              <button
                onClick={() => {
                  setStage(2);
                  void action(refresh);
                }}
              >
                Review sharing <ArrowRight size={16} />
              </button>
            </section>
          )}
          {stage === 2 && (
            <section>
              <h1>{publishedCurrent ? "Your store link is enabled" : state.store.sharing_enabled ? "Review your catalog update" : "Ready to share"}</h1>
              {state.store.sharing_enabled && !publishedCurrent && <p>
                Shoppers still see the previously published catalog. Review and publish this update when it is ready.
              </p>}
              {!state.checklist.search_tested && (
                <div className={styles.warning}>
                  <p>Test a search in the shopper preview before enabling your store link.</p>
                  <button disabled={busy || !candidateAvailable || !verified}
                    onClick={() => void action(preview)}>
                    Test shopper search <ExternalLink size={16} />
                  </button>
                </div>
              )}
              <ul className={styles.checklist}>
                {Object.entries(state.checklist).map(([key, value]) => {
                  const ready = ["catalog_verified", "images_reviewed", "search_tested"].includes(key)
                    ? candidateAvailable && value : value;
                  return (
                  <li key={key}>
                    {ready ? <Check size={18} /> : <Circle size={18} />}
                    <span>{readinessNames[key] ?? key}</span>
                    <small>{ready ? "Verified" : "Not yet"}</small>
                  </li>
                  );
                })}
              </ul>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  disabled={busy || !candidateAvailable || !verified}
                  checked={images}
                  onChange={(e) => setImages(e.target.checked)}
                />
                I reviewed the products and image issues.
              </label>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  disabled={busy || !candidateAvailable || !verified}
                  checked={demo}
                  onChange={(e) => setDemo(e.target.checked)}
                />
                Checkout is a demo. No real payments are taken.
              </label>
              <div className={styles.actions}>
                <button
                  className={styles.primary}
                  disabled={
                    busy ||
                    !candidateAvailable ||
                    !verified ||
                    publishedCurrent ||
                    !images ||
                    !demo ||
                    !state.checklist.search_tested ||
                    !catalog
                  }
                  onClick={() =>
                    void action(async () => {
                      if (!candidateAvailable || !verified || !catalog || !images || !demo ||
                        !state.checklist.search_tested || publishedCurrent) return;
                      await storeRequest("/v1/merchant/store/sharing", "POST", {
                        catalog_id: catalog,
                        enabled: true,
                        acknowledge_demo_checkout: demo,
                        acknowledge_image_issues: images,
                      });
                      await refresh();
                    })
                  }
                >
                  {publishedCurrent ? "Store link enabled" : state.store.sharing_enabled ? "Publish catalog update" : "Enable store link"} <ArrowRight size={16} />
                </button>
                {state.store.sharing_enabled && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await storeRequest(
                          "/v1/merchant/store/sharing",
                          "POST",
                          {
                            catalog_id: state.store.published_catalog_id,
                            enabled: false,
                          },
                        );
                        await refresh();
                      })
                    }
                  >
                    Disable sharing
                  </button>
                )}
              </div>
              {state.store.sharing_enabled && (
                <a
                  href={`/manager/preview?store=${state.store.slug}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open shared store <ExternalLink size={16} />
                </a>
              )}
            </section>
          )}
          {stage === 2 && (
            <section>
              <h2>Store activity</h2>
              {metricsError && (
                <div role="alert">
                  <p>Store activity is unavailable. Your product setup is unaffected.</p>
                  <button onClick={() => void refreshMetrics()}>
                    Retry activity <RefreshCw size={16} />
                  </button>
                </div>
              )}
              <p>
                Last 24 hours. Owner previews and sample-data sessions are
                excluded.
              </p>
              {metrics && (
                <dl className={styles.measurements}>
                  <div>
                    <dt>Searches completed</dt>
                    <dd>{metrics.successful_searches}</dd>
                  </div>
                  <div>
                    <dt>Products selected</dt>
                    <dd>{metrics.product_selections}</dd>
                  </div>
                  <div>
                    <dt>Shoppers selecting after search</dt>
                    <dd>{metrics.searchers_with_selection ?? 0} / {metrics.searching_accounts ?? 0}</dd>
                  </div>
                  <div>
                    <dt>Cart additions</dt>
                    <dd>{metrics.cart_additions}</dd>
                  </div>
                  <div>
                    <dt>Demo checkouts</dt>
                    <dd>{metrics.demo_checkouts}</dd>
                  </div>
                </dl>
              )}
              <h2>Monitoring</h2>
              <p>Checks every five minutes. Notices stay in this app.</p>
              {Object.entries(monitoringPresets).map(([name, label]) => (
                <div key={name}>
                  <label className={styles.checkbox}>
                    <input
                      type="checkbox"
                      disabled={busy}
                      checked={
                        state.store.readiness?.[`monitor_${name}`] === true
                      }
                      onChange={(e) => {
                        const enabled = e.target.checked;
                        void action(async () => {
                          await storeRequest(
                            "/v1/merchant/store/monitors",
                            "PUT",
                            { name, enabled },
                          );
                          await refresh();
                        });
                      }}
                    />
                    {label}
                  </label>
                  {state.store.readiness?.[`monitor_${name}`] === true && (
                    <p>
                      {String(
                        state.store.readiness?.[`alert_${name}`] ??
                          "Waiting for first check.",
                      )}
                    </p>
                  )}
                </div>
              ))}
              <button onClick={() => void action(async () => {
                await Promise.all([refresh(), refreshMetrics()]);
              })} disabled={busy}>
                <RefreshCw size={16} /> Refresh activity
              </button>
            </section>
          )}
          <footer className={styles.footer}>
            <button disabled={stage === 0} onClick={() => setStage(stage - 1)}>
              <ArrowLeft size={16} />
              Back
            </button>
            <button onClick={onWorkspace}>
              Ask your store agent <ArrowRight size={16} />
            </button>
          </footer>
        </div>
      )}
    </main>
  );
}
