import type { NextConfig } from "next";

// Static export served by the page's Python service on Cloud Run (one origin: the page and /api).
// Fonts are downloaded at build time by next/font and self-hosted.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default config;
