import type { Metadata } from "next";
import Form from "next/form";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { query } from "@/lib/api";
import { rupees } from "@/lib/format";
import { can } from "@/lib/roles";
import { requireStaff, staffApi } from "@/lib/session";
import type { Product } from "@/lib/types";

export const metadata: Metadata = { title: "Products" };

export default function ProductsPage({ searchParams }: PageProps<"/products">) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Products</h1>
      <Suspense fallback={<Loading />}>
        <Products searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Products({ searchParams }: Pick<PageProps<"/products">, "searchParams">) {
  const { q } = await searchParams;
  const search = typeof q === "string" ? q : "";
  const [staff, products] = await Promise.all([
    requireStaff(),
    staffApi<Product[]>(`/staff/products${query({ q: search })}`),
  ]);
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <Form action="/products" className="flex gap-2">
          <label htmlFor="product-search" className="sr-only">
            Search products
          </label>
          <input id="product-search" name="q" defaultValue={search} placeholder="Name or SKU" className="input w-64" />
          <button className="btn-outline">Search</button>
        </Form>
        {can(staff.role, "reports") && (
          <Link href="/products/new" className="btn ml-auto">
            New product
          </Link>
        )}
      </div>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-14" />
              <th>Product</th>
              <th>SKU</th>
              <th className="text-right">Price</th>
              <th className="text-right">On hand</th>
              <th className="text-right">Reserved</th>
              <th className="text-right">Available</th>
              <th>Bin</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product) => {
              const low = product.inventory && product.available <= product.inventory.reorder_point;
              return (
                <tr key={product.id} className={product.is_active ? "" : "opacity-60"}>
                  <td>
                    {product.images[0] && (
                      <Image src={product.images[0].url} alt="" width={40} height={40} className="h-10 w-10 rounded object-cover" />
                    )}
                  </td>
                  <td>
                    <Link href={`/products/${product.id}`} className="font-medium text-brand">
                      {product.name}
                    </Link>
                    {!product.is_active && <span className="ml-2 text-xs text-muted">(not on sale)</span>}
                  </td>
                  <td className="font-mono text-xs">{product.sku}</td>
                  <td className="text-right tabular-nums">{rupees(product.price)}</td>
                  <td className="text-right tabular-nums">{product.inventory?.on_hand ?? 0}</td>
                  <td className="text-right tabular-nums">{product.inventory?.reserved ?? 0}</td>
                  <td className={`text-right font-semibold tabular-nums ${low ? "text-danger" : ""}`}>{product.available}</td>
                  <td className="font-mono text-xs">{product.inventory?.bin_location}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {products.length === 0 && <p className="p-6 text-center text-muted">No products found.</p>}
      </div>
    </>
  );
}
