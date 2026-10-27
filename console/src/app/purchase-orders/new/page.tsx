import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { PurchaseOrderForm } from "@/components/PurchaseOrderForm";
import { staffApi } from "@/lib/session";
import type { Product, Supplier } from "@/lib/types";

export const metadata: Metadata = { title: "New purchase order" };

export default function NewPurchaseOrderPage({ searchParams }: PageProps<"/purchase-orders/new">) {
  return (
    <div className="flex flex-col gap-4">
      <Link href="/purchase-orders" className="text-sm text-muted">
        ← Purchase orders
      </Link>
      <h1 className="text-2xl font-semibold">New purchase order</h1>
      <section className="card p-4">
        <Suspense fallback={<Loading />}>
          <NewForm searchParams={searchParams} />
        </Suspense>
      </section>
    </div>
  );
}

async function NewForm({ searchParams }: Pick<PageProps<"/purchase-orders/new">, "searchParams">) {
  const { product } = await searchParams;
  const initial = [product ?? []].flat().map(Number).filter(Boolean);
  const [suppliers, products] = await Promise.all([
    staffApi<Supplier[]>("/staff/suppliers"),
    staffApi<Product[]>("/staff/products"),
  ]);
  if (!suppliers.some((s) => s.is_active)) {
    return (
      <p className="text-muted">
        Add a supplier first, on the{" "}
        <Link href="/suppliers" className="text-brand">
          suppliers page
        </Link>
        .
      </p>
    );
  }
  return (
    <PurchaseOrderForm
      suppliers={suppliers}
      products={products.map(({ id, sku, name }) => ({ id, sku, name }))}
      initialProducts={initial}
    />
  );
}
