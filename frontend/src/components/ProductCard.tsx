import Image from "next/image";
import Link from "next/link";

import { rupees } from "@/lib/money";
import type { Product } from "@/lib/types";

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const image = product.images[0];
  return (
    <Link href={`/products/${product.slug}`} className="group flex flex-col">
      <div className="relative aspect-square overflow-hidden rounded-2xl border border-line bg-accent-soft">
        {image ? (
          <Image
            src={image.url}
            alt={image.alt_text || product.name}
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
            className="object-cover transition duration-300 group-hover:scale-105"
            preload={priority}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-4xl text-accent">✿</div>
        )}
        {product.available === 0 && (
          <span className="absolute left-2 top-2 rounded-full bg-foreground px-2 py-0.5 text-xs font-semibold text-background">
            Sold out
          </span>
        )}
      </div>
      <h3 className="mt-2 text-sm font-medium leading-snug group-hover:text-brand">{product.name}</h3>
      <p className="text-sm font-semibold">{rupees(product.price)}</p>
    </Link>
  );
}

export function ProductGrid({ products }: { products: Product[] }) {
  if (products.length === 0) {
    return (
      <p className="card p-8 text-center text-muted">
        No gifts match that yet. Try fewer filters or another search.
      </p>
    );
  }
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
      {products.map((product, index) => (
        <li key={product.id}>
          <ProductCard product={product} priority={index < 4} />
        </li>
      ))}
    </ul>
  );
}

export function GridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <li key={i}>
          <div className="aspect-square animate-pulse rounded-2xl bg-accent-soft" />
          <div className="mt-2 h-4 w-3/4 animate-pulse rounded bg-line" />
        </li>
      ))}
    </ul>
  );
}
