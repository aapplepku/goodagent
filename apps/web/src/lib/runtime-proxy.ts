import { isLocalRequest } from "./http-security";
import { readFileSync } from "node:fs";

const MAX_BODY = 65536;
const MAX_DATASET_BODY = 1048576;

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
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  ) {
    throw new Error("The demo API must use the configured local service");
  }
  return url.origin;
}

function errorResponse(status: number, message: string): Response {
  const requestId = crypto.randomUUID();
  return Response.json(
    {
      error: {
        type: status === 503 ? "temporarily_unavailable" : "validation_error",
        code: `HTTP_${status}`,
        message,
        request_id: requestId,
        retryable: status === 503,
        details: {},
      },
    },
    {
      status,
      headers: { "x-request-id": requestId, "cache-control": "no-store" },
    },
  );
}

async function boundedBody(
  request: Request,
  limit = MAX_BODY,
): Promise<string | undefined> {
  if (!request.body) return undefined;
  const reader = request.body.getReader();
  let length = 0;
  let timedOut = false;
  const chunks: Uint8Array[] = [];
  const timeout = setTimeout(() => {
    timedOut = true;
    void reader.cancel().catch(() => undefined);
  }, 10000);
  try {
    while (true) {
      const result = await reader.read();
      if (timedOut) throw new Error("Body read timed out");
      if (result.done) break;
      length += result.value.length;
      if (length > limit) throw new Error("Body exceeds limit");
      chunks.push(result.value);
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    return length
      ? new TextDecoder("utf-8", { fatal: true }).decode(bytes)
      : undefined;
  } finally {
    clearTimeout(timeout);
    await reader.cancel().catch(() => undefined);
  }
}

export async function proxyRuntime(
  request: Request,
  segments: string[],
): Promise<Response> {
  if (!isLocalRequest(request))
    return errorResponse(403, "Local demo requests only");
  if (
    !["v1", "health"].includes(segments[0] ?? "") ||
    segments.some(
      (segment) =>
        !/^[a-zA-Z0-9_.-]+$/.test(segment) ||
        segment === "." ||
        segment === "..",
    )
  )
    return errorResponse(404, "Unknown API path");
  const url = new URL(request.url);
  // Local ingested images use the same URLs in both clients. The operator proxy
  // resolves them through owner membership, never through a shopper preview grant.
  if (segments.slice(0, 3).join("/") === "v1/shopper/assets")
    segments = ["v1", "merchant", ...segments.slice(2)];
  if (url.search.length > 4096 || segments.join("/").length > 2048)
    return errorResponse(400, "Request path exceeds limit");
  const contentLength = Number(request.headers.get("content-length") ?? 0);
  const upload = segments.join("/") === "v1/merchant/imports/upload";
  const bodyLimit = upload
    ? 20 * 1024 * 1024
    : segments.at(-2) === "datasets" && segments.at(-1) === "profile"
      ? MAX_DATASET_BODY
      : MAX_BODY;
  if (
    !Number.isInteger(contentLength) ||
    contentLength < 0 ||
    contentLength > bodyLimit
  )
    return errorResponse(413, "Request body exceeds limit");
  let body: string | undefined;
  try {
    body = await boundedBody(request, bodyLimit);
  } catch {
    return errorResponse(413, "Request body exceeds limits or is invalid");
  }
  if (
    body !== undefined &&
    !(
      upload ? ["text/csv", "application/octet-stream"] : ["application/json"]
    ).includes(request.headers.get("content-type")?.split(";")[0] ?? "")
  )
    return errorResponse(415, "Request body must be JSON");
  const headers = new Headers({
    accept: request.headers.get("accept") ?? "application/json",
  });
  for (const key of [
    "content-type",
    "idempotency-key",
    "last-event-id",
    "x-request-id",
    "x-store-slug",
    "x-merchant-owner-id",
    "x-merchant-store-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const shopperRequest = segments[0] === "v1" && segments[1] === "shopper";
  if (!shopperRequest) {
    const allowed = [
      "open_commerce_merchant_session",
      "open_commerce_login_state",
    ];
    const cookies = (request.headers.get("cookie") ?? "")
      .split(";")
      .map((value) => value.trim())
      .filter(
        (value) =>
          allowed.some((name) => value.startsWith(`${name}=`)) &&
          /^[a-zA-Z0-9_=.-]+$/.test(value),
      );
    if (cookies.length) headers.set("cookie", cookies.join("; "));
  }
  if (shopperRequest) {
    const cookie = request.headers.get("cookie") ?? "";
    const token = cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("open_commerce_shopper_session="))
      ?.split("=", 2)[1];
    if (token && /^[A-Za-z0-9_-]{1,200}$/.test(token)) {
      headers.set("cookie", `open_commerce_shopper_session=${token}`);
    }
  }
  try {
    const isAdvance =
      request.method === "POST" &&
      segments.length === 5 &&
      segments[0] === "v1" &&
      segments[1] === "simulator" &&
      segments[2] === "instances" &&
      segments[4] === "advance";
    const isSearch =
      request.method === "POST" && segments.join("/") === "v1/search";
    const response = await fetch(
      `${serverApiUrl()}/${segments.join("/")}${url.search}`,
      {
        method: request.method,
        headers,
        body,
        redirect:
          segments.slice(0, 4).join("/") === "v1/merchant/auth/oidc"
            ? "manual"
            : "error",
        credentials: "omit",
        cache: "no-store",
        // A virtual day includes cold learned-index construction and shopper serving.
        // Cold search builds the same index; ordinary reads keep their short deadline.
        signal: AbortSignal.timeout(
          isAdvance ||
            isSearch ||
            upload ||
            [
              "v1/merchant/store/check-ai",
              "v1/manager/connectors/shopify/import",
              "v1/manager/ranking/preview",
            ].includes(segments.join("/"))
            ? 120000
            : request.method === "POST" &&
                segments.join("/") === "v1/goals/draft"
              ? 100000
              : 15000,
        ),
      },
    );
    const outgoing = new Headers({ "cache-control": "no-store" });
    for (const key of [
      "content-type",
      "x-request-id",
      "retry-after",
      "location",
    ]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    if (
      segments[2] === "auth" &&
      ["merchant", "shopper"].includes(segments[1] ?? "")
    ) {
      for (const cookie of response.headers.getSetCookie())
        if (
          /^open_commerce_(merchant_session|login_state|shopper_session)(_[a-z0-9-]{1,120})?=/.test(
            cookie,
          )
        )
          outgoing.append("set-cookie", cookie);
    }
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return errorResponse(503, "The local API is temporarily unavailable");
  }
}
