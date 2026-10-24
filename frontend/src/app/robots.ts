import type { MetadataRoute } from "next";

const site = process.env.SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/cart", "/checkout", "/account", "/order/"] },
    sitemap: `${site}/sitemap.xml`,
  };
}
