import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { PrintButton } from "@/components/PrintButton";
import { staffApi } from "@/lib/session";
import type { PickList } from "@/lib/types";

export const metadata: Metadata = { title: "Packing" };

export default function PackingPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Pick list</h1>
        <span className="ml-auto" />
        <Link href="/packing/slips" className="btn-outline print:hidden">
          All packing slips
        </Link>
        <PrintButton label="Print pick list" />
      </div>
      <Suspense fallback={<Loading />}>
        <Picks />
      </Suspense>
    </div>
  );
}

async function Picks() {
  const list = await staffApi<PickList>("/staff/pick-list");
  if (list.order_numbers.length === 0) {
    return (
      <p className="card p-8 text-center text-muted">
        No orders are being packed. Pick orders to pack from the{" "}
        <Link href="/orders" className="text-brand">
          order queue
        </Link>
        .
      </p>
    );
  }
  return (
    <>
      <p className="text-sm text-muted">
        {list.order_numbers.length} {list.order_numbers.length === 1 ? "order" : "orders"} being packed, sorted by shelf.
      </p>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-8">✓</th>
              <th>Bin</th>
              <th>Item</th>
              <th className="text-right">Take</th>
              <th>For orders</th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((item) => (
              <tr key={item.product_id}>
                <td>☐</td>
                <td className="font-mono font-semibold">{item.bin_location ?? "—"}</td>
                <td>
                  {item.name}
                  <p className="text-xs text-muted">{item.sku}</p>
                </td>
                <td className="text-right text-lg font-bold tabular-nums">{item.quantity}</td>
                <td className="text-xs">
                  {item.orders.map((o) => `${o.order_number} × ${o.quantity}`).join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-2 print:hidden">
        {list.order_numbers.map((number) => (
          <Link key={number} href={`/orders/${number}`} className="btn-outline">
            {number}
          </Link>
        ))}
      </div>
    </>
  );
}
