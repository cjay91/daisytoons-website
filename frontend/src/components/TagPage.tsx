import Link from "next/link";
import { notFound } from "next/navigation";

import { ProductGrid } from "@/components/ProductCard";
import { getProducts, getTags } from "@/lib/catalog";
import type { Tag } from "@/lib/types";

export async function findTag(kind: Tag["kind"], slug: string): Promise<Tag | undefined> {
  return (await getTags()).find((tag) => tag.kind === kind && tag.slug === slug);
}

export async function TagProducts({ kind, slug }: { kind: Tag["kind"]; slug: string }) {
  const tag = await findTag(kind, slug);
  if (!tag) notFound();
  const filter: Record<string, string> = kind === "occasion" ? { occasion: slug } : { recipient: slug };
  const products = await getProducts(filter);
  return (
    <>
      <h1 className="text-2xl font-bold">
        {kind === "occasion" ? `${tag.name} gifts` : `Gifts ${tag.name.toLowerCase()}`}
      </h1>
      <p className="mb-6 mt-1 text-sm text-muted">
        {products.length} {products.length === 1 ? "gift" : "gifts"} ·{" "}
        <Link href={`/shop?${new URLSearchParams(filter)}`} className="text-brand">
          Filter by price
        </Link>
      </p>
      <ProductGrid products={products} />
    </>
  );
}
