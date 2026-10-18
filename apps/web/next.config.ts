import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  distDir: process.env.OPEN_COMMERCE_NEXT_DIST_DIR ?? ".next",
  output: "standalone",
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  // All operator images use authorized catalog URLs, never a public image cache.
  images: { unoptimized: true },
};

export default nextConfig;
