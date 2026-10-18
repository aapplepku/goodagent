import { createHash, randomBytes } from "node:crypto";
import { chmod, link, lstat, readFile, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import type { ImportReview, OwnerAuthResponse, ShopperChatResponse, StoreReadiness } from "@open-commerce/sdk-typescript";
import { loopbackOrigin, webVtt, type Caption } from "./alpha-recording-utils";
import { acceptedMilestone, allowedDemoRequest, createPrivateCapture, guardDemoRoute } from "./catalog-demo-utils";

test("private no-AI catalog to store demonstration", async ({ browser, request }) => {
  process.umask(0o077);
  const root = path.resolve(import.meta.dirname, "../../..");
  const output = await createPrivateCapture(root, process.env.CATALOG_DEMO_OUTPUT ?? "");
  const runtime = path.resolve(process.env.CATALOG_DEMO_RUNTIME_DIR ?? "");
  if (runtime !== output + "-runtime") throw new Error("Expected the owned private runtime directory");
  const runtimeInfo = await lstat(runtime);
  if (runtimeInfo.isSymbolicLink() || !runtimeInfo.isDirectory()) throw new Error("Unsafe runtime directory");
  const ownerOrigin = loopbackOrigin(process.env.PLAYWRIGHT_BASE_URL);
  const shopperOrigin = loopbackOrigin(process.env.SHOPPER_PLAYWRIGHT_BASE_URL);
  const origins = [ownerOrigin, shopperOrigin];
  const started = new Date().toISOString();
  const contexts: BrowserContext[] = [];
  const clips: { name: string; caption: (text: string) => void; finish: () => Promise<void> }[] = [];
  const completed: Record<string, unknown>[] = [];
  const checkpoints: Record<string, unknown>[] = [];
  const receipt: Record<string, unknown> = {
    schema_version: 1, started_at: started, model_mode: "deterministic",
    passed: false, publication_approved: false, release_qualified: false,
    sample_values_synthetic: true, external_image_downloads_allowed: false,
    real_model_pair_completed: false, browser_denied_requests: 0,
    caption_alignment_review_required: true,
    browser_version: browser.version(), node_version: process.version,
    last_stage: "offscreen_setup",
  };
  let denied = 0;

  async function context(state?: Awaited<ReturnType<typeof request.storageState>>) {
    const result = await browser.newContext({
      storageState: state, viewport: { width: 1440, height: 1000 },
      locale: "en-US", timezoneId: "UTC", serviceWorkers: "block",
      recordVideo: { dir: path.join(output, "raw"), size: { width: 1440, height: 1000 } },
    });
    contexts.push(result);
    await result.route("**/*", (route) => guardDemoRoute(route, origins, () => { denied++; }));
    await result.routeWebSocket("**/*", (socket) => {
      const url = new URL(socket.url());
      url.protocol = url.protocol === "wss:" ? "https:" : "http:";
      if (allowedDemoRequest(url.href, origins)) socket.connectToServer();
      else { denied++; socket.close(); }
    });
    return result;
  }

  function record(name: string, page: Page, createdAt: number) {
    const cues: Caption[] = [];
    let finished = false;
    function caption(text: string) {
      const now = Math.max(Date.now() - createdAt, cues.length ? cues[cues.length - 1].startMs + 1 : 0);
      if (cues.length) cues[cues.length - 1].endMs = now;
      cues.push({ startMs: now, endMs: now + 1, text });
    }
    async function finish() {
      if (finished) return;
      finished = true;
      if (!cues.length) caption("Incomplete private take. No publication approval.");
      cues[cues.length - 1].endMs = Math.max(Date.now() - createdAt, cues[cues.length - 1].startMs + 1);
      const video = page.video();
      await page.close();
      if (!video) throw new Error("Expected private page recording");
      const filename = `${name}.webm`;
      await video.saveAs(path.join(output, filename));
      await chmod(path.join(output, filename), 0o600);
      const captions = `${name}.vtt`;
      const captionBytes = webVtt(cues);
      await writeFile(path.join(output, captions), captionBytes, { flag: "wx", mode: 0o600 });
      const bytes = await readFile(path.join(output, filename));
      completed.push({ name, filename, captions, sha256: createHash("sha256").update(bytes).digest("hex"),
        bytes: bytes.length, cues, captions_sha256: createHash("sha256").update(captionBytes).digest("hex"),
        waits_shortened: false, separate_browser_page: true,
        caption_clock: "wall time measured around page creation; inspect alignment", account_setup_recorded: false });
    }
    const clip = { name, caption, finish };
    clips.push(clip);
    return clip;
  }

  async function readiness(page: Page, label: string): Promise<StoreReadiness> {
    const response = await page.request.get(`${ownerOrigin}/api/runtime/v1/merchant/store`, { maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const state = await response.json() as StoreReadiness;
    checkpoints.push({ label, observed_at: new Date().toISOString(), store_id: state.store.id,
      catalog_id: state.indexing.catalog_id, job_id: state.indexing.job_id,
      source_version: state.indexing.source_version, index_status: state.indexing.status,
      product_count: state.indexing.product_count, indexed_product_count: state.indexing.indexed_product_count,
      image_failures: state.image_failures, checklist: state.checklist,
      sharing_enabled: state.store.sharing_enabled, published_catalog_id: state.store.published_catalog_id });
    expect(state.store.readiness?.ai_verified ?? false).toBe(false);
    return state;
  }
  async function pause(page: Page) { await page.waitForTimeout(5000); }
  async function auditMilestone(stage: "owner-ready" | "preview-tested") {
    const temporary = path.join(runtime, `${stage}.pending-${randomBytes(8).toString("hex")}`);
    const filename = path.join(runtime, `${stage}.json`);
    await writeFile(temporary, JSON.stringify({ store_id: receipt.store_id,
      import_id: receipt.import_id, catalog_id: receipt.catalog_id,
      review_fingerprint: receipt.review_fingerprint,
    }) + "\n", { flag: "wx", mode: 0o600 });
    try { await link(temporary, filename); } finally { await unlink(temporary); }
    const deadline = Date.now() + 30000;
    while (true) {
      const ack = path.join(runtime, `${stage}.ack.json`);
      try {
        const info = await lstat(ack);
        if (info.isSymbolicLink() || !info.isFile() || info.size > 512) throw new Error("Invalid runtime acknowledgement");
        if (acceptedMilestone(JSON.parse(await readFile(ack, "utf8")), stage)) return;
      } catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
      }
      if (Date.now() >= deadline) throw new Error("Runtime audit acknowledgement timed out");
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  async function inaccessible(slug: string) {
    const visitor = await browser.newContext({ serviceWorkers: "block" });
    try {
      const response = await visitor.request.get(`${shopperOrigin}/api/runtime/v1/shopper/store`,
        { headers: { "x-store-slug": slug }, maxRedirects: 0 });
      expect(response.status()).toBe(404);
    } finally { await visitor.close(); }
  }

  try {
    const status = await request.get(`${ownerOrigin}/api/runtime/v1/merchant/auth/status`, { maxRedirects: 0 });
    expect(status.status()).toBe(200);
    expect(await status.json()).toMatchObject({ profile: "self_hosted", setup_required: true });
    const setup = await request.post(`${ownerOrigin}/api/runtime/v1/merchant/auth/setup`, { maxRedirects: 0, data: {
      bootstrap_token: process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN,
      username: "catalog-demo-owner", password: randomBytes(24).toString("hex"),
      name: "Everyday Goods", description: "A sample store for home and everyday finds.",
    } });
    expect(setup.status(), "Fresh disposable owner setup must succeed off-screen").toBe(200);
    const { store } = await setup.json() as OwnerAuthResponse;
    receipt.store_id = store.id;
    receipt.store_slug = store.slug;
    expect(store.sharing_enabled).toBe(false);
    await inaccessible(store.slug);
    const ownerContext = await context(await request.storageState()); // Never serialize cookies.
    receipt.last_stage = "owner_ready";
    const ownerStart = Date.now();
    const owner = await ownerContext.newPage();
    const ownerClip = record("catalog-to-store", owner, ownerStart);
    ownerClip.caption("Basic-mode sample rehearsal. Owner setup was completed off-screen. No AI calls.");
    await owner.goto(`${ownerOrigin}/manager`);
    await expect(owner.getByRole("heading", { name: "Bring your products" })).toBeVisible();
    await readiness(owner, "before_import");
    await auditMilestone("owner-ready");
    await pause(owner);
    ownerClip.caption("Choose the attributed sample. Prices and stock are synthetic.");
    const sampleRequest = owner.waitForResponse(r => r.url().endsWith("/v1/merchant/imports/sample") && r.request().method() === "POST");
    receipt.last_stage = "sample_review";
    await owner.getByRole("button", { name: "Use sample products", exact: true }).click();
    const sampleResponse = await sampleRequest;
    expect(sampleResponse.ok()).toBe(true);
    const review = await sampleResponse.json() as ImportReview;
    expect(review).toMatchObject({ sample_data: true, product_count: 48, errors: [] });
    expect(review.review_fingerprint).toMatch(/^sha256:[0-9a-f]{64}$/);
    receipt.import_id = review.id;
    receipt.review_fingerprint = review.review_fingerprint;
    await expect(owner.getByRole("button", { name: "Confirm products", exact: true })).toBeEnabled();
    await pause(owner);
    await owner.screenshot({ path: path.join(output, "review.png") });
    ownerClip.caption("Confirm reviewed products. Actual image preparation and indexing; waiting is not shortened.");
    receipt.last_stage = "indexing";
    await owner.getByRole("button", { name: "Confirm products", exact: true }).click();
    await expect(owner.getByRole("button", { name: "Open shopper preview", exact: true })).toBeEnabled({ timeout: 180000 });
    const ready = await readiness(owner, "indexed_before_search");
    expect(ready.indexing).toMatchObject({ status: "ready", product_count: 48, indexed_product_count: 48 });
    expect(ready.image_failures).toBe(0);
    expect(ready.checklist).toMatchObject({ catalog_verified: true, search_tested: false });
    expect(ready.store.sharing_enabled).toBe(false);
    receipt.catalog_id = ready.indexing.catalog_id;
    await inaccessible(store.slug);
    await owner.getByRole("button", { name: "Review sharing", exact: true }).click();
    await owner.getByLabel("I reviewed the products and image issues.").check();
    await owner.getByLabel("Checkout is a demo. No real payments are taken.").check();
    await expect(owner.getByRole("button", { name: "Enable store link", exact: true })).toBeDisabled();
    await owner.getByRole("button", { name: "2 Preview", exact: true }).click();
    ownerClip.caption("Private preview opens in a separate recorded tab. AI remains disconnected.");
    const previewStart = Date.now();
    receipt.last_stage = "private_preview";
    const popup = ownerContext.waitForEvent("page");
    await owner.getByRole("button", { name: "Open shopper preview", exact: true }).click();
    const preview = await popup;
    const previewClip = record("private-preview", preview, previewStart);
    previewClip.caption("Private preview: attributed sample photos, synthetic prices. No model connection test.");
    await expect(preview.getByRole("heading", { name: "Browse the store" })).toBeVisible();
    const sampleImage = preview.getByLabel("Catalog products", { exact: true }).getByRole("img").first();
    await expect(sampleImage).toBeVisible();
    await expect.poll(() => sampleImage.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await pause(preview);
    await preview.getByRole("button", { name: "Start something new", exact: true }).click();
    await expect(preview.getByLabel("Conversation mode", { exact: true })).toHaveText("Basic mode: AI chat is not connected.");
    previewClip.caption("Basic search for Serene. No LLM answer or relevance benchmark.");
    await preview.getByLabel("Shopping request", { exact: true }).fill("Serene");
    receipt.last_stage = "basic_search";
    const resultRequest = preview.waitForResponse(r => r.url().endsWith("/v1/shopper/chat") && r.request().method() === "POST");
    await preview.getByRole("button", { name: "Send request", exact: true }).click();
    const resultResponse = await resultRequest;
    expect(resultResponse.ok()).toBe(true);
    const result = await resultResponse.json() as ShopperChatResponse;
    expect(result.assistant_message.content).toContain("Basic mode: AI chat is not connected.");
    expect(result.assistant_message.steps?.some(step => step.stage === "search" && step.status === "completed")).toBe(true);
    const selected = result.assistant_message.products?.find(product => product.product_id === "B0896LJNLH");
    expect(selected).toMatchObject({ product_id: "B0896LJNLH", price_minor: 1388, currency: "USD" });
    receipt.preview_product = { product_id: selected!.product_id, price_minor: selected!.price_minor, currency: selected!.currency };
    const resultCard = preview.locator(".product-card").filter({ hasText: selected!.title });
    await expect(resultCard).toBeVisible();
    await expect.poll(() => resultCard.getByRole("img").evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await pause(preview);
    await preview.screenshot({ path: path.join(output, "preview-result.png") });
    await previewClip.finish();
    await inaccessible(store.slug);
    const tested = await readiness(owner, "after_preview_search");
    expect(tested.checklist.search_tested).toBe(true);
    expect(tested.store.sharing_enabled).toBe(false);
    await auditMilestone("preview-tested");
    receipt.last_stage = "explicit_sharing";
    await owner.getByRole("button", { name: "Review sharing", exact: true }).click();
    await owner.getByLabel("I reviewed the products and image issues.").check();
    await owner.getByLabel("Checkout is a demo. No real payments are taken.").check();
    ownerClip.caption("Enable this verified catalog explicitly. The link works on this test machine only.");
    await pause(owner);
    await owner.getByRole("button", { name: "Enable store link", exact: true }).click();
    await expect(owner.getByRole("heading", { name: "Your store link is enabled" })).toBeVisible();
    const published = await readiness(owner, "after_explicit_sharing");
    expect(published.store).toMatchObject({ sharing_enabled: true, published_catalog_id: ready.indexing.catalog_id });
    await owner.screenshot({ path: path.join(output, "owner-ready.png") });
    await pause(owner);
    await ownerClip.finish();

    const guestContext = await context();
    receipt.last_stage = "fresh_guest_browse";
    expect(await guestContext.cookies()).toEqual([]);
    const guestStart = Date.now();
    const guest = await guestContext.newPage();
    const guestClip = record("shared-store-guest", guest, guestStart);
    guestClip.caption("Fresh guest visit to the shared local sample store. No account required.");
    await guest.goto(`${shopperOrigin}/s/${store.slug}`);
    await expect(guest.getByRole("heading", { name: "Browse the store" })).toBeVisible();
    await expect(guest.getByText("Private preview", { exact: false })).toHaveCount(0);
    const guestImage = guest.getByLabel("Catalog products", { exact: true }).getByRole("img").first();
    await expect.poll(() => guestImage.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await pause(guest);
    receipt.last_stage = "guest_filter";
    await guest.getByLabel("Find catalog products", { exact: true }).fill("Serene");
    const filteredRequest = guest.waitForResponse(r => r.url().includes("/v1/shopper/catalog?") && new URL(r.url()).searchParams.get("q") === "Serene");
    await guest.getByRole("button", { name: "Find products", exact: true }).click();
    const filteredResponse = await filteredRequest;
    expect(filteredResponse.ok()).toBe(true);
    expect((await filteredResponse.json()).items.map((item: { product_id: string }) => item.product_id)).toEqual(["B0896LJNLH"]);
    receipt.last_stage = "guest_grid_ready";
    await expect(guest.getByLabel("Catalog products", { exact: true })).toHaveAttribute("aria-busy", "false");
    await expect(guest.getByText("1 products matching filters", { exact: true })).toBeVisible();
    const guestProduct = guest.getByLabel("Catalog products", { exact: true }).getByRole("article");
    await expect(guestProduct).toHaveCount(1);
    await expect(guestProduct).toContainText(selected!.title);
    await expect.poll(() => guestProduct.getByRole("img").evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    guestClip.caption("One matching product, with its sample photo. Prices are synthetic; checkout is a demo.");
    await pause(guest);
    await guest.screenshot({ path: path.join(output, "guest-browse.png") });
    await guestClip.finish();
    expect(denied, "Even a swallowed denied request invalidates this take").toBe(0);
    receipt.last_stage = "browser_completed";
    receipt.passed = true;
  } catch {
    // Never pass authenticated Playwright call logs to a test reporter.
    throw new Error("Private catalog take failed; inspect bounded receipts and retained media");
  } finally {
    const browserCompleted = receipt.passed === true;
    const finishFailures: string[] = [];
    for (const clip of clips) {
      try { await clip.finish(); } catch { finishFailures.push(clip.name); }
    }
    for (const item of contexts) {
      try { await item.close(); } catch { finishFailures.push("context-close"); }
    }
    if (finishFailures.length || denied || completed.length !== 3) receipt.passed = false;
    const sourceFiles = ["apps/web/capture/catalog-demo.spec.ts", "apps/web/capture/catalog-demo-utils.ts", "apps/web/capture/catalog-demo-reporter.ts", "apps/web/catalog-demo.config.ts"];
    const sources = [];
    for (const filename of sourceFiles) sources.push({ path: filename,
      sha256: createHash("sha256").update(await readFile(path.join(root, filename))).digest("hex") });
    await writeFile(path.join(output, "receipt.json"), JSON.stringify({ ...receipt,
      finished_at: new Date().toISOString(), browser_denied_requests: denied, checkpoints, clips: completed,
      finish_failures: finishFailures, source_files: sources,
    }, null, 2) + "\n", { flag: "wx", mode: 0o600 });
    const players = ["catalog-to-store", "private-preview", "shared-store-guest"].filter(name => completed.some(item => item.name === name));
    await writeFile(path.join(output, "index.html"), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Private Basic-mode catalog demonstration</title><style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:0 16px;color:#172721;background:#f8faf9}video{width:100%;background:#111}p{line-height:1.6}h1{font-size:28px}h2{font-size:20px}</style><h1>Private Basic-mode demonstration</h1><p>Not approved for publication. ${receipt.passed ? "Browser assertions passed; runtime and human review remain separate." : "Incomplete failed take; retained for diagnosis."} No conversational AI. Sample photos are attributed Amazon Berkeley Objects; prices and stock are synthetic. Separate pages are separate clips, with actual waits retained. Account setup was off-screen. This is not the planned real-model demo pair.</p>${players.map(name => `<h2>${name}</h2><video controls preload="metadata"><source src="${name}.webm" type="video/webm"><track default kind="captions" srclang="en" label="English" src="${name}.vtt"></video>`).join("")}</html>`, { flag: "wx", mode: 0o600 });
    if (browserCompleted) expect(receipt.passed, "An incomplete take remains failed after video finalization").toBe(true);
  }
});
