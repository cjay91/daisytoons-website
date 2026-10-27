import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { OrderActions } from "@/components/OrderActions";
import { StatusBadge } from "@/components/StatusBadge";
import { dateTime, rupees } from "@/lib/format";
import { loadOrder } from "@/lib/orders";
import { staffApi } from "@/lib/session";

export const metadata: Metadata = { title: "Order" };

export default function OrderPage({ params }: PageProps<"/orders/[number]">) {
  return (
    <div className="flex flex-col gap-4">
      <Link href="/orders" className="text-sm text-muted print:hidden">
        ← Orders
      </Link>
      <Suspense fallback={<Loading />}>
        <OrderDetail params={params} />
      </Suspense>
    </div>
  );
}

async function OrderDetail({ params }: Pick<PageProps<"/orders/[number]">, "params">) {
  const { number } = await params;
  const [order, couriers] = await Promise.all([loadOrder(number), staffApi<string[]>("/staff/couriers")]);
  const address = order.shipping_address;
  const storefront = process.env.STOREFRONT_URL ?? "http://localhost:3000";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{order.order_number}</h1>
        <StatusBadge status={order.status} />
        {order.gift_wrap && <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold">🎁 Gift wrap</span>}
        <Link href={`/orders/${order.order_number}/slip`} className="btn-outline ml-auto">
          Packing slip and label
        </Link>
      </div>

      {order.needs_attention && (
        <p role="alert" className="rounded-lg border border-danger bg-danger-soft p-3 text-sm text-danger">
          ⚠ {order.needs_attention}
        </p>
      )}

      <OrderActions order={order} couriers={couriers} />

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <h2 className="mb-2 font-semibold">Items</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Item</th>
                <th className="text-right">Qty</th>
                <th className="text-right">Price</th>
                <th className="text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.product_id}>
                  <td>
                    <Link href={`/products/${item.product_id}`} className="hover:underline">
                      {item.product_name}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums">{item.quantity}</td>
                  <td className="text-right tabular-nums">{rupees(item.unit_price)}</td>
                  <td className="text-right tabular-nums">{rupees(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="mt-3 ml-auto grid max-w-xs grid-cols-2 gap-1 text-sm">
            <dt className="text-muted">Subtotal</dt>
            <dd className="text-right tabular-nums">{rupees(order.subtotal)}</dd>
            {order.gift_wrap && (
              <>
                <dt className="text-muted">Gift wrap</dt>
                <dd className="text-right tabular-nums">{rupees(order.gift_wrap_fee)}</dd>
              </>
            )}
            <dt className="text-muted">Delivery</dt>
            <dd className="text-right tabular-nums">{Number(order.delivery_fee) ? rupees(order.delivery_fee) : "Free"}</dd>
            <dt className="font-semibold">Total</dt>
            <dd className="text-right font-semibold tabular-nums">{rupees(order.total)}</dd>
            {Number(order.refunded_total) > 0 && (
              <>
                <dt className="text-danger">Refunded</dt>
                <dd className="text-right text-danger tabular-nums">−{rupees(order.refunded_total)}</dd>
              </>
            )}
          </dl>
          {order.gift_wrap && (
            <div className="mt-4 rounded-lg bg-accent-soft p-3 text-sm">
              <p className="font-semibold">Gift message</p>
              <p className="mt-1 whitespace-pre-wrap italic">{order.gift_message || "(none)"}</p>
            </div>
          )}
          {order.notes && (
            <div className="mt-3 text-sm">
              <p className="font-semibold">Customer note</p>
              <p className="whitespace-pre-wrap">{order.notes}</p>
            </div>
          )}
        </section>

        <section className="card flex flex-col gap-3 p-4 text-sm">
          <div>
            <h2 className="font-semibold">Customer</h2>
            <p>{order.customer_name}</p>
            <p>
              <a href={`mailto:${order.email}`} className="text-brand">
                {order.email}
              </a>
            </p>
            <p>
              <a href={`tel:${order.phone}`}>{order.phone}</a>
            </p>
            <p className="text-muted">{order.customer_id ? "Has an account" : "Guest checkout"}</p>
          </div>
          <div>
            <h2 className="font-semibold">Deliver to</h2>
            <p>
              {address.line1}
              {address.line2 && <>, {address.line2}</>}
              <br />
              {address.city}, {address.district} {address.postal_code}
            </p>
          </div>
          <div>
            <h2 className="font-semibold">Payment</h2>
            <p>{order.paid_at ? `Paid ${dateTime(order.paid_at)}` : "Not paid"}</p>
            {order.payment_reference && <p className="text-muted">PayHere ref {order.payment_reference}</p>}
            {order.paid_at && (
              <p className="text-muted">
                {order.confirmation_sent_at ? `Confirmation emailed ${dateTime(order.confirmation_sent_at)}` : "Confirmation email not sent yet"}
              </p>
            )}
          </div>
          {order.shipment && (
            <div>
              <h2 className="font-semibold">Shipment</h2>
              <p>
                {order.shipment.courier} · <span className="font-mono">{order.shipment.tracking_number}</span>
              </p>
              {order.shipment.tracking_url && (
                <a href={order.shipment.tracking_url} className="text-brand" target="_blank" rel="noreferrer">
                  Track parcel
                </a>
              )}
              <p className="text-muted">
                Shipped {dateTime(order.shipment.shipped_at)}
                {order.shipment.staff && ` by ${order.shipment.staff.full_name}`}
              </p>
              <p className="text-muted">
                {order.shipment.notified_at ? `Customer emailed ${dateTime(order.shipment.notified_at)}` : "Tracking email not sent yet; it will be retried"}
              </p>
              {order.shipment.delivered_at && <p className="text-muted">Delivered {dateTime(order.shipment.delivered_at)}</p>}
            </div>
          )}
          {order.access_key && (
            <a
              href={`${storefront}/order/${order.order_number}?key=${order.access_key}`}
              target="_blank"
              rel="noreferrer"
              className="text-brand"
            >
              Customer&apos;s order page ↗
            </a>
          )}
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="mb-2 font-semibold">History</h2>
          <ol className="flex flex-col gap-2 text-sm">
            {order.events.map((event, i) => (
              <li key={i} className="flex flex-wrap gap-x-2">
                <span className="w-40 text-muted">{dateTime(event.created_at)}</span>
                <StatusBadge status={event.to_status} />
                <span>{event.note}</span>
                {event.staff && <span className="text-muted">· {event.staff.full_name}</span>}
              </li>
            ))}
          </ol>
        </section>

        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Payments and refunds</h2>
          {order.payment_events.length === 0 && order.refunds.length === 0 && <p className="text-sm text-muted">Nothing yet.</p>}
          <ul className="flex flex-col gap-2 text-sm">
            {order.payment_events.map((event, i) => (
              <li key={`p${i}`}>
                <span className="text-muted">{dateTime(event.received_at)}</span> · {event.provider} notification:{" "}
                <strong>{event.outcome.replaceAll("_", " ")}</strong>
                {event.provider_payment_id && <span className="text-muted"> ({event.provider_payment_id})</span>}
              </li>
            ))}
            {order.refunds.map((refund) => (
              <li key={`r${refund.id}`} className="text-danger">
                <span className="text-muted">{dateTime(refund.created_at)}</span> · Refund {rupees(refund.amount)}: {refund.reason}
                {refund.reference && ` (ref ${refund.reference})`}
                {refund.restocked && " · restocked"}
                {refund.staff && <span className="text-muted"> · {refund.staff.full_name}</span>}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
