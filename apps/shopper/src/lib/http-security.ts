const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function isLocalRequest(request: Request): boolean {
  try {
    const url = new URL(request.url);
    const host = request.headers.get("host") ?? url.host;
    const origin = new URL(`${url.protocol}//${host}`);
    const configured: unknown = JSON.parse(
      process.env.OPEN_COMMERCE_PUBLIC_ORIGINS ?? "[]",
    );
    const publicOrigin = Array.isArray(configured)
      ? (configured.find(
          (item: unknown) =>
            typeof item === "string" &&
            new URL(item).host === host.toLowerCase(),
        ) as string | undefined)
      : undefined;
    if (
      (!LOOPBACK.has(origin.hostname) && !publicOrigin) ||
      origin.host !== host.toLowerCase()
    )
      return false;
    const source = request.headers.get("origin");
    return (
      (!source || source === (publicOrigin ?? origin.origin)) &&
      (request.headers.get("sec-fetch-site") !== "cross-site" ||
        (request.method === "GET" && url.pathname.startsWith("/s/")))
    );
  } catch {
    return false;
  }
}

export function contentSecurityPolicy(nonce: string, development: boolean) {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    `style-src-elem 'self' ${development ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    "style-src-attr 'unsafe-inline'",
    `connect-src 'self'${development ? " ws://localhost:* ws://127.0.0.1:*" : ""}`,
    "img-src 'self' data:",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export const SECURITY_HEADERS = {
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "no-referrer",
  "permissions-policy": "camera=(), microphone=(), geolocation=()",
  "x-open-commerce-auth": "local-demo-shopper-account",
};
