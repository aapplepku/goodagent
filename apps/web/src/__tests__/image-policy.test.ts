import { expect, it } from "vitest";

import nextConfig from "../../next.config";

it("disables the public optimizer for authorized operator catalog images", () => {
  expect(nextConfig.images?.unoptimized).toBe(true);
});
