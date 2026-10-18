import {
  OpenCommerceApiError,
  OpenCommerceClient,
} from "@open-commerce/sdk-typescript";

export type MerchantBinding = { ownerId: string; storeId: string };
export type MerchantRequest = <T>(path: string, method?: string, body?: unknown, key?: string) => Promise<T>;
export type MerchantTransport = {
  client: OpenCommerceClient;
  request: MerchantRequest;
  upload: <T>(path: string, file: Blob, key?: string) => Promise<T>;
};

type MerchantTransportOptions = {
  binding?: MerchantBinding;
  isActive?: () => boolean;
  onSessionExpired?: () => void;
};

/** Capture the verified view's owner/store. These headers are preconditions, not routing. */
export function createMerchantTransport(options: MerchantTransportOptions = {}): MerchantTransport {
  const ownerId = options.binding?.ownerId;
  const storeId = options.binding?.storeId;
  const isActive = options.isActive ?? (() => true);
  const onSessionExpired = options.onSessionExpired;
  function assertActive() {
    if (!isActive()) throw new DOMException("This store view is no longer active.", "AbortError");
  }
  const fetcher: typeof fetch = async (input, init) => {
    assertActive();
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    if (ownerId !== undefined && storeId !== undefined) {
      headers.set("X-Merchant-Owner-Id", ownerId);
      headers.set("X-Merchant-Store-Id", storeId);
    } else {
      headers.delete("X-Merchant-Owner-Id");
      headers.delete("X-Merchant-Store-Id");
    }
    const response = await fetch(input, { ...init, headers, credentials: "include", cache: "no-store" });
    assertActive();
    if (ownerId !== undefined && response.status === 401) onSessionExpired?.();
    return response;
  };
  async function read<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetcher(`/api/runtime${path}`, init);
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    assertActive();
    if (!response.ok) throw new OpenCommerceApiError(response.status, {
      message: data?.error?.message ?? "Request failed. Please retry.",
      code: data?.error?.code ?? "REQUEST_FAILED",
      request_id: data?.error?.request_id ?? "",
    });
    return data as T;
  }
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const sdk = new OpenCommerceClient({ baseUrl: `${origin}/api/runtime`, fetcher, credentials: "include" });
  // Also fence SDK completion after body parsing, before a caller can start follow-up work.
  const methods = new Map<PropertyKey, unknown>();
  const client = new Proxy(sdk, {
    get(target, property) {
      const value: unknown = Reflect.get(target, property);
      if (typeof value !== "function") return value;
      if (!methods.has(property)) methods.set(property, async (...args: unknown[]) => {
        assertActive();
        const result: unknown = await Reflect.apply(value, target, args);
        assertActive();
        return result;
      });
      return methods.get(property);
    },
  });
  return {
    client,
    request: <T>(path: string, method = "GET", body?: unknown, key = crypto.randomUUID()) => read<T>(path, {
      method,
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
    upload: <T>(path: string, file: Blob, key = crypto.randomUUID()) => read<T>(path, {
      method: "POST", body: file, headers: { "Content-Type": "text/csv", "Idempotency-Key": key },
    }),
  };
}

export function createBrowserClient(): OpenCommerceClient {
  return createMerchantTransport().client;
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof OpenCommerceApiError) {
    const requestId = error.error?.request_id
      ? ` Request ${error.error.request_id}.`
      : "";
    return `${error.message}.${requestId}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The local API could not complete the request.";
}
