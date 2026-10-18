"use client";

import { useMerchantDisplay } from "@/lib/merchant-display";
import styles from "./merchant-store-identity.module.css";

export function MerchantStoreIdentity({ compact = false }: { compact?: boolean }) {
  const display = useMerchantDisplay();
  if (!display) return null;
  const { name, slug } = display.store;
  return <div className={compact ? styles.compact : styles.identity}
    role="group" aria-label={compact ? "Current store" : "Store target"}>
    <strong title={name}>{name}</strong>
    <span title={`/s/${slug}`}>/s/{slug}</span>
  </div>;
}
