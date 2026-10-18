"use client";

import { createContext, useContext, useMemo } from "react";
import { createBrowserClient, type MerchantTransport } from "./api";

export const MerchantTransportContext = createContext<MerchantTransport | null>(null);

/** Authenticated descendants share their StoreAccess generation; standalone legacy views stay unbound. */
export function useMerchantClient() {
  const transport = useContext(MerchantTransportContext);
  const fallback = useMemo(() => createBrowserClient(), []);
  return transport?.client ?? fallback;
}

export function useMerchantTransport(): MerchantTransport {
  const transport = useContext(MerchantTransportContext);
  if (!transport) throw new Error("Merchant requests require StoreAccess.");
  return transport;
}
