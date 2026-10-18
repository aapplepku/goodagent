"use client";

import { createContext, useContext } from "react";

// Only authenticated self-service workspaces have owner-controlled setup navigation.
export const StoreNavigationContext = createContext<{
  openProducts: () => void;
  onSessionExpired?: () => void;
} | null>(null);

export function useStoreNavigation() {
  return useContext(StoreNavigationContext);
}
