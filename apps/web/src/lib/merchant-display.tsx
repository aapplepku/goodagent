"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { StoreProfile } from "@open-commerce/sdk-typescript";

type StoreIdentity = Pick<StoreProfile, "id" | "name" | "slug">;
type MerchantDisplay = {
  store: StoreIdentity;
  captureRead: () => (store: StoreProfile) => void;
  acceptProfile: (store: StoreProfile) => void;
};

const MerchantDisplayContext = createContext<MerchantDisplay | null>(null);

/** Display updates never replace the session's immutable request binding. */
export function MerchantDisplayProvider({ initialStore, isActive, children }: {
  initialStore: StoreProfile;
  isActive: () => boolean;
  children: ReactNode;
}) {
  const [store, setStore] = useState<StoreIdentity>(() => ({
    id: initialStore.id, name: initialStore.name, slug: initialStore.slug,
  }));
  const mounted = useRef(true);
  const revision = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const updates = useMemo(() => {
    function accept(next: StoreProfile) {
      if (!mounted.current || !isActive() || next.id !== initialStore.id) return;
      setStore((current) => current.name === next.name && current.slug === next.slug
        ? current : { id: next.id, name: next.name, slug: next.slug });
    }
    return {
      captureRead() {
        const read = ++revision.current;
        return (next: StoreProfile) => { if (read === revision.current) accept(next); };
      },
      acceptProfile(next: StoreProfile) {
        // A successful write supersedes reads already in flight, including focus refreshes.
        if (!mounted.current || !isActive() || next.id !== initialStore.id) return;
        revision.current += 1;
        accept(next);
      },
    };
  }, [initialStore.id, isActive]);
  const value = useMemo(() => ({ store, ...updates }), [store, updates]);
  return <MerchantDisplayContext.Provider value={value}>{children}</MerchantDisplayContext.Provider>;
}

export function useMerchantDisplay() {
  return useContext(MerchantDisplayContext);
}
