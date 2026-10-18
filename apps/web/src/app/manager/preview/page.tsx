import { readFileSync } from "node:fs";
import { PreviewRedirect } from "./redirect";

export const dynamic = "force-dynamic";
export default function PreviewPage() {
  const path = process.env.OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST;
  const manifest = path
    ? (JSON.parse(readFileSync(path, "utf8")) as {
        services?: { shopper_web?: { url?: string } };
      })
    : null;
  const origin = new URL(
    process.env.OPEN_COMMERCE_SHOPPER_PUBLIC_URL ??
      manifest?.services?.shopper_web?.url ??
      "http://127.0.0.1:3001",
  );
  if (
    !["http:", "https:"].includes(origin.protocol) ||
    origin.username ||
    origin.password
  )
    throw new Error("Invalid shopper public URL");
  return <PreviewRedirect origin={origin.origin} />;
}
