import type { NextConfig } from "next";

// Product photos are served from the image bucket (S3_PUBLIC_BASE_URL on the API).
const imageBase = new URL(process.env.IMAGE_BASE_URL ?? "http://localhost:8333/daisytoons-images");
const localImages = ["localhost", "127.0.0.1"].includes(imageBase.hostname);

// Sent with every page. HSTS is added by the HTTPS proxy (Caddy) in production.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  // The Docker image builds a self-contained server (see Dockerfile).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  images: {
    remotePatterns: [new URL(`${imageBase.href.replace(/\/$/, "")}/**`)],
    // Only for the local image store in development.
    dangerouslyAllowLocalIP: localImages,
  },
  experimental: {
    serverActions: {
      // Photo uploads go through a Server Action; the API takes photos up to 5 MB.
      bodySizeLimit: "6mb",
    },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
