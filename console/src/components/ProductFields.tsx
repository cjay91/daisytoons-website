import type { Product } from "@/lib/types";

/** Name, slug, price, description and on-sale, shared by the new and edit forms. */
export function ProductFields({ product, withSku = false }: { product?: Product; withSku?: boolean }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {withSku && (
        <div>
          <label htmlFor="sku" className="label">
            SKU
          </label>
          <input id="sku" name="sku" required maxLength={64} className="input" />
        </div>
      )}
      <div>
        <label htmlFor="name" className="label">
          Name
        </label>
        <input id="name" name="name" required maxLength={200} defaultValue={product?.name} className="input" />
      </div>
      <div>
        <label htmlFor="slug" className="label">
          Web address
        </label>
        <input
          id="slug"
          name="slug"
          required
          pattern="[a-z0-9]+(-[a-z0-9]+)*"
          title="Lowercase letters, numbers and dashes"
          defaultValue={product?.slug}
          className="input font-mono"
        />
      </div>
      <div>
        <label htmlFor="price" className="label">
          Price (Rs)
        </label>
        <input id="price" name="price" type="number" step="0.01" min="0" required defaultValue={product?.price} className="input" />
      </div>
      <div className="sm:col-span-2">
        <label htmlFor="description" className="label">
          Description
        </label>
        <textarea id="description" name="description" rows={4} defaultValue={product?.description} className="input" />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" name="is_active" defaultChecked={product?.is_active ?? true} />
        On sale in the shop
      </label>
    </div>
  );
}
