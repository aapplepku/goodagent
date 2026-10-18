// Test-only legacy cache entry, encoded by the installed Next.js implementation.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const { IncomingMessage } = require("node:http");
const { Socket } = require("node:net");
const { createRequire } = require("node:module");
const path = require("node:path");
const nextRequire = createRequire(path.resolve("apps/shopper/package.json"));
const { defaultConfig } = nextRequire("next/dist/server/config-shared");
const { ImageOptimizerCache, getImageEtag } = nextRequire("next/dist/server/image-optimizer");

async function main() {
  const [distDir, imagePath, href] = process.argv.slice(2);
  assert(distDir && imagePath && href);
  const buffer = await fs.readFile(imagePath);
  const request = new IncomingMessage(new Socket());
  request.headers.accept = "*/*";
  const parameters = ImageOptimizerCache.validateParams(
    request, { url: href, w: "640", q: "75" }, defaultConfig, false,
  );
  assert(!parameters.errorMessage);
  const key = ImageOptimizerCache.getCacheKey(parameters);
  const cache = new ImageOptimizerCache({ distDir, nextConfig: defaultConfig });
  const etag = getImageEtag(buffer);
  await cache.set(key, { kind: "IMAGE", buffer, extension: "png", etag, upstreamEtag: etag }, {
    cacheControl: { revalidate: 600, expire: undefined },
  });
  const stored = await cache.get(key);
  assert(stored && !stored.isStale && stored.value.buffer.equals(buffer));
  console.log(JSON.stringify({ key, bytes: buffer.length, verified: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
