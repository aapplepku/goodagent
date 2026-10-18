export type CheckoutAttempt = {
  checkoutId: string;
  cartVersion: number;
  expiresAt: string;
  key: string;
  method: "test_success" | "test_decline";
};

export function loadAttempt(scope: string): CheckoutAttempt | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(`checkout:${scope}`) ?? "null");
    if (!value || typeof value !== "object") return null;
    const item = value as Record<string, unknown>;
    if (typeof item.checkoutId !== "string" || !/^[a-f0-9-]{36}$/i.test(item.checkoutId) ||
      typeof item.key !== "string" || !/^[a-f0-9-]{36}$/i.test(item.key) ||
      !Number.isInteger(item.cartVersion) || Number(item.cartVersion) < 1 ||
      typeof item.expiresAt !== "string" || !Number.isFinite(Date.parse(item.expiresAt)) ||
      !["test_success", "test_decline"].includes(String(item.method))) return null;
    return item as CheckoutAttempt;
  } catch { return null; }
}

export function saveAttempt(scope: string, attempt: CheckoutAttempt | null): void {
  try {
    if (attempt) sessionStorage.setItem(`checkout:${scope}`, JSON.stringify(attempt));
    else sessionStorage.removeItem(`checkout:${scope}`);
  } catch { /* Status is recoverable from the server when tab storage is unavailable. */ }
}
