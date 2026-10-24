import type { NextConfig } from "next";

// Product photos are served from the image bucket (S3_PUBLIC_BASE_URL on the API).
const imageBase = new URL(process.env.IMAGE_BASE_URL ?? "http://localhost:8333/daisytoons-images");
const localImages = ["localhost", "127.0.0.1"].includes(imageBase.hostname);

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  images: {
    remotePatterns: [new URL(`${imageBase.href.replace(/\/$/, "")}/**`)],
    // Only for the local image store in development.
    dangerouslyAllowLocalIP: localImages,
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
