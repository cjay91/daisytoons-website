import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/AutoRefresh";
import { OrderDetails, StatusBadge, Tracking } from "@/components/OrderView";
import { api, ApiError } from "@/lib/api";
import { liveToken } from "@/lib/session";
import type { Order } from "@/lib/types";

export const metadata: Metadata = { title: "Your order", robots: { index: false } };

export default function OrderPage(props: PageProps<"/order/[number]">) {
  return (
    <Suspense fallback={<p className="text-muted">Loading your order…</p>}>
      <OrderContent params={props.params} searchParams={props.searchParams} />
    </Suspense>
  );
}

async function loadOrder(number: string, key: string | undefined): Promise<Order | null> {
  try {
    if (key) return await api<Order>(`/orders/${encodeURIComponent(number)}?key=${encodeURIComponent(key)}`);
    const token = await liveToken();
    if (token) return await api<Order>(`/me/orders/${encodeURIComponent(number)}`, { token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
  return null;
}

async function OrderContent({
  params,
  searchParams,
}: {
  params: PageProps<"/order/[number]">["params"];
  searchParams: PageProps<"/order/[number]">["searchParams"];
}) {
  const { number } = await params;
  const { key } = await searchParams;
  const order = await loadOrder(number, typeof key === "string" ? key : undefined);
  if (!order) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">Order {order.order_number}</h1>
          <StatusBadge status={order.status} />
        </div>
        <Message order={order} />
      </div>
      {order.status === "pending" && <AutoRefresh />}
      <Tracking order={order} />
      <OrderDetails order={order} />
      <Link href="/shop" className="btn-outline w-fit">
        Keep shopping
      </Link>
    </div>
  );
}

function Message({ order }: { order: Order }) {
  if (order.status === "pending") {
    return (
      <p className="mt-2 text-muted">
        We&apos;re waiting for the payment to confirm. This page updates on its own. If you
        didn&apos;t finish paying, your items are held until the time shown on the payment page.
      </p>
    );
  }
  if (order.status === "cancelled") {
    return (
      <p className="mt-2 text-muted">
        This order was cancelled and you haven&apos;t been charged. Your cart is still saved if
        you&apos;d like to try again.
      </p>
    );
  }
  return (
    <p className="mt-2 text-muted">
      Thank you! We&apos;ve emailed a confirmation to {order.email}. Keep this page to follow
      your delivery.
    </p>
  );
}
