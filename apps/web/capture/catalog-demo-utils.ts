import { lstatSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import type { Route } from "@playwright/test";

function privateCapturePath(root: string, output: string): string {
  const base = path.resolve(root, ".opencommerce");
  const destination = path.resolve(output);
  if (!output || !destination.startsWith(base + path.sep)) {
    throw new Error("Capture must remain under ignored .opencommerce");
  }
  let current = path.dirname(destination);
  while (true) {
    const info = lstatSync(current);
    if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("Unsafe capture parent");
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return destination;
}

export function newPrivateCapturePath(root: string, output: string): string {
  const destination = privateCapturePath(root, output);
  try {
    lstatSync(destination);
    throw new Error("Capture output already exists");
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
  }
  return destination;
}

export function captureScratchPath(root: string, output: string, worker: {
  connected: boolean; canSend: boolean; index: string | undefined;
}): string {
  // Playwright creates its scratch directory before reloading config in an IPC worker.
  // A standalone CLI invocation, including one with a stale worker-index variable,
  // must still reject an existing output before Playwright can clear it.
  if (!worker.connected || !worker.canSend || !/^\d+$/.test(worker.index ?? "")) {
    return newPrivateCapturePath(root, output);
  }
  const destination = privateCapturePath(root, output);
  try {
    const info = lstatSync(destination);
    if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("Unsafe capture scratch directory");
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
  }
  return destination;
}

export async function createPrivateCapture(root: string, output: string): Promise<string> {
  const destination = newPrivateCapturePath(root, output);
  await mkdir(destination, { mode: 0o700 });
  return destination;
}

export function allowedDemoRequest(url: string, origins: readonly string[]): boolean {
  try {
    const parsed = new URL(url);
    return origins.includes(parsed.origin) && !parsed.username && !parsed.password &&
      !/^\/api\/runtime\/v1\/(?:manager(?:\/|$)|merchant\/store\/check-ai(?:\/|$))/.test(decodeURIComponent(parsed.pathname));
  } catch { return false; }
}

export async function guardDemoRoute(route: Route, origins: readonly string[], denied: () => void): Promise<void> {
  try {
    if (!allowedDemoRequest(route.request().url(), origins)) {
      denied();
      await route.abort("blockedbyclient");
      return;
    }
    // Redirected browser requests can bypass Playwright's next route interception.
    // Fetch exactly one response and never let the browser follow a redirect.
    const response = await route.fetch({ maxRedirects: 0 });
    try {
      if (response.status() >= 300 && response.status() < 400) {
        denied();
        await route.abort("blockedbyclient");
      } else await route.fulfill({ response });
    } finally { await response.dispose(); }
  } catch {
    denied();
    try { await route.abort("failed"); } catch { /* The page may already be closing. */ }
  }
}

export function acceptedMilestone(value: unknown, stage: string): boolean {
  if (value === null) return false;
  if (!value || typeof value !== "object" || !("passed" in value) || !("stage" in value) ||
      value.stage !== stage || Object.keys(value).length !== 2 || typeof value.passed !== "boolean") {
    throw new Error("Invalid runtime acknowledgement");
  }
  if (!value.passed) throw new Error("Runtime audit rejected this take");
  return true;
}
