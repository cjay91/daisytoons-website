import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { adjustStock, setProductTags, updateImage, updateInventory, updateProduct, uploadImage } from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { Loading } from "@/components/Loading";
import { ProductFields } from "@/components/ProductFields";
import { ApiError } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { can } from "@/lib/roles";
import { requireStaff, staffApi } from "@/lib/session";
import type { Product, StockAdjustment, Tag } from "@/lib/types";

export const metadata: Metadata = { title: "Product" };

const REASONS = [
  { value: "received", label: "Received from supplier" },
  { value: "damaged", label: "Damaged" },
  { value: "returned", label: "Returned by customer" },
  { value: "correction", label: "Correction" },
];

const REASON_LABELS: Record<string, string> = {
  received: "Received",
  count: "Stock count",
  damaged: "Damaged",
  returned: "Returned",
  correction: "Correction",
  import: "Import",
  sale: "Sale",
  order_cancelled: "Order cancelled",
};

export default function ProductPage({ params }: PageProps<"/products/[id]">) {
  return (
    <div className="flex flex-col gap-4">
      <Link href="/products" className="text-sm text-muted">
        ← Products
      </Link>
      <Suspense fallback={<Loading />}>
        <ProductDetail params={params} />
      </Suspense>
    </div>
  );
}

