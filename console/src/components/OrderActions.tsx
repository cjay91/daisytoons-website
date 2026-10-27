import {
  cancelOrder,
  markDelivered,
  packOrder,
  refundOrder,
  resendTracking,
  resolveAttention,
  shipOrder,
} from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { rupees } from "@/lib/format";
import type { Order } from "@/lib/types";

/** The steps this person can take on the order now. The API lists them in order.actions. */
export function OrderActions({ order, couriers }: { order: Order; couriers: string[] }) {
  const can = new Set(order.actions);
  const hidden = { order_number: order.order_number };
  if (can.size === 0) return null;
  return (
    <div className="flex flex-col gap-4">
      {(can.has("pack") || can.has("deliver") || can.has("resend_tracking") || can.has("resolve_attention")) && (
        <div className="flex flex-wrap gap-3">
          {can.has("pack") && <ActionForm action={packOrder} hidden={hidden} submit="Start packing" variant="outline" />}
          {can.has("deliver") && (
            <ActionForm action={markDelivered} hidden={hidden} submit="Mark delivered" variant="outline" />
          )}
          {can.has("resend_tracking") && (
            <ActionForm action={resendTracking} hidden={hidden} submit="Email tracking again" variant="outline" pending="Sending…" />
          )}
          {can.has("resolve_attention") && (
            <ActionForm action={resolveAttention} hidden={hidden} submit="Clear attention flag" variant="outline" />
          )}
        </div>
      )}

      {can.has("ship") && (
        <section className="card p-4">
          <h2 className="mb-3 font-semibold">Ship</h2>
          <ActionForm action={shipOrder} hidden={hidden} submit="Mark shipped and email customer" pending="Shipping…">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label htmlFor="courier" className="label">
                  Courier
                </label>
                <input id="courier" name="courier" list="couriers" required defaultValue={couriers[0]} className="input" />
                <datalist id="couriers">
                  {couriers.map((courier) => (
                    <option key={courier} value={courier} />
                  ))}
                </datalist>
              </div>
              <div>
                <label htmlFor="tracking_number" className="label">
                  Tracking number
                </label>
                <input id="tracking_number" name="tracking_number" required className="input" />
              </div>
              <div>
                <label htmlFor="tracking_url" className="label">
                  Tracking link <span className="font-normal text-muted">(optional)</span>
                </label>
                <input id="tracking_url" name="tracking_url" type="url" placeholder="https://" className="input" />
              </div>
            </div>
          </ActionForm>
        </section>
      )}

      {(can.has("refund") || can.has("cancel")) && (
        <details className="card p-4">
          <summary className="cursor-pointer font-semibold">Cancel or refund</summary>
          <div className="mt-4 grid gap-6 md:grid-cols-2">
            {can.has("cancel") && (
              <ActionForm
                action={cancelOrder}
                hidden={hidden}
                submit="Cancel order"
                variant="danger"
                confirm={`Cancel order ${order.order_number}? This can't be undone.`}
              >
                <p className="text-sm text-muted">
                  {order.paid_at
                    ? `The items go back into stock and a refund of ${rupees(order.refundable)} is recorded. Make the refund in the PayHere dashboard first.`
                    : "The order hasn't been paid. Its held stock is released."}
                </p>
                <div>
                  <label htmlFor="cancel-reason" className="label">
                    Reason
                  </label>
                  <input id="cancel-reason" name="reason" required className="input" />
                </div>
                {order.paid_at && (
                  <div>
                    <label htmlFor="refund_reference" className="label">
                      PayHere refund reference
                    </label>
                    <input id="refund_reference" name="refund_reference" className="input" />
                  </div>
                )}
              </ActionForm>
            )}
            {can.has("refund") && (
              <ActionForm action={refundOrder} hidden={hidden} submit="Record refund" variant="danger" confirm="Record this refund?">
                <p className="text-sm text-muted">
                  Up to {rupees(order.refundable)} can be refunded. Make the refund in the PayHere dashboard, then record it here. A full refund marks the order refunded.
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="amount" className="label">
                      Amount (Rs)
                    </label>
                    <input id="amount" name="amount" type="number" step="0.01" min="0.01" max={order.refundable} defaultValue={order.refundable} required className="input" />
                  </div>
                  <div>
                    <label htmlFor="reference" className="label">
                      PayHere refund reference
                    </label>
                    <input id="reference" name="reference" className="input" />
                  </div>
                </div>
                <div>
                  <label htmlFor="refund-reason" className="label">
                    Reason
                  </label>
                  <input id="refund-reason" name="reason" required className="input" />
                </div>
                {order.status !== "cancelled" && (
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="restock" />
                    Put the items back in stock (full refunds only)
                  </label>
                )}
              </ActionForm>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
