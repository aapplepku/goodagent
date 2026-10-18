import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.OPEN_COMMERCE_NEXT_DIST_DIR ?? ".next",
  devIndicators: false,
  output: "standalone",
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  // Catalog assets must keep their per-request authorization and no-store policy.
  images: {
    localPatterns: [],
    remotePatterns: [],
  },
};

export default nextConfig;
