import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { purchaseOrderAction } from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { Loading } from "@/components/Loading";
import { PrintButton } from "@/components/PrintButton";
import { PurchaseOrderForm } from "@/components/PurchaseOrderForm";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/api";
import { dateTime, rupees } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { Product, PurchaseOrder, Supplier } from "@/lib/types";

export const metadata: Metadata = { title: "Purchase order" };

export default function PurchaseOrderPage({ params }: PageProps<"/purchase-orders/[id]">) {
  return (
    <div className="flex flex-col gap-4">
      <Link href="/purchase-orders" className="text-sm text-muted print:hidden">
        ← Purchase orders
      </Link>
      <Suspense fallback={<Loading />}>
        <Detail params={params} />
      </Suspense>
    </div>
  );
}

async function Detail({ params }: Pick<PageProps<"/purchase-orders/[id]">, "params">) {
  const { id } = await params;
  let po: PurchaseOrder;
  try {
    po = await staffApi<PurchaseOrder>(`/staff/purchase-orders/${Number(id)}`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
  const open = po.status === "draft" || po.status === "sent";
  const hidden = { po_id: po.id };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">PO-{po.id}</h1>
        <StatusBadge status={po.status} />
        <span className="ml-auto" />
        <PrintButton />
      </div>

      {open && (
        <div className="flex flex-wrap gap-3 print:hidden">
          {po.status === "draft" && (
            <ActionForm action={purchaseOrderAction} hidden={{ ...hidden, step: "send" }} submit="Mark sent to supplier" variant="outline" />
          )}
          <ActionForm
            action={purchaseOrderAction}
            hidden={{ ...hidden, step: "receive" }}
            submit="Goods received: add to stock"
            confirm="Add every item on this order to stock?"
          />
          <ActionForm
            action={purchaseOrderAction}
            hidden={{ ...hidden, step: "cancel" }}
            submit="Cancel"
            variant="outline"
            confirm="Cancel this purchase order?"
          />
        </div>
      )}

      <section className="card p-4">
        <div className="mb-3 grid gap-2 text-sm sm:grid-cols-3">
          <div>
            <p className="text-muted">Supplier</p>
            <p className="font-medium">{po.supplier.name}</p>
            <p className="text-muted">{[po.supplier.email, po.supplier.phone].filter(Boolean).join(" · ")}</p>
          </div>
          <div>
            <p className="text-muted">Expected</p>
            <p>{po.expected_at ?? "—"}</p>
          </div>
          <div>
            <p className="text-muted">History</p>
            <p>Created {dateTime(po.created_at)}</p>
            {po.sent_at && <p>Sent {dateTime(po.sent_at)}</p>}
            {po.received_at && <p>Received {dateTime(po.received_at)}</p>}
          </div>
        </div>
        {po.notes && <p className="mb-3 text-sm">{po.notes}</p>}
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Unit cost</th>
              <th className="text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {po.items.map((item) => (
              <tr key={item.product_id}>
                <td>{item.product.name}</td>
                <td className="font-mono text-xs">{item.product.sku}</td>
                <td className="text-right tabular-nums">{item.quantity}</td>
                <td className="text-right tabular-nums">{rupees(item.unit_cost)}</td>
                <td className="text-right tabular-nums">{rupees(item.line_total)}</td>
              </tr>
            ))}
            <tr>
              <td colSpan={4} className="text-right font-semibold">
                Total
              </td>
              <td className="text-right font-semibold tabular-nums">{rupees(po.total)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {po.status === "draft" && <EditDraft po={po} />}
    </div>
  );
}

async function EditDraft({ po }: { po: PurchaseOrder }) {
  const [suppliers, products] = await Promise.all([
    staffApi<Supplier[]>("/staff/suppliers"),
    staffApi<Product[]>("/staff/products"),
  ]);
  return (
    <details className="card p-4 print:hidden">
      <summary className="cursor-pointer font-semibold">Edit draft</summary>
      <div className="mt-4">
        <PurchaseOrderForm suppliers={suppliers} products={products.map(({ id, sku, name }) => ({ id, sku, name }))} po={po} />
      </div>
    </details>
  );
}
