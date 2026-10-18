"use client";

import type { OrderSummary, ShopperOrderList } from "@open-commerce/sdk-typescript";
import { RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useShopperSessionError } from "@/lib/session-errors";

export function OrderHistory({ client, guest, onClose }: {
  client: { shopperOrders: (query: { limit: number; offset: number }) => Promise<ShopperOrderList> };
  guest: boolean;
  onClose: () => void;
}) {
  const handleSessionError = useShopperSessionError();
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const trigger = document.activeElement;
    closeButton.current?.focus();
    return () => { if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus(); };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    void client.shopperOrders({ limit: 20, offset }).then((page) => {
      if (!active) return;
      setOrders((previous) => offset === 0 ? page.items : [
        ...previous,
        ...page.items.filter((order) => !previous.some((item) => item.id === order.id)),
      ]);
      setNext(page.next_offset ?? null);
    }).catch((cause) => {
      if (!active) return;
      if (handleSessionError(cause)) {
        active = false;
        return;
      }
      setError(true);
    })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [client, offset, attempt, handleSessionError]);

  return <aside className="memory-drawer order-history" aria-label="Demo orders" onKeyDown={(event) => {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }}>
    <header>
      <strong>Demo orders</strong>
      <button ref={closeButton} aria-label="Close orders" title="Close orders" onClick={onClose}><X size={18} /></button>
    </header>
    <div className="order-history-body">
      <p>No money charged. These are test checkouts, not purchases or shipments.</p>
      {guest && <p>Available for this guest visit only. Create an account to keep these orders; signing into a different account does not transfer them.</p>}
      {orders.map((order) => <details className="order-history-item" key={order.id}>
        <summary>
          <strong>{order.order_number}</strong>
          <span>{order.total.currency} {(order.total.amount_minor / 100).toFixed(2)}</span>
          <time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString()}</time>
          <span>{order.status === "cancelled" ? "Demo cancelled" : "Demo completed"}</span>
        </summary>
        <ul>{order.lines.map((line) => <li key={`${line.product_id}:${line.variant_id}`}>
          <strong>{line.title}</strong> &times; {line.quantity}
          <small>Variant: {line.variant_id}</small>
          <span>{line.line_total.currency} {(line.line_total.amount_minor / 100).toFixed(2)}</span>
        </li>)}</ul>
      </details>)}
      {loading && <p role="status">Loading demo orders...</p>}
      {!loading && !error && orders.length === 0 && <p>No demo orders yet.</p>}
      {error && <div role="alert">
        <p>Could not load demo orders. Your order records have not changed.</p>
        <button disabled={loading} onClick={() => setAttempt((value) => value + 1)}><RefreshCw size={16} /> Retry orders</button>
      </div>}
      {next !== null && !error && <button disabled={loading} onClick={() => setOffset(next)}>Show older orders</button>}
    </div>
  </aside>;
}
