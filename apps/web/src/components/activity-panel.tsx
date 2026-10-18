"use client";

import type { ActivityOverview, ActivityQuery, ActivityRule } from "@open-commerce/sdk-typescript";
import { Activity, Pause, Play, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createBrowserClient } from "@/lib/api";
import { useMerchantClient } from "@/lib/merchant-transport";
import styles from "./activity-panel.module.css";

type ActivityClient = Pick<ReturnType<typeof createBrowserClient>, "managerActivity" | "configureManagerActivity">;

function checkState(rule: ActivityRule) {
  return rule.definition.enabled && rule.next_check_at && Date.now() > Date.parse(rule.next_check_at) + 60000
    ? "check_overdue" : rule.check.state;
}

export function ActivityPanel({ client: suppliedClient }: { client?: ActivityClient }) {
  const defaultClient = useMerchantClient();
  const client = suppliedClient ?? defaultClient;
  const [data, setData] = useState<ActivityOverview | null>(null);
  const [query, setQuery] = useState<ActivityQuery>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const result = await client.managerActivity(query);
      setData(result);
      setError(null);
    } catch { setError("Activity is unavailable. Retrying shortly."); }
  }, [client, query]);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  async function toggle(rule: ActivityRule) {
    setBusy(true);
    try {
      await client.configureManagerActivity(
        { ...rule.definition, enabled: !rule.definition.enabled }, crypto.randomUUID());
      await refresh();
    } catch { setError("The monitor could not be updated."); }
    finally { setBusy(false); }
  }
  return <section className={styles.panel} aria-label="Store activity">
    <div className={styles.toolbar}>
      <Activity size={17} /><h3>Shopper logs & monitors</h3>
      <button type="button" aria-label="Refresh activity" title="Refresh activity" onClick={() => void refresh()}><RefreshCw size={16} /></button>
    </div>
    {error && <p role="alert">{error}</p>}
    {!data ? <p role="status">Loading activity...</p> : <>
      <div className={styles.toolbar}>
        <select aria-label="Activity type" value={query.kind ?? ""} onChange={(event) => setQuery({ kind: event.target.value as ActivityQuery["kind"] || null })}>
          <option value="">All events</option>
          {(data.available_kinds ?? []).map((kind) => <option key={kind} value={kind}>{kind.replaceAll("_", " ")} ({data.observed_counts[kind] ?? 0})</option>)}
        </select>
        <select aria-label="Activity time window" value={query.window_minutes ?? 1440} onChange={(event) => setQuery({ ...query, window_minutes: Number(event.target.value) })}>
          <option value={60}>Past hour</option><option value={1440}>Past day</option><option value={10080}>Past week</option><option value={43200}>Past 30 days</option>
        </select>
      </div>
      <p className={styles.note}>Updated {new Date(data.checked_at).toLocaleTimeString()} · Store-wide, redacted</p>
      {(query.status || query.empty_results_only) && <p className={styles.note}>
        {query.status ? "Outcome: " + query.status + ". " : ""}{query.empty_results_only ? "Zero-result events only." : ""}
      </p>}
      <details><summary>Available data</summary><p className={styles.note}>{data.available_fields?.join(", ")}</p><p className={styles.note}>{data.limitation}</p></details>
      <h4>Saved views & monitors</h4>
      {!data.rules.length && <p className={styles.note}>No saved views or monitors.</p>}
      {data.rules.map((rule) => <details className={styles.rule} key={rule.id}>
        <summary><strong>{rule.definition.name}</strong><span data-state={checkState(rule)}>{checkState(rule).replaceAll("_", " ")}</span></summary>
        <p>{rule.definition.metric?.replaceAll("_", " ")}{rule.definition.threshold != null ? " >= " + rule.definition.threshold : " · Log view"}</p>
        <p>{rule.check.value == null ? "No measurement" : "Measured " + rule.check.value} · {rule.check.sample_count} samples</p>
        <p>Window: {rule.definition.query?.window_minutes ?? 1440} min · Interval: {rule.definition.interval_minutes ?? 5} min · Minimum: {rule.definition.minimum_samples ?? 5} samples</p>
        <p>Checked {new Date(rule.check.checked_at).toLocaleString()}{rule.next_check_at ? " · Next " + new Date(rule.next_check_at).toLocaleTimeString() : ""}</p>
        <div className={styles.actions}><button type="button" onClick={() => setQuery(rule.definition.query ?? {})}>View events</button>
          <button type="button" disabled={busy} aria-label={(rule.definition.enabled ? "Pause " : "Resume ") + rule.definition.name} title={rule.definition.enabled ? "Pause monitor" : "Resume monitor"} onClick={() => void toggle(rule)}>{rule.definition.enabled ? <Pause size={14} /> : <Play size={14} />}</button></div>
      </details>)}
      <h4>Recent events</h4>
      {!data.events.length && <p className={styles.note}>No events in this window.</p>}
      {data.events.map((event) => <div className={styles.event} key={event.id}>
        <strong>{event.kind.replaceAll("_", " ")}</strong><span data-state={event.status}>{event.status}</span>
        <time>{new Date(event.occurred_at).toLocaleTimeString()}</time><span>{event.duration_ms} ms{event.result_count != null ? " · " + event.result_count + " results" : ""}</span>
      </div>)}
      <p className={styles.note}>Latest {data.event_limit} events · {data.retention_days}-day retention</p>
    </>}
  </section>;
}
