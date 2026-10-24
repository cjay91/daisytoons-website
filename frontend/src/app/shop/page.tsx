import type { Metadata } from "next";
import { Suspense } from "react";

import { Filters } from "@/components/Filters";
import { GridSkeleton, ProductGrid } from "@/components/ProductCard";
import { getProducts, getTags, type ProductFilters } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Shop all gifts",
  description: "Search Daisytoons gifts by occasion, recipient and price.",
};

const KEYS = ["q", "occasion", "recipient", "min_price", "max_price", "sort"] as const;

function toFilters(params: Record<string, string | string[] | undefined>): ProductFilters {
  const filters: ProductFilters = {};
  for (const key of KEYS) {
    const value = params[key];
    const text = (Array.isArray(value) ? value[0] : value)?.trim();
    if (text) filters[key] = text;
  }
  return filters;
}

export default function ShopPage(props: PageProps<"/shop">) {
  return (
    <>
      <h1 className="mb-4 text-2xl font-bold">Shop all gifts</h1>
      <Suspense fallback={<GridSkeleton />}>
        <Results searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}

async function Results({ searchParams }: { searchParams: PageProps<"/shop">["searchParams"] }) {
  const filters = toFilters(await searchParams);
  const [tags, products] = await Promise.all([getTags(), getProducts(filters)]);
  return (
    <>
      <Filters tags={tags} current={filters} />
      <p className="my-4 text-sm text-muted">
        {products.length} {products.length === 1 ? "gift" : "gifts"}
        {filters.q ? ` matching "${filters.q}"` : ""}
      </p>
      <ProductGrid products={products} />
    </>
  );
}
