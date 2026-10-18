import { mkdtemp, mkdir, rm, stat, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Route } from "@playwright/test";
import type { Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import CatalogDemoReporter from "../../capture/catalog-demo-reporter";
import { acceptedMilestone, allowedDemoRequest, captureScratchPath, createPrivateCapture, guardDemoRoute, newPrivateCapturePath } from "../../capture/catalog-demo-utils";

const roots: string[] = [];
async function fixture() {
  // /tmp may itself be a symlink on macOS; use the resolved temporary directory.
  const { realpath } = await import("node:fs/promises");
  const root = await mkdtemp(path.join(await realpath(os.tmpdir()), "catalog-demo-"));
  roots.push(root);
  await mkdir(path.join(root, ".opencommerce"));
  return root;
}
afterEach(async () => {
  vi.restoreAllMocks();
  for (const root of roots.splice(0)) await rm(root, { recursive: true });
});

describe("private Basic-mode demo admission", () => {
  it("creates private new-only output and refuses replacement", async () => {
    const root = await fixture();
    const output = path.join(root, ".opencommerce", "take-1");
    expect(await createPrivateCapture(root, output)).toBe(output);
    expect((await stat(output)).mode & 0o777).toBe(0o700);
    await expect(createPrivateCapture(root, output)).rejects.toThrow();
  });
  it.each(["", "../outside", ".opencommerce-other/take"])("rejects outside output %s", async (output) => {
    const root = await fixture();
    await expect(createPrivateCapture(root, output ? path.join(root, output) : output)).rejects.toThrow();
  });
  it("rejects symlink parents without following them", async () => {
    const root = await fixture();
    await mkdir(path.join(root, "elsewhere"));
    await symlink(path.join(root, "elsewhere"), path.join(root, ".opencommerce", "link"));
    await expect(createPrivateCapture(root, path.join(root, ".opencommerce", "link", "take"))).rejects.toThrow("Unsafe capture parent");
  });
  it("rejects a broken output symlink and missing parents", async () => {
    const root = await fixture();
    const link = path.join(root, ".opencommerce", "link");
    await symlink(path.join(root, "absent"), link);
    expect(() => newPrivateCapturePath(root, link)).toThrow("already exists");
    expect(() => newPrivateCapturePath(root, path.join(root, ".opencommerce", "missing", "take"))).toThrow();
  });
  it.each([
    { connected: false, canSend: false, index: undefined },
    { connected: false, canSend: false, index: "0" },
    { connected: true, canSend: false, index: "0" },
    { connected: true, canSend: true, index: undefined },
    { connected: true, canSend: true, index: "not-worker" },
  ])("refuses preexisting scratch before standalone runner cleanup %j", async (worker) => {
    const root = await fixture();
    const output = path.join(root, ".opencommerce", "scratch");
    expect(captureScratchPath(root, output, worker)).toBe(output);
    await mkdir(output);
    expect(() => captureScratchPath(root, output, worker)).toThrow("already exists");
    expect((await stat(output)).isDirectory()).toBe(true);
  });
  it("allows the IPC worker to reload its runner-created scratch only", async () => {
    const root = await fixture();
    const output = path.join(root, ".opencommerce", "scratch");
    const worker = { connected: true, canSend: true, index: "0" };
    expect(captureScratchPath(root, output, worker)).toBe(output);
    await mkdir(output);
    expect(captureScratchPath(root, output, worker)).toBe(output);
    expect(() => newPrivateCapturePath(root, output)).toThrow("already exists");
    const file = path.join(root, ".opencommerce", "not-directory");
    await writeFile(file, "retained evidence");
    expect(() => captureScratchPath(root, file, worker)).toThrow("Unsafe");
    const link = path.join(root, ".opencommerce", "link");
    await symlink(output, link);
    expect(() => captureScratchPath(root, link, worker)).toThrow("Unsafe");
    expect(() => captureScratchPath(root, path.join(link, "nested"), worker)).toThrow("Unsafe");
    expect(() => captureScratchPath(root, path.join(root, "outside"), worker)).toThrow("ignored");
  });
  const origins = ["http://127.0.0.1:53131", "http://127.0.0.1:53331"];
  it.each(["/manager", "/api/runtime/v1/merchant/imports/sample", "/api/runtime/v1/shopper/chat"])("permits the explicit local workflow %s", (route) => {
    expect(allowedDemoRequest(origins[0] + route, origins)).toBe(true);
  });
  it.each([
    "https://example.test/image.png", "http://127.0.0.1:1234/", "http://localhost:53131/",
    origins[0] + "/api/runtime/v1/merchant/store/check-ai",
    origins[0] + "/api/runtime/v1/manager/threads",
    origins[0] + "/api/runtime/v1/%6danager/threads",
    origins[0] + "/api/runtime/v1/merchant/store/%63heck-ai",
    origins[0] + "/%invalid", "not a URL",
  ])("blocks foreign endpoints and model-capable operator routes %s", (url) => {
    expect(allowedDemoRequest(url, origins)).toBe(false);
  });
  it("rejects credentialed loopback requests", () => {
    const url = new URL(origins[0]);
    url.username = "test-user";
    url.password = "test-value";
    expect(allowedDemoRequest(url.href, origins)).toBe(false);
  });
});

describe("capture failure boundaries", () => {
  const origin = "http://127.0.0.1:53131";
  function route(status = 200, location?: string) {
    const response = { status: () => status, headers: () => ({ location }), dispose: vi.fn(async () => {}) };
    const value = { request: () => ({ url: () => origin + "/manager" }),
      fetch: vi.fn(async () => response), fulfill: vi.fn(async () => {}),
      abort: vi.fn(async () => {}), continue: vi.fn(async () => {}) };
    return { value, response, typed: value as unknown as Route };
  }
  it.each([
    "https://example.invalid/escape", origin + "/api/runtime/v1/merchant/store/check-ai",
    origin + "/api/runtime/v1/manager/threads", origin + "/manager",
  ])("blocks the redirect before forwarding its target %s", async (location) => {
    const target = route(302, location);
    const denied = vi.fn();
    await guardDemoRoute(target.typed, [origin], denied);
    expect(target.value.fetch).toHaveBeenCalledWith({ maxRedirects: 0 });
    expect(denied).toHaveBeenCalledTimes(1);
    expect(target.value.abort).toHaveBeenCalledWith("blockedbyclient");
    expect(target.value.continue).not.toHaveBeenCalled();
    expect(target.value.fulfill).not.toHaveBeenCalled();
    expect(target.response.dispose).toHaveBeenCalledTimes(1);
  });
  it("fulfills one nonredirect response without unguarded browser continuation", async () => {
    const target = route();
    const denied = vi.fn();
    await guardDemoRoute(target.typed, [origin], denied);
    expect(target.value.fulfill).toHaveBeenCalledWith({ response: target.response });
    expect(target.value.continue).not.toHaveBeenCalled();
    expect(denied).not.toHaveBeenCalled();
  });
  it("contains protocol errors and counts even failed abort attempts", async () => {
    const target = route();
    target.value.fetch.mockRejectedValue(new Error("Cookie: SYNTHETIC-PRIVATE-COOKIE"));
    target.value.abort.mockRejectedValue(new Error("Set-Cookie: SYNTHETIC-PRIVATE-COOKIE"));
    const denied = vi.fn();
    await expect(guardDemoRoute(target.typed, [origin], denied)).resolves.toBeUndefined();
    expect(denied).toHaveBeenCalledTimes(1);
  });
  it("fails a negative milestone immediately, without polling it again", () => {
    expect(acceptedMilestone(null, "owner-ready")).toBe(false);
    expect(acceptedMilestone({ passed: true, stage: "owner-ready" }, "owner-ready")).toBe(true);
    expect(() => acceptedMilestone({ passed: false, stage: "owner-ready" }, "owner-ready")).toThrow("rejected");
    expect(() => acceptedMilestone({ passed: true, stage: "preview-tested" }, "owner-ready")).toThrow("Invalid");
  });
  it("does not report synthetic cookies from errors, steps, stdout or stderr", () => {
    const writes: string[] = [];
    vi.spyOn(process.stdout, "write").mockImplementation((value) => { writes.push(String(value)); return true; });
    const reporter: Reporter = new CatalogDemoReporter();
    const secret = "Cookie: SYNTHETIC-PRIVATE-COOKIE; Set-Cookie: SYNTHETIC-NEW-COOKIE";
    const result = { status: "failed", duration: 42, error: { message: secret, stack: secret },
      errors: [{ message: secret }], steps: [{ title: secret }], stdout: [secret], stderr: [secret],
    } as unknown as TestResult;
    reporter.onTestEnd?.({ title: secret } as unknown as TestCase, result);
    reporter.onError?.({ message: secret, stack: secret });
    reporter.onStdOut?.(secret, undefined, undefined);
    reporter.onStdErr?.(secret, undefined, undefined);
    expect(writes.join("")).not.toContain("SYNTHETIC");
    expect(writes.join("")).not.toContain("Cookie");
    expect(writes.join("")).toContain('"status":"failed"');
  });
});
