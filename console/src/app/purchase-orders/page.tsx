import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { query } from "@/lib/api";
import { dateTime, rupees } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { PurchaseOrder } from "@/lib/types";

export const metadata: Metadata = { title: "Purchase orders" };

export default function PurchaseOrdersPage({ searchParams }: PageProps<"/purchase-orders">) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Purchase orders</h1>
        <Link href="/purchase-orders/new" className="btn ml-auto">
          New purchase order
        </Link>
      </div>
      <Suspense fallback={<Loading />}>
        <List searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function List({ searchParams }: Pick<PageProps<"/purchase-orders">, "searchParams">) {
  const { status } = await searchParams;
  const current = typeof status === "string" ? status : "";
  const orders = await staffApi<PurchaseOrder[]>(`/staff/purchase-orders${query({ status: current })}`);
  return (
    <>
      <div className="flex gap-2">
        {["", "draft", "sent", "received", "cancelled"].map((s) => (
          <Link
            key={s}
            href={`/purchase-orders${query({ status: s })}`}
            className={`rounded-full border px-3 py-1 text-sm capitalize ${s === current ? "border-foreground bg-foreground text-background" : "border-line bg-surface"}`}
          >
            {s || "All"}
          </Link>
        ))}
      </div>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>PO</th>
              <th>Supplier</th>
              <th>Status</th>
              <th className="text-right">Lines</th>
              <th className="text-right">Total</th>
              <th>Expected</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((po) => (
              <tr key={po.id}>
                <td>
                  <Link href={`/purchase-orders/${po.id}`} className="font-semibold text-brand">
                    PO-{po.id}
                  </Link>
                </td>
                <td>{po.supplier.name}</td>
                <td>
                  <StatusBadge status={po.status} />
                </td>
                <td className="text-right tabular-nums">{po.items.length}</td>
                <td className="text-right tabular-nums">{rupees(po.total)}</td>
                <td>{po.expected_at}</td>
                <td className="text-muted">{dateTime(po.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {orders.length === 0 && <p className="p-6 text-center text-muted">No purchase orders.</p>}
      </div>
    </>
  );
}
