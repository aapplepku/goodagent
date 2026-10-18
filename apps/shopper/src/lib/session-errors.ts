"use client";

import { createContext, useContext } from "react";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";

export function isSessionExpired(error: unknown): boolean {
  return error instanceof OpenCommerceApiError && error.status === 401;
}

// Each provider callback is bound to the account epoch that issued the request.
export const ShopperSessionErrors = createContext<(error: unknown) => boolean>(() => false);

export function useShopperSessionError() {
  return useContext(ShopperSessionErrors);
}
