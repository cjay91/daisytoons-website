import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { PackingSlip } from "@/components/PackingSlip";
import { PrintButton } from "@/components/PrintButton";
import { query } from "@/lib/api";
import { loadOrder } from "@/lib/orders";
import { staffApi } from "@/lib/session";
import type { OrderList } from "@/lib/types";

export const metadata: Metadata = { title: "Packing slips" };

export default function SlipsPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center gap-3 print:hidden">
        <Link href="/packing" className="text-sm text-muted">
          ← Pick list
        </Link>
        <span className="ml-auto" />
        <PrintButton label="Print all" />
      </div>
      <Suspense fallback={<Loading />}>
        <Slips />
      </Suspense>
    </div>
  );
}

async function Slips() {
  const list = await staffApi<OrderList>(`/staff/orders${query({ status: "packing", limit: 200 })}`);
  if (list.orders.length === 0) return <p className="card p-8 text-center text-muted">No orders are being packed.</p>;
  const orders = await Promise.all(list.orders.map((o) => loadOrder(o.order_number)));
  return (
    <div className="flex flex-col gap-4 print:gap-0">
      {orders.map((order) => (
        <div key={order.order_number} className="card overflow-hidden">
          <PackingSlip order={order} />
        </div>
      ))}
    </div>
  );
}
