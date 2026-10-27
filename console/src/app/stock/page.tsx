import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { can } from "@/lib/roles";
import { requireStaff, staffApi } from "@/lib/session";
import type { LowStock } from "@/lib/types";

export const metadata: Metadata = { title: "Low stock" };

export default function StockPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Low stock</h1>
      <p className="text-sm text-muted">Products on sale whose available stock is at or below their reorder point.</p>
      <Suspense fallback={<Loading />}>
        <Low />
      </Suspense>
    </div>
  );
}

async function Low() {
  const [staff, items] = await Promise.all([requireStaff(), staffApi<LowStock[]>("/staff/stock/low")]);
  if (items.length === 0) return <p className="card p-8 text-center text-muted">Nothing needs reordering.</p>;
  const toOrder = items.filter((i) => i.on_order === 0).map((i) => String(i.product_id));
  return (
    <>
      {can(staff.role, "purchasing") && toOrder.length > 0 && (
        <Link href={`/purchase-orders/new?${toOrder.map((id) => `product=${id}`).join("&")}`} className="btn self-start">
          Order the {toOrder.length} not already on order
        </Link>
      )}
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Bin</th>
              <th className="text-right">Available</th>
              <th className="text-right">Reorder at</th>
              <th className="text-right">On hand</th>
              <th className="text-right">On order</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.product_id}>
                <td>
                  <Link href={`/products/${item.product_id}`} className="font-medium text-brand">
                    {item.name}
                  </Link>
                  <p className="font-mono text-xs text-muted">{item.sku}</p>
                </td>
                <td className="font-mono text-xs">{item.bin_location}</td>
                <td className={`text-right font-semibold tabular-nums ${item.available === 0 ? "text-danger" : ""}`}>{item.available}</td>
                <td className="text-right tabular-nums">{item.reorder_point}</td>
                <td className="text-right tabular-nums">{item.on_hand}</td>
                <td className="text-right tabular-nums">{item.on_order || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
