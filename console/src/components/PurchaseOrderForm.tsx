"use client";

import { useActionState, useState } from "react";

import { savePurchaseOrder, type FormState } from "@/app/actions";
import type { Product, PurchaseOrder, Supplier } from "@/lib/types";

type Row = { key: number; product_id: string; quantity: string; unit_cost: string };

type Props = {
  suppliers: Supplier[];
  products: Pick<Product, "id" | "sku" | "name">[];
  po?: PurchaseOrder;
  // Products to start with, such as the ones on the low-stock list.
  initialProducts?: number[];
};

export function PurchaseOrderForm({ suppliers, products, po, initialProducts = [] }: Props) {
  const [state, action, pending] = useActionState<FormState, FormData>(savePurchaseOrder, {});
  const start: Row[] = po
    ? po.items.map((item, i) => ({ key: i, product_id: String(item.product_id), quantity: String(item.quantity), unit_cost: item.unit_cost }))
    : initialProducts.map((id, i) => ({ key: i, product_id: String(id), quantity: "1", unit_cost: "" }));
  const [rows, setRows] = useState<Row[]>(start.length ? start : [{ key: 0, product_id: "", quantity: "1", unit_cost: "" }]);
  const [nextKey, setNextKey] = useState(rows.length);

  const update = (key: number, field: keyof Row, value: string) =>
    setRows((current) => current.map((row) => (row.key === key ? { ...row, [field]: value } : row)));
  const total = rows.reduce((sum, row) => sum + Number(row.quantity || 0) * Number(row.unit_cost || 0), 0);

  return (
    <form action={action} className="flex flex-col gap-4">
      {po && <input type="hidden" name="po_id" value={po.id} />}
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="supplier_id" className="label">
            Supplier
          </label>
          <select id="supplier_id" name="supplier_id" required defaultValue={po?.supplier.id ?? ""} className="input">
            <option value="" disabled>
              Choose a supplier
            </option>
            {suppliers
              .filter((s) => s.is_active || s.id === po?.supplier.id)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </div>
        <div>
          <label htmlFor="expected_at" className="label">
            Expected
          </label>
          <input id="expected_at" name="expected_at" type="date" defaultValue={po?.expected_at ?? ""} className="input" />
        </div>
        <div>
          <label htmlFor="notes" className="label">
            Notes
          </label>
          <input id="notes" name="notes" defaultValue={po?.notes ?? ""} className="input" />
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Product</th>
            <th className="w-28">Quantity</th>
            <th className="w-36">Unit cost (Rs)</th>
            <th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.key}>
              <td>
                <select
                  name="product_id"
                  required
                  aria-label={`Product ${i + 1}`}
                  value={row.product_id}
                  onChange={(e) => update(row.key, "product_id", e.target.value)}
                  className="input"
                >
                  <option value="" disabled>
                    Choose a product
                  </option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  name="quantity"
                  type="number"
                  min="1"
                  required
                  aria-label={`Quantity ${i + 1}`}
                  value={row.quantity}
                  onChange={(e) => update(row.key, "quantity", e.target.value)}
                  className="input"
                />
              </td>
              <td>
                <input
                  name="unit_cost"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  aria-label={`Unit cost ${i + 1}`}
                  value={row.unit_cost}
                  onChange={(e) => update(row.key, "unit_cost", e.target.value)}
                  className="input"
                />
              </td>
              <td>
                {rows.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Remove line ${i + 1}`}
                    className="text-muted hover:text-danger"
                    onClick={() => setRows((current) => current.filter((r) => r.key !== row.key))}
                  >
                    ✕
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn-outline"
          onClick={() => {
            setRows((current) => [...current, { key: nextKey, product_id: "", quantity: "1", unit_cost: "" }]);
            setNextKey(nextKey + 1);
          }}
        >
          Add line
        </button>
        <span className="ml-auto text-sm text-muted">
          Total Rs {total.toLocaleString("en-LK", { maximumFractionDigits: 2 })}
        </span>
        <button className="btn" disabled={pending}>
          {pending ? "Saving…" : po ? "Save changes" : "Save draft"}
        </button>
      </div>
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
    </form>
  );
}
