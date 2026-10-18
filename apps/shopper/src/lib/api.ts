import {
  OpenCommerceApiError,
  OpenCommerceClient,
} from "@open-commerce/sdk-typescript";

export type ShopperRequest = <T>(
  path: string,
  method?: string,
  body?: unknown,
  idempotencyKey?: string,
) => Promise<T>;

export type ShopperTransport = {
  client: OpenCommerceClient;
  request: ShopperRequest;
  /** Immutable view ownership; null is reserved for discovery or explicit recovery. */
  forAccount: (accountId: string | null) => ShopperTransport;
};

type TransportOptions = {
  slug?: string | null;
  isActive?: () => boolean;
  onUnavailable?: (error: OpenCommerceApiError) => void;
};

function apiError(status: number, data: unknown): OpenCommerceApiError {
  const detail = data && typeof data === "object" && "error" in data ? data.error : null;
  const error = detail && typeof detail === "object" ? detail : {};
  return new OpenCommerceApiError(status, {
    message: "message" in error && typeof error.message === "string" ? error.message : "The store is unavailable. Please retry.",
    code: "code" in error && typeof error.code === "string" ? error.code : "request_failed",
    request_id: "request_id" in error && typeof error.request_id === "string" ? error.request_id : "",
  });
}

/** Capture request ownership once; a later URL change cannot retarget this transport. */
export function createShopperTransport(options: TransportOptions = {}): ShopperTransport {
  const origin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const slug = options.slug === undefined
    ? (typeof window === "undefined" ? null : window.location.pathname.match(/^\/s\/([a-z0-9-]+)(?:\/|$)/)?.[1])
    : options.slug;
  return bindTransport(origin, slug, options, null);
}

function bindTransport(
  origin: string,
  slug: string | null | undefined,
  options: TransportOptions,
  accountId: string | null,
): ShopperTransport {
  const isActive = options.isActive ?? (() => true);
  const fetcher: typeof fetch = async (input, init) => {
    if (!isActive()) throw new DOMException("This store visit is no longer active.", "AbortError");
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    if (slug) headers.set("x-store-slug", slug);
    else headers.delete("x-store-slug");
    if (accountId) headers.set("x-shopper-account-id", accountId);
    else headers.delete("x-shopper-account-id");
    const response = await fetch(input, { ...init, headers, credentials: "include", cache: "no-store" });
    if (response.status === 404 && options.onUnavailable && isActive()) {
      const data: unknown = await response.clone().json().catch(() => null);
      const error = apiError(response.status, data);
      if (error.error?.code === "STORE_UNAVAILABLE" && isActive()) options.onUnavailable(error);
    }
    return response;
  };
  const client = new OpenCommerceClient({
    baseUrl: origin + "/api/runtime",
    credentials: "include",
    fetcher,
  });
  const request: ShopperRequest = async <T>(path: string, method = "GET", body?: unknown, idempotencyKey?: string) => {
    const response = await fetcher(origin + "/api/runtime" + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey ?? crypto.randomUUID(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data: unknown;
    try {
      data = response.status === 204 ? null : await response.json();
    } catch (error) {
      if (!response.ok) throw new OpenCommerceApiError(response.status, null);
      throw error;
    }
    if (!response.ok) throw apiError(response.status, data);
    return data as T;
  };
  const transport: ShopperTransport = {
    client,
    request,
    forAccount: (next) => next === accountId ? transport : bindTransport(origin, slug, options, next),
  };
  return transport;
}

export function createShopperClient(options: TransportOptions = {}): OpenCommerceClient {
  return createShopperTransport(options).client;
}

export function shopperErrorMessage(error: unknown): string {
  if (error instanceof OpenCommerceApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The store assistant could not complete that request.";
}
