import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AddToCart } from "@/components/AddToCart";
import { getProduct } from "@/lib/catalog";
import { rupees } from "@/lib/money";
import type { Product } from "@/lib/types";

type Params = PageProps<"/products/[slug]">["params"];

export async function generateMetadata(props: PageProps<"/products/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const product = await getProduct(slug);
  if (!product) return {};
  const description = product.description.slice(0, 160) || `${product.name} from Daisytoons.`;
  return {
    title: product.name,
    description,
    alternates: { canonical: `/products/${product.slug}` },
    openGraph: {
      title: product.name,
      description,
      images: product.images.slice(0, 1).map((image) => ({ url: image.url, alt: image.alt_text })),
    },
  };
}

export default function ProductPage(props: PageProps<"/products/[slug]">) {
  return (
    <Suspense fallback={<ProductSkeleton />}>
      <ProductDetails params={props.params} />
    </Suspense>
  );
}

async function ProductDetails({ params }: { params: Params }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();
  const [main, ...rest] = product.images;
  return (
    <article className="grid gap-8 md:grid-cols-2">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd(product)).replace(/</g, "\\u003c") }}
      />
      <div className="flex flex-col gap-3">
        <div className="relative aspect-square overflow-hidden rounded-3xl border border-line bg-accent-soft">
          {main ? (
            <Image
              src={main.url}
              alt={main.alt_text || product.name}
              fill
              sizes="(min-width: 768px) 50vw, 100vw"
              className="object-cover"
              preload
            />
          ) : (
            <div className="flex h-full items-center justify-center text-6xl text-accent">✿</div>
          )}
        </div>
        {rest.length > 0 && (
          <ul className="grid grid-cols-4 gap-2">
            {rest.map((image) => (
              <li key={image.id} className="relative aspect-square overflow-hidden rounded-xl border border-line">
                <Image src={image.url} alt={image.alt_text || product.name} fill sizes="25vw" className="object-cover" />
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{product.name}</h1>
        <p className="mt-2 text-2xl font-semibold">{rupees(product.price)}</p>
        <div className="mt-6">
          <AddToCart productId={product.id} available={product.available} />
        </div>
        <div className="mt-6 whitespace-pre-line text-muted">{product.description}</div>
        <ul className="mt-6 flex flex-wrap gap-2">
          {product.tags.map((tag) => (
            <li key={tag.id}>
              <Link
                href={`/${tag.kind === "occasion" ? "occasions" : "for"}/${tag.slug}`}
                className="btn-outline text-xs"
              >
                {tag.name}
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-8 rounded-2xl bg-accent-soft p-4 text-sm">
          <p className="font-semibold">Gift wrap available</p>
          <p className="text-muted">Add wrapping and a message in your cart for Rs 250.</p>
        </div>
      </div>
    </article>
  );
}

function jsonLd(product: Product) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    sku: product.sku,
    description: product.description,
    image: product.images.map((image) => image.url),
    offers: {
      "@type": "Offer",
      price: product.price,
      priceCurrency: product.currency,
      availability:
        product.available > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
    },
  };
}

function ProductSkeleton() {
  return (
    <div className="grid gap-8 md:grid-cols-2" aria-hidden>
      <div className="aspect-square animate-pulse rounded-3xl bg-accent-soft" />
      <div className="flex flex-col gap-3">
        <div className="h-8 w-2/3 animate-pulse rounded bg-line" />
        <div className="h-6 w-1/4 animate-pulse rounded bg-line" />
      </div>
    </div>
  );
}
