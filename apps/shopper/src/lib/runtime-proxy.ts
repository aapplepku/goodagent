import { isLocalRequest } from "./http-security";
import { readFileSync } from "node:fs";

const MAX_BODY = 65536;

export function serverApiUrl(): string {
  const manifestPath = process.env.OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST;
  const manifest: unknown = manifestPath
    ? JSON.parse(readFileSync(manifestPath, "utf8"))
    : null;
  const manifestUrl =
    manifest && typeof manifest === "object" && "services" in manifest
      ? (manifest as { services?: { api?: { url?: unknown } } }).services?.api
          ?.url
      : undefined;
  if (manifestPath && typeof manifestUrl !== "string")
    throw new Error("Local runtime manifest is invalid");
  const url = new URL(
    typeof manifestUrl === "string"
      ? manifestUrl
      : (process.env.OPEN_COMMERCE_API_BASE_URL ?? "http://127.0.0.1:8000"),
  );
  if (
    url.protocol !== "http:" ||
    !["api", "localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error("The shopper API must use the configured local service");
  return url.origin;
}

function errorResponse(status: number, message: string): Response {
  return Response.json(
    {
      error: {
        type: status === 503 ? "temporarily_unavailable" : "validation_error",
        code: `HTTP_${status}`,
        message,
        request_id: crypto.randomUUID(),
        retryable: status === 503,
        details: {},
      },
    },
    { status, headers: { "cache-control": "no-store" } },
  );
}

export async function proxyRuntime(request: Request, segments: string[]) {
  if (!isLocalRequest(request))
    return errorResponse(403, "Local requests only");
  if (
    segments[0] !== "v1" ||
    !["shopper", "stores"].includes(segments[1] ?? "") ||
    segments.some((segment) => !/^[a-zA-Z0-9_.-]+$/.test(segment))
  )
    return errorResponse(404, "Unknown shopper API path");
  const length = Number(request.headers.get("content-length") ?? 0);
  if (!Number.isInteger(length) || length < 0 || length > MAX_BODY)
    return errorResponse(413, "Request body exceeds the limit");
  let body: string | undefined;
  try {
    if (request.body) {
      const reader = request.body.getReader();
      const decoder = new TextDecoder("utf-8", { fatal: true });
      let bytes = 0;
      body = "";
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          bytes += value.byteLength;
          if (bytes > MAX_BODY) {
            await reader.cancel();
            return errorResponse(413, "Request body exceeds the limit");
          }
          body += decoder.decode(value, { stream: true });
        }
        body += decoder.decode();
      } finally {
        reader.releaseLock();
      }
    }
  } catch {
    return errorResponse(400, "Request body is invalid");
  }
  if (body && new TextEncoder().encode(body).length > MAX_BODY)
    return errorResponse(413, "Request body exceeds the limit");

  const headers = new Headers({ accept: "application/json" });
  for (const key of [
    "content-type",
    "idempotency-key",
    "x-request-id",
    "x-store-slug",
    "x-shopper-account-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const cookies = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((item) => item.trim())
    .filter((item) =>
      /^(open_commerce_shopper_session|open_commerce_preview)(_[a-z0-9-]{1,120})?=[A-Za-z0-9_-]{1,200}$/.test(
        item,
      ),
    );
  if (cookies.length) headers.set("cookie", cookies.join("; "));
  const store = new URL(request.url).searchParams.get("store");
  if (store && /^[a-z0-9-]{1,120}$/.test(store))
    headers.set("x-store-slug", store);

  try {
    const response = await fetch(
      `${serverApiUrl()}/${segments.join("/")}${new URL(request.url).search}`,
      {
        method: request.method,
        headers,
        body,
        redirect: "error",
        cache: "no-store",
        signal: AbortSignal.timeout(100000),
      },
    );
    const outgoing = new Headers({ "cache-control": "no-store" });
    for (const key of ["content-type", "x-request-id"]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    for (const cookie of response.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return errorResponse(503, "The store assistant is temporarily unavailable");
  }
}
