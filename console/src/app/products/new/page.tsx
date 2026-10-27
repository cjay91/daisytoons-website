import type { Metadata } from "next";
import Link from "next/link";

import { createProduct } from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { ProductFields } from "@/components/ProductFields";

export const metadata: Metadata = { title: "New product" };

export default function NewProductPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Link href="/products" className="text-sm text-muted">
        ← Products
      </Link>
      <h1 className="text-2xl font-semibold">New product</h1>
      <section className="card p-4">
        <ActionForm action={createProduct} submit="Create product" pending="Creating…">
          <ProductFields withSku />
        </ActionForm>
      </section>
      <p className="text-sm text-muted">Add photos, tags and stock after creating it.</p>
    </div>
  );
}
