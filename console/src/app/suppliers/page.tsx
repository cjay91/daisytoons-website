import type { Metadata } from "next";
import { Suspense } from "react";

import { saveSupplier } from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { Loading } from "@/components/Loading";
import { SupplierFields } from "@/components/SupplierFields";
import { staffApi } from "@/lib/session";
import type { Supplier } from "@/lib/types";

export const metadata: Metadata = { title: "Suppliers" };

export default function SuppliersPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Suppliers</h1>
      <Suspense fallback={<Loading />}>
        <Suppliers />
      </Suspense>
      <section className="card p-4">
        <h2 className="mb-3 font-semibold">Add a supplier</h2>
        <ActionForm action={saveSupplier} submit="Add supplier">
          <SupplierFields />
        </ActionForm>
      </section>
    </div>
  );
}

async function Suppliers() {
  const suppliers = await staffApi<Supplier[]>("/staff/suppliers");
  if (suppliers.length === 0) return <p className="card p-6 text-center text-muted">No suppliers yet.</p>;
  return (
    <ul className="card divide-y divide-line">
      {suppliers.map((supplier) => (
        <li key={supplier.id} className={supplier.is_active ? "" : "opacity-60"}>
          <details className="p-4">
            <summary className="flex cursor-pointer flex-wrap gap-x-4">
              <span className="font-medium">{supplier.name}</span>
              <span className="text-sm text-muted">{[supplier.email, supplier.phone].filter(Boolean).join(" · ")}</span>
              {!supplier.is_active && <span className="text-sm text-muted">(inactive)</span>}
            </summary>
            <div className="mt-3">
              <ActionForm action={saveSupplier} hidden={{ supplier_id: supplier.id }} submit="Save">
                <SupplierFields supplier={supplier} />
              </ActionForm>
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}
