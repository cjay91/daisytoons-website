import type { Order } from "@/lib/types";

import { dateTime } from "@/lib/format";

/** One printed page: the address label to stick on the parcel, and the slip that goes inside. */
export function PackingSlip({ order }: { order: Order }) {
  const address = order.shipping_address;
  return (
    <article className="flex break-after-page flex-col gap-6 bg-white p-8 text-black print:p-0">
      <section className="rounded-lg border-2 border-dashed border-black p-5">
        <p className="text-xs font-semibold uppercase tracking-wide">Deliver to</p>
        <p className="mt-2 text-xl font-bold">{order.customer_name}</p>
        <p className="text-lg leading-snug">
          {address.line1}
          {address.line2 && (
            <>
              <br />
              {address.line2}
            </>
          )}
          <br />
          {address.city}, {address.district}
          {address.postal_code && ` ${address.postal_code}`}
        </p>
        <p className="mt-2 text-lg font-semibold">☎ {order.phone}</p>
        <div className="mt-4 flex items-end justify-between border-t border-black pt-3 text-sm">
          <span>
            From: Daisytoons
            {order.shipment && (
              <>
                {" "}
                · {order.shipment.courier} {order.shipment.tracking_number}
              </>
            )}
          </span>
          <span className="font-mono text-2xl font-bold">{order.order_number}</span>
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="text-2xl font-bold">Daisytoons</h2>
          <p className="text-sm">
            Order <strong>{order.order_number}</strong> · {dateTime(order.paid_at ?? order.created_at)}
          </p>
        </div>
        <table className="mt-4 w-full text-left text-sm">
          <thead>
            <tr className="border-b border-black">
              <th className="py-1 pr-2 w-10">✓</th>
              <th className="py-1 pr-2 w-14">Qty</th>
              <th className="py-1">Item</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.product_id} className="border-b border-gray-300">
                <td className="py-2 pr-2">☐</td>
                <td className="py-2 pr-2 text-lg font-bold">{item.quantity}</td>
                <td className="py-2">{item.product_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {order.gift_wrap && (
          <div className="mt-6 rounded-lg border-2 border-black p-4">
            <p className="text-sm font-bold uppercase">🎁 Gift wrap this order</p>
            {order.gift_message ? (
              <>
                <p className="mt-2 text-xs uppercase">Card message</p>
                <p className="mt-1 whitespace-pre-wrap font-serif text-lg italic">{order.gift_message}</p>
              </>
            ) : (
              <p className="mt-1 text-sm">No card message.</p>
            )}
            <p className="mt-2 text-xs">Gift order: leave prices out of the parcel.</p>
          </div>
        )}
        {order.notes && (
          <div className="mt-4 text-sm">
            <p className="font-bold">Customer note</p>
            <p className="whitespace-pre-wrap">{order.notes}</p>
          </div>
        )}
        <p className="mt-8 text-center text-sm">Thank you for shopping with Daisytoons!</p>
      </section>
    </article>
  );
}
