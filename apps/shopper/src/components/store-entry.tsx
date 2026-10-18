"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import type { Storefront } from "@open-commerce/sdk-typescript";
import { RefreshCw, Store } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { createShopperTransport, shopperErrorMessage, type ShopperTransport } from "@/lib/api";
import { ShopperTransportContext } from "@/lib/shopper-transport";
import { ShopperApp } from "./shopper-app";

type Initialization = { slug: string; active: boolean; guestReady: boolean };
type ReadyStore = { store: Storefront; transport: ShopperTransport };

function PreviewNavigation({ onNavigate }: { onNavigate: () => void }) {
  // Next updates this context on router hash navigation; native fragment changes emit events.
  const searchParams = useSearchParams();
  useEffect(() => { onNavigate(); }, [searchParams, onNavigate]);
  useEffect(() => {
    window.addEventListener("hashchange", onNavigate);
    window.addEventListener("popstate", onNavigate);
    return () => {
      window.removeEventListener("hashchange", onNavigate);
      window.removeEventListener("popstate", onNavigate);
    };
  }, [onNavigate]);
  return null;
}

export function StoreEntry({ slug }: { slug: string }) {
  const [ready, setReady] = useState<ReadyStore | null>(null);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  const initialization = useRef<Initialization | null>(null);
  const seenPreviews = useRef(new Set<string>());

  const begin = useCallback((token?: string, guestReady = false) => {
    if (initialization.current) initialization.current.active = false;
    const current: Initialization = { slug, active: true, guestReady };
    initialization.current = current;
    const isActive = () => mounted.current && current.active && initialization.current === current;
    const transport = createShopperTransport({
      slug,
      isActive,
      onUnavailable: (cause) => {
        current.active = false;
        setReady(null);
        setError(cause.message);
      },
    });
    setReady(null);
    setError("");
    const initialize = async () => {
      if (token) {
        await transport.request("/v1/stores/" + slug + "/preview", "POST", { token });
        if (!isActive()) return;
      }
      const store = await transport.request<Storefront>("/v1/shopper/store");
      if (!isActive()) return;
      if (!current.guestReady) {
        await transport.request("/v1/shopper/auth/guest", "POST");
        if (!isActive()) return;
        current.guestReady = true;
      }
      setReady({ store, transport });
    };
    void initialize().catch((cause: unknown) => {
      if (isActive()) {
        current.active = false;
        setError(shopperErrorMessage(cause));
      }
    });
  }, [slug]);

  const consumePreview = useCallback(() => {
    if (!mounted.current || window.location.pathname !== "/s/" + slug) return false;
    const token = new URLSearchParams(window.location.hash.slice(1)).get("preview");
    if (!token) return false;
    window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    if (!seenPreviews.current.has(token)) {
      seenPreviews.current.add(token);
      begin(token);
    }
    return true;
  }, [slug, begin]);

  useEffect(() => {
    // The shared generation survives Strict Mode's immediate effect cleanup and replay.
    mounted.current = true;
    if (!initialization.current || initialization.current.slug !== slug) {
      if (!consumePreview()) begin();
    }
    return () => { mounted.current = false; };
  }, [slug, begin, consumePreview]);

  return <>
    <Suspense fallback={null}><PreviewNavigation onNavigate={consumePreview} /></Suspense>
    {ready ? <ShopperTransportContext.Provider value={ready.transport}>
      <ShopperApp store={ready.store} initialView="catalog" />
    </ShopperTransportContext.Provider> : (
      <main className="store-opening" aria-labelledby="store-opening-title">
        <Store className="store-opening-icon" size={32} aria-hidden="true" />
        <h1 id="store-opening-title">{error ? "This store is unavailable" : "Opening the store"}</h1>
        <p role={error ? "alert" : "status"}>
          {error || "Getting your products ready..."}
        </p>
        {error && (
          <button type="button" className="store-retry" onClick={() => begin(undefined, initialization.current?.guestReady)}>
            <RefreshCw size={18} aria-hidden="true" />
            Try again
          </button>
        )}
      </main>
    )}
  </>;
}
