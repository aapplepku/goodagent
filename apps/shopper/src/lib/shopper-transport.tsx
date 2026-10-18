"use client";

import { createContext, useContext, useMemo } from "react";
import { createShopperTransport, type ShopperTransport } from "./api";

export const ShopperTransportContext = createContext<ShopperTransport | null>(null);

/** Store entries own the transport; standalone legacy views capture their scope on mount. */
export function useShopperTransport(slug?: string): ShopperTransport {
  const supplied = useContext(ShopperTransportContext);
  const fallback = useMemo(() => createShopperTransport({ slug }), [slug]);
  return supplied ?? fallback;
}
