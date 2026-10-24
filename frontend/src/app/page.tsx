import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { GridSkeleton, ProductGrid } from "@/components/ProductCard";
import { getProducts, getTags } from "@/lib/catalog";

export default function Home() {
  return (
    <>
      <section className="rounded-3xl bg-accent-soft px-6 py-10 sm:px-10 sm:py-16">
        <p className="text-sm font-semibold uppercase tracking-widest text-brand">Daisytoons gifts</p>
        <h1 className="mt-2 max-w-xl text-3xl font-bold tracking-tight sm:text-5xl">
          The right gift, wrapped and on its way.
        </h1>
        <p className="mt-4 max-w-lg text-muted">
          Find something they&apos;ll love by occasion or by who it&apos;s for. Gift wrap and a
          handwritten-style message are one tap away.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/shop" className="btn">
            Shop all gifts
          </Link>
          <Link href="/occasions" className="btn-outline bg-surface">
            Shop by occasion
          </Link>
        </div>
      </section>

      <Suspense fallback={<div className="mt-10 h-24" />}>
        <OccasionChips />
      </Suspense>

      <section className="mt-12">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-xl font-bold">New in</h2>
          <Link href="/shop?sort=newest" className="text-sm font-medium text-brand">
            See all
          </Link>
        </div>
        <Suspense fallback={<GridSkeleton />}>
          <NewIn />
        </Suspense>
      </section>
    </>
  );
}

async function OccasionChips() {
  await connection();
  const tags = await getTags();
  const occasions = tags.filter((tag) => tag.kind === "occasion");
  const recipients = tags.filter((tag) => tag.kind === "recipient");
  return (
    <div className="mt-10 grid gap-6 sm:grid-cols-2">
      <ChipGroup title="Shop by occasion" base="/occasions" tags={occasions} />
      <ChipGroup title="Shop by who it's for" base="/for" tags={recipients} />
    </div>
  );
}

function ChipGroup({ title, base, tags }: { title: string; base: string; tags: { slug: string; name: string }[] }) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-bold">{title}</h2>
      <ul className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <li key={tag.slug}>
            <Link href={`${base}/${tag.slug}`} className="btn-outline bg-surface">
              {tag.name}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

async function NewIn() {
  await connection();
  const products = await getProducts({ sort: "newest" });
  return <ProductGrid products={products.slice(0, 8)} />;
}
