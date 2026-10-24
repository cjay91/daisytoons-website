import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { OrderDetails, StatusBadge, Tracking } from "@/components/OrderView";
import { requireLogin } from "@/lib/account";
import { api, ApiError } from "@/lib/api";
import type { Order } from "@/lib/types";

export const metadata: Metadata = { title: "Order", robots: { index: false } };

export default function AccountOrderPage(props: PageProps<"/account/orders/[number]">) {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <Content params={props.params} />
    </Suspense>
  );
}

async function Content({ params }: { params: PageProps<"/account/orders/[number]">["params"] }) {
  const { number } = await params;
  const token = await requireLogin(`/account/orders/${number}`);
  let order: Order;
  try {
    order = await api<Order>(`/me/orders/${encodeURIComponent(number)}`, { token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/account" className="text-sm text-brand">
          ← All orders
        </Link>
        <h2 className="text-xl font-bold">Order {order.order_number}</h2>
        <StatusBadge status={order.status} />
      </div>
      <Tracking order={order} />
      <OrderDetails order={order} />
    </div>
  );
}
