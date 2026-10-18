"use client";

import type { CatalogConnection } from "@open-commerce/sdk-typescript";
import { Download, Plug, X } from "lucide-react";
import { useRef, useState } from "react";
import { apiErrorMessage } from "../lib/api";
import { useMerchantClient } from "@/lib/merchant-transport";
import styles from "./ranking-panel.module.css";

export function ShopifyPanel() {
  const client = useMerchantClient();
  const [connection, setConnection] = useState<CatalogConnection | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const key = useRef<string | null>(null);
  async function check() {
    setBusy(true); setNotice(null);
    try { setConnection(await client.checkShopify()); }
    catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(false); }
  }
  async function load() {
    setBusy(true); setNotice(null);
    key.current ??= `shopify-${crypto.randomUUID()}`;
    try {
      const result = await client.importShopify(key.current);
      setNotice(`${result.product_count} products staged. Index status: ${result.status}. The previous catalog stays available until verification.`);
      setConfirm(false); key.current = null;
    } catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(false); }
  }
  return <section className={styles.panel} aria-label="Shopify catalog connection">
    <h3>Shopify</h3><p>Read-only catalog import · Test store</p>
    <button type="button" disabled={busy} onClick={() => void check()}><Plug size={16} /> Check connection</button>
    {connection && <p>{connection.detail}</p>}
    {connection?.connected && <button type="button" disabled={busy} onClick={() => setConfirm(true)}><Download size={16} /> Import catalog</button>}
    {confirm && <div className={styles.review}><strong>Replace the local catalog after indexing?</strong><p>Products and prices come from {connection?.shop}. Stock is not synchronized. Nothing changes in Shopify.</p><div className={styles.actions}><button type="button" disabled={busy} onClick={() => void load()}><Download size={16} /> Confirm import</button><button type="button" disabled={busy} onClick={() => setConfirm(false)}><X size={16} /> Cancel</button></div></div>}
    {busy && <p role="status">Checking Shopify…</p>}
    {notice && <p role="status">{notice}</p>}
  </section>;
}
