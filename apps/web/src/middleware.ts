import { NextRequest, NextResponse } from "next/server";
import {
  contentSecurityPolicy,
  isLocalRequest,
  SECURITY_HEADERS,
} from "./lib/http-security";

export function middleware(request: NextRequest) {
  if (!isLocalRequest(request))
    return new NextResponse("Local demo requests only", { status: 403 });
  const nonce = crypto.randomUUID().replaceAll("-", "");
  const csp = contentSecurityPolicy(
    nonce,
    process.env.NODE_ENV === "development",
  );
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("content-security-policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("content-security-policy", csp);
  response.headers.set("cache-control", "no-store");
  for (const [key, value] of Object.entries(SECURITY_HEADERS))
    response.headers.set(key, value);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
