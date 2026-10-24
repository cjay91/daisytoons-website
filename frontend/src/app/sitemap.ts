import type { MetadataRoute } from "next";
import { connection } from "next/server";

import { getProducts, getTags } from "@/lib/catalog";

const site = process.env.SITE_URL ?? "http://localhost:3000";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Built when it's requested, from the live catalog.
  await connection();
  const [products, tags] = await Promise.all([getProducts(), getTags()]);
  return [
    { url: site, changeFrequency: "daily", priority: 1 },
    { url: `${site}/shop`, changeFrequency: "daily", priority: 0.8 },
    { url: `${site}/occasions`, changeFrequency: "weekly", priority: 0.6 },
    ...tags.map((tag) => ({
      url: `${site}/${tag.kind === "occasion" ? "occasions" : "for"}/${tag.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...products.map((product) => ({
      url: `${site}/products/${product.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
  ];
}
