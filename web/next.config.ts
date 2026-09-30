import type { NextConfig } from "next";

// Static export served by the FastAPI duel service (one process, one origin, works offline).
// Fonts are downloaded at build time by next/font and self-hosted: no internet on stage.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // `npm run dev` talks to a running duel service (make duel) through this proxy.
  ...(process.env.NODE_ENV === "development"
    ? { async rewrites() { return [{ source: "/api/:path*", destination: "http://127.0.0.1:8787/api/:path*" }]; } }
    : {}),
};

export default config;
