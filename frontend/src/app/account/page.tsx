import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { StatusBadge } from "@/components/OrderView";
import { requireLogin } from "@/lib/account";
import { api } from "@/lib/api";
import { rupees } from "@/lib/money";
import type { OrderSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Your orders", robots: { index: false } };

export default function AccountPage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading your orders…</p>}>
      <Orders />
    </Suspense>
  );
}

async function Orders() {
  const token = await requireLogin("/account");
  const orders = await api<OrderSummary[]>("/me/orders", { token });
  if (orders.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="text-muted">No orders yet.</p>
        <Link href="/shop" className="btn mt-4">
          Find a gift
        </Link>
      </div>
    );
  }
  return (
    <ul className="card divide-y divide-line">
      {orders.map((order) => (
        <li key={order.order_number}>
          <Link href={`/account/orders/${order.order_number}`} className="flex flex-wrap items-center gap-3 p-4 hover:bg-accent-soft/50">
            <span className="font-semibold">{order.order_number}</span>
            <StatusBadge status={order.status} />
            <span className="text-sm text-muted">
              {new Date(order.created_at).toLocaleDateString("en-LK", { dateStyle: "medium", timeZone: "Asia/Colombo" })} ·{" "}
              {order.item_count} {order.item_count === 1 ? "item" : "items"}
            </span>
            <span className="ml-auto font-medium">{rupees(order.total)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