async function load(id: string) {
  try {
    return await Promise.all([
      staffApi<Product>(`/staff/products/${Number(id)}`),
      staffApi<StockAdjustment[]>(`/staff/products/${Number(id)}/stock-adjustments`),
      staffApi<Tag[]>("/tags"),
    ]);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
}

async function ProductDetail({ params }: Pick<PageProps<"/products/[id]">, "params">) {
  const { id } = await params;
  const [staff, [product, adjustments, tags]] = await Promise.all([requireStaff(), load(id)]);
  // Admins edit products; admins and packers manage stock (see backend/app/permissions.py).
  const editCatalog = staff.role === "admin";
  const editStock = can(staff.role, "stock");
  const hidden = { product_id: product.id };
  const inventory = product.inventory;
  const has = new Set(product.tags.map((t) => t.id));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-2xl font-semibold">{product.name}</h1>
        <span className="font-mono text-sm text-muted">{product.sku}</span>
        {!product.is_active && <span className="text-sm text-muted">(not on sale)</span>}
      </div>

      <section className="card grid gap-4 p-4 sm:grid-cols-4">
        {[
          ["On hand", inventory?.on_hand ?? 0],
          ["Reserved for unpaid orders", inventory?.reserved ?? 0],
          ["Available to sell", product.available],
          ["Reorder at", inventory?.reorder_point ?? 0],
        ].map(([label, value]) => (
          <div key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="text-2xl font-semibold tabular-nums">{value}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        {editStock && (
          <section className="card p-4">
            <h2 className="mb-3 font-semibold">Change stock</h2>
            <ActionForm action={adjustStock} hidden={hidden} submit="Update stock">
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" name="kind" value="change" defaultChecked /> Add or remove
                </label>
                <label className="flex items-center gap-2">
                  <input type="radio" name="kind" value="count" /> Set to a count
                </label>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="amount" className="label">
                    Amount
                  </label>
                  <input id="amount" name="amount" type="number" required className="input" placeholder="12, or −2" />
                </div>
                <div>
                  <label htmlFor="reason" className="label">
                    Reason <span className="font-normal text-muted">(add or remove)</span>
                  </label>
                  <select id="reason" name="reason" className="input">
                    {REASONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="note" className="label">
                  Note
                </label>
                <input id="note" name="note" maxLength={1000} className="input" />
              </div>
            </ActionForm>
            <hr className="my-4 border-line" />
            <ActionForm action={updateInventory} hidden={hidden} submit="Save shelf details" variant="outline">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="bin_location" className="label">
                    Bin location
                  </label>
                  <input id="bin_location" name="bin_location" maxLength={50} defaultValue={inventory?.bin_location ?? ""} className="input font-mono" />
                </div>
                <div>
                  <label htmlFor="reorder_point" className="label">
                    Reorder when available is at or below
                  </label>
                  <input id="reorder_point" name="reorder_point" type="number" min="0" defaultValue={inventory?.reorder_point ?? 0} className="input" />
                </div>
              </div>
            </ActionForm>
          </section>
        )}

        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Stock history</h2>
          <div className="max-h-96 overflow-y-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Reason</th>
                  <th className="text-right">Change</th>
                  <th className="text-right">After</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {adjustments.map((a) => (
                  <tr key={a.id}>
                    <td className="whitespace-nowrap text-muted">{dateTime(a.created_at)}</td>
                    <td>{REASON_LABELS[a.reason] ?? a.reason}</td>
                    <td className={`text-right tabular-nums ${a.quantity_change < 0 ? "text-danger" : "text-ok"}`}>
                      {a.quantity_change > 0 ? `+${a.quantity_change}` : a.quantity_change}
                    </td>
                    <td className="text-right tabular-nums">{a.on_hand_after}</td>
                    <td className="text-muted">{a.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {adjustments.length === 0 && <p className="p-3 text-sm text-muted">No changes yet.</p>}
          </div>
        </section>
      </div>

      {editCatalog && (
        <>
          <section className="card p-4">
            <h2 className="mb-3 font-semibold">Details</h2>
            <ActionForm action={updateProduct} hidden={hidden} submit="Save details">
              <ProductFields product={product} />
            </ActionForm>
          </section>

          <section className="card p-4">
            <h2 className="mb-3 font-semibold">Occasions and recipients</h2>
            <ActionForm action={setProductTags} hidden={hidden} submit="Save tags">
              {(["occasion", "recipient"] as const).map((kind) => (
                <fieldset key={kind}>
                  <legend className="label capitalize">{kind}s</legend>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                    {tags
                      .filter((t) => t.kind === kind)
                      .map((tag) => (
                        <label key={tag.id} className="flex items-center gap-1.5">
                          <input type="checkbox" name={`${kind}s`} value={tag.slug} defaultChecked={has.has(tag.id)} />
                          {tag.name}
                        </label>
                      ))}
                  </div>
                </fieldset>
              ))}
            </ActionForm>
          </section>

          <section className="card p-4">
            <h2 className="mb-3 font-semibold">Photos</h2>
            <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {product.images.map((image, i) => (
                <div key={image.id} className="flex flex-col gap-2">
                  <Image src={image.url} alt={image.alt_text} width={240} height={240} className="aspect-square w-full rounded-lg object-cover" />
                  <ActionForm
                    action={updateImage}
                    hidden={{ ...hidden, image_id: image.id }}
                    submit="Save"
                    variant="outline"
                    className="flex flex-col gap-2"
                  >
                    <input name="alt_text" defaultValue={image.alt_text} placeholder="Describe the photo" aria-label="Photo description" className="input" />
                    <div className="flex gap-3 text-xs">
                      {i > 0 && (
                        <label className="flex items-center gap-1">
                          <input type="radio" name="intent" value="first" /> Make main photo
                        </label>
                      )}
                      <label className="flex items-center gap-1 text-danger">
                        <input type="radio" name="intent" value="delete" /> Delete
                      </label>
                    </div>
                  </ActionForm>
                </div>
              ))}
            </div>
            <ActionForm action={uploadImage} hidden={hidden} submit="Upload photo" pending="Uploading…" variant="outline">
              <div className="grid gap-3 sm:grid-cols-2">
                <input name="file" type="file" accept="image/jpeg,image/png,image/webp" required aria-label="Photo" className="text-sm" />
                <input name="alt_text" placeholder="Describe the photo" aria-label="Photo description" className="input" />
              </div>
            </ActionForm>
          </section>
        </>
      )}
    </div>
  );
}
