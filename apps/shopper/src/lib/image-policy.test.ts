// @vitest-environment node
import { IncomingMessage } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import { Socket } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { PHASE_PRODUCTION_SERVER } from "next/constants";
import loadConfig from "next/dist/server/config";
import type { NextConfigComplete } from "next/dist/server/config-shared";
import { ImageOptimizerCache } from "next/dist/server/image-optimizer";

import nextConfig from "../../next.config";

let config: NextConfigComplete;
let directory: string;

beforeAll(async () => {
  // Normalize the real app policy without reading a developer's environment file.
  directory = await mkdtemp(join(tmpdir(), "image-policy-"));
  config = await loadConfig(PHASE_PRODUCTION_SERVER, directory, {
    customConfig: {
      ...nextConfig,
      images: {
        ...nextConfig.images,
        localPatterns: [...(nextConfig.images?.localPatterns ?? [])],
      },
    },
  });
});

afterAll(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

function validate(url: string) {
  const request = new IncomingMessage(new Socket());
  return ImageOptimizerCache.validateParams(
    request, { url, w: "640", q: "75" }, config, false,
  );
}

describe("shopper image optimizer policy", () => {
  it("only opts into generated static media, not arbitrary public paths", () => {
    expect(nextConfig.images?.localPatterns).toEqual([]);
    expect(nextConfig.images?.unoptimized).not.toBe(true);
  });

  it("includes Next's generated static-media allowance in the effective policy", () => {
    expect(config.images.localPatterns).toEqual([
      { pathname: "/_next/static/media/**", search: "" },
    ]);
    expect(validate("/_next/static/media/bundled.png")).toMatchObject({
      href: "/_next/static/media/bundled.png", isStatic: true,
    });
  });

  it.each([
    "/api/runtime/v1/shopper/assets/fixture?store=test-store",
    "/api/runtime/v1/merchant/assets/fixture",
    "/api/runtime/v1/shopper/assets/fixture",
    "/api/runtime/v1/shopper/store?store=test-store",
    "/s/test-store",
    "/abo-images/B000X1T1E2.jpg",
    "/shopper-grocery-spread.png",
    "/shopper-grocery-spread.png?store=test-store",
    "/shopper-grocery-spread.png?url=/api/runtime/v1/shopper/assets/fixture",
    "/shopper-grocery-spread.png/../api/runtime/v1/shopper/assets/fixture",
    "/%61pi/runtime/v1/shopper/assets/fixture",
    "/shopper-grocery-spread.png/%2e%2e/api/runtime/v1/shopper/assets/fixture",
    "/%2fapi%2fruntime%2fv1%2fshopper%2fassets%2ffixture",
    "https://example.com/shopper-grocery-spread.png",
    "http://127.0.0.1:8000/v1/shopper/assets/fixture",
    "//127.0.0.1:8000/v1/shopper/assets/fixture",
  ])("rejects dynamic, query-bearing and remote image sources: %s", (url) => {
    expect(validate(url)).toHaveProperty("errorMessage");
  });
});
