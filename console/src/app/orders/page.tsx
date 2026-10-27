import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { packSelected } from "@/app/actions";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { query } from "@/lib/api";
import { dateTime, rupees } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { OrderList, OrderStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Orders" };

const PAGE_SIZE = 50;
const TABS: { label: string; params: Record<string, string> }[] = [
  { label: "To ship", params: {} },
  { label: "Needs attention", params: { view: "attention" } },
  { label: "Unpaid", params: { status: "pending" } },
  { label: "Shipped", params: { status: "shipped" } },
  { label: "Delivered", params: { status: "delivered" } },
  { label: "Cancelled", params: { status: "cancelled" } },
  { label: "Refunded", params: { status: "refunded" } },
];

export default function OrdersPage({ searchParams }: PageProps<"/orders">) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Orders</h1>
      <Suspense fallback={<Loading />}>
        <Queue searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

function one(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

async function Queue({ searchParams }: Pick<PageProps<"/orders">, "searchParams">) {
  const params = await searchParams;
  const status = one(params.status) as OrderStatus | undefined;
  const view = one(params.view);
  const q = one(params.q);
  const page = Math.max(Number(one(params.page) ?? 1) || 1, 1);
  const list = await staffApi<OrderList>(
    `/staff/orders${query({
      status,
      q,
      needs_attention: view === "attention",
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })}`,
  );
  const toShip = !status && !view && !q;
  const current = (tab: Record<string, string>) => tab.status === status && tab.view === view && !q;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((tab) => (
          <Link
            key={tab.label}
            href={`/orders${query(tab.params)}`}
            className={`rounded-full border px-3 py-1 text-sm ${current(tab.params) ? "border-foreground bg-foreground text-background" : "border-line bg-surface"}`}
          >
            {tab.label}
          </Link>
        ))}
        <Form action="/orders" className="ml-auto flex gap-2">
          <label htmlFor="order-search" className="sr-only">
            Search orders
          </label>
          <input id="order-search" name="q" defaultValue={q} placeholder="Order number, name, email or phone" className="input w-72" />
          <button className="btn-outline">Search</button>
        </Form>
      </div>

      {list.orders.length === 0 ? (
        <p className="card p-8 text-center text-muted">{toShip ? "Nothing waiting to ship. 🎉" : "No orders found."}</p>
      ) : (
        <form action={packSelected} className="flex flex-col gap-3">
          {toShip && (
            <div className="flex items-center gap-3">
              <button className="btn">Start packing selected</button>
              <span className="text-sm text-muted">Oldest first. Selected orders move to packing and go on the pick list.</span>
            </div>
          )}
          <div className="card overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  {toShip && <th className="w-8" aria-label="Select" />}
                  <th>Order</th>
                  <th>Status</th>
                  <th>Customer</th>
                  <th>District</th>
                  <th className="text-right">Items</th>
                  <th className="text-right">Total</th>
                  <th>Paid</th>
                </tr>
              </thead>
              <tbody>
                {list.orders.map((order) => (
                  <tr key={order.order_number}>
                    {toShip && (
                      <td>
                        {order.status === "paid" && (
                          <input type="checkbox" name="order" value={order.order_number} aria-label={`Select ${order.order_number}`} />
                        )}
                      </td>
                    )}
                    <td>
                      <Link href={`/orders/${order.order_number}`} className="font-semibold text-brand">
                        {order.order_number}
                      </Link>
                      {order.gift_wrap && <span className="ml-2 text-xs" title="Gift wrap">🎁</span>}
                      {order.needs_attention && (
                        <p className="mt-1 max-w-xs text-xs text-danger">{order.needs_attention}</p>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td>
                      {order.customer_name}
                      <p className="text-xs text-muted">{order.email}</p>
                    </td>
                    <td>{order.district}</td>
                    <td className="text-right tabular-nums">{order.item_count}</td>
                    <td className="text-right tabular-nums">{rupees(order.total)}</td>
                    <td className="whitespace-nowrap text-muted">{dateTime(order.paid_at ?? order.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </form>
      )}

      {list.total > PAGE_SIZE && (
        <div className="flex items-center gap-3 text-sm">
          {page > 1 && (
            <Link className="btn-outline" href={`/orders${query({ status, view, q, page: page - 1 })}`}>
              Previous
            </Link>
          )}
          <span className="text-muted">
            Page {page} of {Math.ceil(list.total / PAGE_SIZE)} · {list.total} orders
          </span>
          {page * PAGE_SIZE < list.total && (
            <Link className="btn-outline" href={`/orders${query({ status, view, q, page: page + 1 })}`}>
              Next
            </Link>
          )}
        </div>
      )}
    </>
  );
}
