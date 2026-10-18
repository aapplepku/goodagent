"use client";

import type { RankingModel, RankingOverview, RankingPreview, TrainRankingInput } from "@open-commerce/sdk-typescript";
import { Check, FlaskConical, LoaderCircle, Power, RefreshCw, Search, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, createBrowserClient } from "../lib/api";
import { useMerchantClient } from "@/lib/merchant-transport";
import styles from "./ranking-panel.module.css";

type Client = Pick<ReturnType<typeof createBrowserClient>, "rankingOverview" | "trainRanking" | "approveRanking" | "previewRanking">;

export function RankingPanel({ client: supplied }: { client?: Client }) {
  const fallback = useMerchantClient();
  const client = supplied ?? fallback;
  const [overview, setOverview] = useState<RankingOverview | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [goal, setGoal] = useState("Increase purchases from search");
  const [method, setMethod] = useState<TrainRankingInput["method"]>("logistic_regression");
  const [target, setTarget] = useState<TrainRankingInput["target"]>("purchase");
  const [review, setReview] = useState<RankingModel | "disable" | null>(null);
  const reviewActiveId = useRef<string | null>(null);
  const [query, setQuery] = useState("");
  const [comparison, setComparison] = useState<RankingPreview | null>(null);
  const keys = useRef(new Map<string, string>());
  const active = overview?.models.find((model) => model.active);
  const refresh = useCallback(async () => {
    try { setOverview(await client.rankingOverview()); }
    catch (error) { setNotice(apiErrorMessage(error)); }
  }, [client]);
  function startReview(model: RankingModel | "disable") {
    reviewActiveId.current = active?.id ?? null;
    setReview(model);
  }
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 3000); return () => window.clearInterval(timer); }, [refresh]);

  function key(command: unknown) {
    const identity = JSON.stringify(command);
    let value = keys.current.get(identity);
    if (!value) { value = `ranking-${crypto.randomUUID()}`; keys.current.set(identity, value); }
    return value;
  }
  async function build() {
    const body = { goal, target, method };
    setBusy(true); setNotice(null);
    try { await client.trainRanking(body, key(body)); keys.current.delete(JSON.stringify(body)); await refresh(); }
    catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(false); }
  }
  async function approve() {
    if (!review) return;
    const model = review === "disable" ? null : review;
    const body = { model_id: model?.id ?? null, artifact_hash: model?.artifact_hash ?? null,
      expected_active_id: reviewActiveId.current,
      confirm: model ? "APPLY_LOCAL_RANKING" as const : "DISABLE_LOCAL_RANKING" as const };
    setBusy(true); setNotice(null);
    try { setOverview(await client.approveRanking(body, key(body))); setReview(null); }
    catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(false); }
  }
  async function preview(model: RankingModel) {
    setBusy(true); setNotice(null);
    try { setComparison(await client.previewRanking({ model_id: model.id, query })); }
    catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(false); }
  }
  return <section className={styles.panel} aria-label="Search ranking models">
    <header><h3>Search ranking</h3><button type="button" title="Refresh models" aria-label="Refresh models" onClick={() => void refresh()}><RefreshCw size={16} /></button></header>
    <p>{active && active.catalog_id === overview?.catalog_id ? `Active: ${active.method.replaceAll("_", " ")} / ${active.target.replaceAll("_", " ")}` : "Baseline search active"}</p>
    {overview?.dataset ? <p>{overview.dataset.event_count} events · {overview.dataset.product_count} products</p> : <p>No retained engagement. Upload an engagement CSV in Data.</p>}
    {overview?.dataset && <details><summary>Available signals</summary><dl>{Object.entries(overview.dataset.event_counts).map(([kind, count]) => <div key={kind}><dt>{kind.replaceAll("_", " ")}</dt><dd>{count}</dd></div>)}</dl></details>}
    <form onSubmit={(event) => { event.preventDefault(); void build(); }}>
      <label>Merchant goal<input value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={500} required /></label>
      <div className={styles.fields}>
        <label>Target<select value={target} onChange={(event) => setTarget(event.target.value as TrainRankingInput["target"])}><option value="purchase">Purchases</option><option value="add_to_cart">Cart additions</option><option value="click">Clicks</option><option value="product_view">Product views</option></select></label>
        <label>Model<select value={method} onChange={(event) => setMethod(event.target.value as TrainRankingInput["method"])}><option value="logistic_regression">Logistic regression</option><option value="popularity">Popularity</option></select></label>
      </div>
      <button type="submit" disabled={busy || !overview?.dataset || !overview.catalog_id || overview.models.some((model) => ["queued", "running"].includes(model.status))}><FlaskConical size={16} /> Build candidate</button>
    </form>
    <label>Preview query<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. coffee" maxLength={200} /></label>
    {notice && <p role="alert">{notice}</p>}
    {overview?.models.map((model) => <article className={styles.model} key={model.id}>
      <header><strong>{model.method.replaceAll("_", " ")}</strong><span>{model.active && model.catalog_id === overview.catalog_id ? "Active" : model.status === "ready" ? "Evaluated candidate" : model.status}</span></header>
      <p>{model.goal}</p>
      <small>{model.id.slice(0, 8)} · {new Date(model.created_at).toLocaleString()}</small>
      {model.error && <p role="status">{model.error}</p>}
      {model.status === "ready" && <>
        <p>{model.metrics.eligible_for_activation ? "Passed the offline baseline gate. Not evidence of sales lift." : "Below the offline baseline. Activation blocked."}</p>
        <details><summary>Evaluation and fingerprint</summary><dl>{Object.entries(model.metrics).map(([name, value]) => <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{typeof value === "number" ? Number(value.toFixed(4)) : String(value)}</dd></div>)}</dl><code>{model.artifact_hash}</code></details>
        <div className={styles.actions}><button type="button" disabled={busy || !query.trim() || model.catalog_id !== overview.catalog_id} onClick={() => void preview(model)}><Search size={16} /> Preview</button><button type="button" disabled={busy || model.active || !model.metrics.eligible_for_activation || model.catalog_id !== overview.catalog_id} onClick={() => startReview(model)}><Check size={16} /> Review & apply</button></div>
      </>}
      {["queued", "running"].includes(model.status) && <p role="status"><LoaderCircle size={14} /> Building in the background</p>}
    </article>)}
    {comparison && <section aria-label="Ranking comparison"><h4>Search comparison</h4><div className={styles.comparison}>{(["baseline", "candidate"] as const).map((side) => <div key={side}><strong>{side === "baseline" ? "Baseline" : "Candidate"}</strong><ol>{comparison[side].results.map((item) => <li key={item.product_id}>{item.title}</li>)}</ol></div>)}</div></section>}
    {active && <button type="button" disabled={busy} onClick={() => startReview("disable")}><Power size={16} /> Restore baseline</button>}
    {review && <div className={styles.review} role="group" aria-label="Confirm ranking change"><strong>{review === "disable" ? "Restore baseline search?" : "Apply this exact model to local shopper search?"}</strong><p>{review === "disable" ? "The trained artifact will be retained." : `${review.id.slice(0, 8)} · ${review.target.replaceAll("_", " ")}. Only this catalog is affected. You can restore baseline at any time.`}</p><div className={styles.actions}><button type="button" disabled={busy} onClick={() => void approve()}><Check size={16} /> Confirm</button><button type="button" onClick={() => setReview(null)}><X size={16} /> Cancel</button></div></div>}
  </section>;
}
