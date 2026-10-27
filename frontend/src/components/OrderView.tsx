import { rupees } from "@/lib/money";
import type { Order, OrderStatus } from "@/lib/types";

const LABELS: Record<OrderStatus, string> = {
  pending: "Waiting for payment",
  paid: "Paid",
  packing: "Being packed",
  shipped: "On its way",
  delivered: "Delivered",
  cancelled: "Cancelled",
  refunded: "Refunded",
};

const STEPS: OrderStatus[] = ["paid", "packing", "shipped", "delivered"];

export function StatusBadge({ status }: { status: OrderStatus }) {
  const tone =
    status === "cancelled" || status === "refunded"
      ? "bg-line text-muted"
      : status === "pending"
        ? "bg-accent-soft text-brand"
        : "bg-ok/15 text-ok";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>{LABELS[status]}</span>;
}

function when(iso: string) {
  return new Date(iso).toLocaleString("en-LK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Colombo" });
}

/** Paid → packing → shipped → delivered, with the time each step happened. */
export function Tracking({ order }: { order: Order }) {
  if (order.status === "pending" || order.status === "cancelled") return null;
  const reached = new Map(order.events.map((event) => [event.to_status, event.created_at]));
  const current = STEPS.indexOf(order.status);
  const shipment = order.shipment;
  return (
    <div className="card p-5">
      <ol className="grid gap-4 sm:grid-cols-4">
        {STEPS.map((step, index) => {
          const done = current >= index || reached.has(step);
          return (
            <li key={step} className="flex items-start gap-3 sm:flex-col sm:gap-2">
              <span
                className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${done ? "bg-ok text-white" : "border border-line text-muted"}`}
              >
                {done ? "✓" : index + 1}
              </span>
              <div>
                <p className={`text-sm font-medium ${done ? "" : "text-muted"}`}>{LABELS[step]}</p>
                {reached.get(step) && <p className="text-xs text-muted">{when(reached.get(step)!)}</p>}
              </div>
            </li>
          );
        })}
      </ol>
      {shipment && (
        <p className="mt-4 border-t border-line pt-4 text-sm">
          Sent with {shipment.courier}, tracking number{" "}
          <span className="font-mono font-semibold">{shipment.tracking_number}</span>
          {shipment.tracking_url && (
            <>
              {" · "}
              <a href={shipment.tracking_url} target="_blank" rel="noreferrer" className="font-medium text-brand">
                Track your parcel
              </a>
            </>
          )}
        </p>
      )}
    </div>
  );
}

export function OrderDetails({ order }: { order: Order }) {
  const address = order.shipping_address;
  return (
    <div className="grid gap-6 md:grid-cols-[1fr_18rem]">
      <section className="card p-5">
        <h2 className="mb-3 font-semibold">Items</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {order.items.map((item) => (
            <li key={item.product_id} className="flex justify-between gap-3">
              <span>
                {item.quantity} × {item.product_name}
              </span>
              <span className="font-medium">{rupees(item.line_total)}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-4 flex flex-col gap-1 border-t border-line pt-4 text-sm">
          <Line label="Items" value={rupees(order.subtotal)} />
          {order.gift_wrap && <Line label="Gift wrap" value={rupees(order.gift_wrap_fee)} />}
          <Line label="Delivery" value={Number(order.delivery_fee) ? rupees(order.delivery_fee) : "Free"} />
          <Line label="Total" value={rupees(order.total)} strong />
        </dl>
      </section>
      <section className="card p-5 text-sm">
        <h2 className="mb-2 font-semibold">Delivering to</h2>
        <p>{order.customer_name}</p>
        <p>{address.line1}</p>
        {address.line2 && <p>{address.line2}</p>}
        <p>
          {address.city}, {address.district}
        </p>
        <p className="mt-2 text-muted">{order.phone}</p>
        {order.gift_wrap && (
          <>
            <h2 className="mb-1 mt-4 font-semibold">Gift wrapped</h2>
            {order.gift_message && <p className="italic text-muted">&ldquo;{order.gift_message}&rdquo;</p>}
          </>
        )}
        <p className="mt-4 text-xs text-muted">Ordered {when(order.created_at)}</p>
      </section>
    </div>
  );
}

function Line({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between ${strong ? "text-base font-semibold" : ""}`}>
      <dt className={strong ? "" : "text-muted"}>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
