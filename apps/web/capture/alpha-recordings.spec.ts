import { createHash, randomBytes } from "node:crypto";
import { chmod, lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import type { ShopperChatResponse } from "@open-commerce/sdk-typescript";
import { loopbackOrigin, webVtt, type Caption } from "./alpha-recording-utils";

const harnessFiles = [import.meta.filename, path.join(import.meta.dirname, "alpha-recording-utils.ts"), path.join(import.meta.dirname, "../alpha-recordings.config.ts")];
const harnessHashes = await Promise.all(harnessFiles.map(async (filename) => ({
  filename: path.basename(filename), sha256: createHash("sha256").update(await readFile(filename)).digest("hex"),
})));

test("two private alpha recordings from a fresh sample store", async ({ browser, request }) => {
  process.umask(0o077);
  const root = path.resolve(import.meta.dirname, "../../..");
  const privateRoot = path.join(root, ".opencommerce");
  const output = path.resolve(process.env.ALPHA_RECORDING_DIR ?? "");
  if (!output.startsWith(privateRoot + path.sep)) throw new Error("Recordings must remain under ignored .opencommerce");
  let parent = path.dirname(output);
  while (parent.startsWith(privateRoot)) {
    if ((await lstat(parent)).isSymbolicLink()) throw new Error("Symlink capture parent refused");
    parent = path.dirname(parent);
  }
  await mkdir(output, { mode: 0o700 });
  const ownerOrigin = loopbackOrigin(process.env.PLAYWRIGHT_BASE_URL);
  const shopperOrigin = loopbackOrigin(process.env.SHOPPER_PLAYWRIGHT_BASE_URL);
  const status = await request.get("/api/runtime/v1/merchant/auth/status");
  expect(status.ok()).toBe(true);
  const setup = await status.json();
  expect(setup.profile).toBe("self_hosted");
  expect(setup.setup_required, "Never record against an existing owner/store").toBe(true);
  const auth = await request.post("/api/runtime/v1/merchant/auth/setup", { data: {
    bootstrap_token: process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN,
    username: "alpha-demo-owner", password: randomBytes(24).toString("hex"),
    name: "Everyday Goods", description: "Thoughtful finds for home and everyday life.",
  } });
  expect(auth.ok(), "Disposable owner setup failed").toBe(true);
  const createdStore = (await auth.json()).store;
  const ownerState = await request.storageState(); // Memory only; never serialize session state.
  const completed: Record<string, unknown>[] = [];
  const contexts: BrowserContext[] = [];
  const transcript: { prompt: string; response: string; products: unknown[]; memories: string[];
    steps: NonNullable<ShopperChatResponse["assistant_message"]["steps"]> }[] = [];
  let passed = false;

  async function recording(name: string, state?: Awaited<ReturnType<typeof request.storageState>>) {
    const context = await browser.newContext({
      storageState: state, viewport: { width: 1440, height: 1000 }, locale: "en-US", timezoneId: "UTC",
      recordVideo: { dir: path.join(output, "raw"), size: { width: 1440, height: 1000 } },
    });
    contexts.push(context);
    await context.route("**/*", async (route) => {
      const origin = new URL(route.request().url()).origin;
      if (![ownerOrigin, shopperOrigin].includes(origin)) return route.abort("blockedbyclient");
      return route.continue();
    });
    const start = Date.now();
    const page = await context.newPage();
    const cues: Caption[] = [];
    function caption(text: string) {
      const now = Date.now() - start;
      if (cues.length) cues[cues.length - 1].endMs = now;
      cues.push({ startMs: now, endMs: now + 1, text });
    }
    async function finish() {
      cues[cues.length - 1].endMs = Date.now() - start;
      const video = page.video();
      await context.close();
      if (!video) throw new Error("Recording not created");
      const filename = `${name}.webm`;
      await video.saveAs(path.join(output, filename));
      await chmod(path.join(output, filename), 0o600);
      await writeFile(path.join(output, `${name}.vtt`), webVtt(cues), { flag: "wx", mode: 0o600 });
      const bytes = await readFile(path.join(output, filename));
      completed.push({ name, filename, captions: `${name}.vtt`, bytes: bytes.length,
        sha256: createHash("sha256").update(bytes).digest("hex"), cues,
        waits_shortened: false, account_setup_recorded: false, model_mode: "openai" });
    }
    return { page, context, caption, finish };
  }

  async function chat(page: Page, prompt: string): Promise<ShopperChatResponse> {
    const messages = page.locator('.shop-message[data-role="assistant"]');
    const previousCount = await messages.count();
    await page.getByLabel("Shopping request", { exact: true }).fill(prompt);
    const response = page.waitForResponse(r => r.url().endsWith("/v1/shopper/chat") && r.request().method() === "POST", { timeout: 180000 });
    await page.getByRole("button", { name: "Send request", exact: true }).click();
    const reply = await response;
    expect(reply.ok(), "Real shopper turn failed; do not replace with a canned response").toBe(true);
    const result = await reply.json() as ShopperChatResponse;
    transcript.push({ prompt, response: result.assistant_message.content,
      products: result.assistant_message.products ?? [], memories: (result.memories_saved ?? []).map(m => m.content),
      steps: result.assistant_message.steps ?? [] });
    expect(result.assistant_message.steps?.some(s => s.status === "fallback")).toBe(false);
    expect(result.assistant_message.content.trim()).not.toBe("");
    await expect(messages).toHaveCount(previousCount + 1);
    await expect(messages.last()).toBeVisible();
    return result;
  }

  async function pause(page: Page) { await page.waitForTimeout(2500); }
  try {
    const owner = await recording("catalog-to-store", ownerState);
    owner.caption("Private alpha rehearsal. Owner already signed in; account setup and secrets are not recorded.");
    await owner.page.goto(`${ownerOrigin}/manager`);
    await expect(owner.page.getByRole("heading", { name: "Bring your products" })).toBeVisible();
    await pause(owner.page);
    owner.caption("Explicitly choosing licensed sample products. Prices, stock and engagement are synthetic.");
    await owner.page.getByRole("button", { name: "Use sample products", exact: true }).click();
    await expect(owner.page.getByRole("button", { name: "Confirm products", exact: true })).toBeEnabled();
    await pause(owner.page);
    owner.caption("Review and confirm. Indexing and image checks run in the real worker; no waiting time is removed.");
    await owner.page.getByRole("button", { name: "Confirm products", exact: true }).click();
    await expect(owner.page.getByRole("button", { name: "Open shopper preview" })).toBeEnabled({ timeout: 120000 });
    const check = owner.page.waitForResponse(r => r.url().endsWith("/v1/merchant/store/check-ai"));
    await owner.page.getByRole("button", { name: "Check AI connection" }).click();
    expect((await (await check).json()).connected, "A configured key alone is not a connected model").toBe(true);
    owner.caption("Private preview opens in another tab. A real model-backed catalog search is tested there before sharing.");
    const popup = owner.context.waitForEvent("page");
    await owner.page.getByRole("button", { name: "Open shopper preview" }).click();
    const preview = await popup;
    await expect(preview.getByRole("heading", { name: "Browse the store" })).toBeVisible();
    await preview.getByRole("button", { name: "Start something new", exact: true }).click();
    const previewReply = await chat(preview, "Find dishwasher-safe drinking glasses under $30.");
    expect(previewReply.assistant_message.products?.length).toBeGreaterThan(0);
    expect(previewReply.assistant_message.products?.every(p => p.price_minor <= 3000 && p.currency === "USD")).toBe(true);
    await preview.close();
    await owner.page.getByRole("button", { name: "Review sharing" }).click();
    owner.caption("Sharing is an explicit owner action for this verified catalog. Checkout is demo-only.");
    await owner.page.getByLabel("I reviewed the products and image issues.").check();
    await owner.page.getByLabel("Checkout is a demo. No real payments are taken.").check();
    await owner.page.getByRole("button", { name: "Enable store link", exact: true }).click();
    await expect(owner.page.getByRole("heading", { name: "Your store link is enabled" })).toBeVisible();
    const href = await owner.page.getByRole("link", { name: "Open shared store" }).getAttribute("href");
    const slug = new URL(href!, ownerOrigin).searchParams.get("store");
    expect(slug).toMatch(/^[a-z0-9-]+$/);
    expect(slug).toBe(createdStore.slug);
    await owner.page.screenshot({ path: path.join(output, "owner-ready.png") });
    await pause(owner.page);
    await owner.finish();

    // Register a synthetic shopper off-screen; never record the recovery-code UI.
    const preparation = await browser.newContext();
    contexts.push(preparation);
    const headers = { "x-store-slug": slug! };
    const storefront = await preparation.request.get(`${shopperOrigin}/api/runtime/v1/shopper/store`, { headers });
    expect(storefront.ok(), "Shopper must resolve the newly created store before any account write").toBe(true);
    expect(await storefront.json()).toMatchObject({ slug: createdStore.slug, name: createdStore.name, preview: false, sample_data: true });
    expect((await preparation.request.post(`${shopperOrigin}/api/runtime/v1/shopper/auth/guest`, { headers })).ok()).toBe(true);
    const registration = await preparation.request.post(`${shopperOrigin}/api/runtime/v1/shopper/auth/register`, { headers, data: {
      username: "alpha-demo-shopper", display_name: "Demo shopper", password: randomBytes(24).toString("hex"),
    } });
    expect(registration.ok()).toBe(true);
    const shopperState = await preparation.storageState();
    await preparation.close();
    const shopper = await recording("shopping-with-an-agent", shopperState);
    shopper.caption("Registered synthetic shopper. Public sample photos; prices and availability are illustrative, not current offers.");
    await shopper.page.goto(`${shopperOrigin}/s/${slug}`);
    await expect(shopper.page.getByRole("heading", { name: "Browse the store" })).toBeVisible();
    const sampleImage = shopper.page.getByLabel("Catalog products").getByRole("img").first();
    await expect(sampleImage).toBeVisible();
    await expect.poll(() => sampleImage.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await pause(shopper.page);
    await shopper.page.getByRole("button", { name: "Start something new", exact: true }).click();
    shopper.caption("Real OpenAI conversation using the configured model. The agent searches the store catalog.");
    const budget = await chat(shopper.page, "Find dishwasher-safe drinking glasses under $30.");
    expect(budget.assistant_message.products?.length).toBeGreaterThan(0);
    expect(budget.assistant_message.products?.every(p => p.price_minor <= 3000 && p.currency === "USD")).toBe(true);
    await pause(shopper.page);
    shopper.caption("Compare actual catalog prices. This recording is one observed run, not a general quality guarantee.");
    const comparison = await chat(shopper.page, "Compare Serene 16-Piece and Eastlake 15-Ounce Set of 6. Which is cheaper, and by how much?");
    expect(comparison.assistant_message.content).toContain("23.34");
    expect(comparison.assistant_message.products?.map(p => p.product_id).sort()).toEqual(["B0896KVCJY", "B0896LJNLH"]);
    await pause(shopper.page);
    shopper.caption("Ask to save a preference. The saved indicator and memory panel must reflect a committed database save.");
    const memory = await chat(shopper.page, "I prefer dishwasher-safe drinking glasses. Please remember that for future shopping.");
    expect(memory.memories_saved?.length ?? 0).toBeGreaterThan(0);
    await shopper.page.getByRole("button", { name: /Shopping memory/ }).click();
    await expect(shopper.page.locator(".memory-list")).toContainText(/dishwasher/i);
    await pause(shopper.page);
    await shopper.page.reload();
    await shopper.page.getByRole("button", { name: /Shopping memory/ }).click();
    await expect(shopper.page.locator(".memory-list")).toContainText(/dishwasher/i);
    shopper.caption("Memory survives reload. Account controls allow opt-out and deletion; guest memory is temporary.");
    await pause(shopper.page);
    await shopper.page.getByRole("button", { name: "Close memory" }).click();
    await shopper.page.getByRole("button", { name: "Browse catalog", exact: true }).click();
    await shopper.page.getByLabel("Find catalog products").fill("Serene");
    const filtered = shopper.page.waitForResponse(r => r.url().includes("/v1/shopper/catalog?") && new URL(r.url()).searchParams.get("q") === "Serene");
    await shopper.page.getByRole("button", { name: "Find products", exact: true }).click();
    const filteredResponse = await filtered;
    expect(filteredResponse.ok()).toBe(true);
    expect((await filteredResponse.json()).items.map((item: { product_id: string }) => item.product_id)).toEqual(["B0896LJNLH"]);
    const products = shopper.page.getByLabel("Catalog products");
    await expect(products).toHaveAttribute("aria-busy", "false");
    const selected = products.getByRole("article").filter({ has: shopper.page.getByRole("heading", { name: "AmazonBasics Serene 16-Piece Old Fashioned and Coolers Glass Drinkware Set", exact: true }) });
    await selected.getByRole("button", { name: "View product", exact: true }).click();
    shopper.caption("Inspect the real product and variant before adding. The agent cannot silently purchase anything.");
    await expect(shopper.page.getByLabel("Product details", { exact: true })).toBeVisible();
    await expect(shopper.page.getByLabel("Product details", { exact: true })).toContainText("AmazonBasics Serene 16-Piece Old Fashioned and Coolers Glass Drinkware Set");
    await shopper.page.getByLabel("Choose a variant").selectOption("B0896LJNLH-default");
    await pause(shopper.page);
    await shopper.page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await shopper.page.getByRole("button", { name: "Review checkout", exact: true }).click();
    shopper.caption("Explicit demo checkout. No money is charged, and no real inventory or fulfillment is changed.");
    await pause(shopper.page);
    await shopper.page.getByRole("button", { name: "Approve test payment", exact: true }).click();
    await expect(shopper.page.getByText("Order confirmed", { exact: true })).toBeVisible();
    await shopper.page.screenshot({ path: path.join(output, "shopper-checkout.png") });
    await pause(shopper.page);
    await shopper.finish();
    await writeFile(path.join(output, "index.html"), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Private alpha demonstrations</title><style>body{font:16px system-ui;margin:32px auto;max-width:1000px;padding:0 16px;color:#172721;background:#f7faf9}video{width:100%;background:#111}h1{font-size:28px}h2{font-size:20px;margin-top:32px}p{line-height:1.6}a{color:#087b70}</style><h1>Private alpha demonstrations</h1><p>Experimental self-hosted store. Real recorded interaction, including waits. Sample prices and stock are synthetic; checkout charges no money. These recordings are not approved for publication.</p><h2>Catalog to working store</h2><video controls preload="metadata"><source src="catalog-to-store.webm" type="video/webm"><track default kind="captions" srclang="en" label="English" src="catalog-to-store.vtt"></video><p>Owner already signed in. Preview search runs in a separate tab; that raw clip is retained privately.</p><h2>Shopping with an agent</h2><video controls preload="metadata"><source src="shopping-with-an-agent.webm" type="video/webm"><track default kind="captions" srclang="en" label="English" src="shopping-with-an-agent.vtt"></video><p>Registered synthetic shopper. Account setup and recovery codes are excluded. This is one observed model run, not a quality benchmark.</p></html>`, { flag: "wx", mode: 0o600 });
    passed = true;
  } finally {
    if (!passed) {
      for (const [contextIndex, context] of contexts.entries()) {
        for (const [pageIndex, page] of context.pages().entries()) {
          await page.screenshot({ path: path.join(output, `failure-${contextIndex}-${pageIndex}.png`) }).catch(() => undefined);
        }
      }
    }
    for (const context of contexts) await context.close().catch(() => undefined);
    const finalHashes = await Promise.all(harnessFiles.map(async (filename) => ({
      filename: path.basename(filename), sha256: createHash("sha256").update(await readFile(filename)).digest("hex"),
    })));
    const unchanged = JSON.stringify(finalHashes) === JSON.stringify(harnessHashes);
    await writeFile(path.join(output, "manifest.json"), JSON.stringify({
      recorded_at: new Date().toISOString(), passed: passed && unchanged, publication_approved: false,
      viewport: { width: 1440, height: 1000 }, recordings: completed,
      browser_version: browser.version(), harness_hashes_before: harnessHashes, harness_hashes_after: finalHashes, harness_unchanged: unchanged,
      limitations: ["Private rehearsal, not a qualified public candidate", "Fixed synthetic prompts; no retry on model/test failure", "Owner preview is a separate raw clip", "No edit or shortened waits", "Captions are sidecar WebVTT"],
    }, null, 2), { flag: "wx", mode: 0o600 });
    await writeFile(path.join(output, "synthetic-transcript.json"), JSON.stringify(transcript, null, 2), { flag: "wx", mode: 0o600 });
    expect(unchanged, "Harness changed during capture; provenance is invalid").toBe(true);
  }
});
