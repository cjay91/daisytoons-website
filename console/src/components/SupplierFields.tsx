import type { Supplier } from "@/lib/types";

export function SupplierFields({ supplier }: { supplier?: Supplier }) {
  const id = supplier ? `-${supplier.id}` : "";
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div>
        <label htmlFor={`name${id}`} className="label">
          Name
        </label>
        <input id={`name${id}`} name="name" required maxLength={200} defaultValue={supplier?.name} className="input" />
      </div>
      <div>
        <label htmlFor={`email${id}`} className="label">
          Email
        </label>
        <input id={`email${id}`} name="email" type="email" defaultValue={supplier?.email ?? ""} className="input" />
      </div>
      <div>
        <label htmlFor={`phone${id}`} className="label">
          Phone
        </label>
        <input id={`phone${id}`} name="phone" maxLength={32} defaultValue={supplier?.phone ?? ""} className="input" />
      </div>
      <div className="sm:col-span-3">
        <label htmlFor={`notes${id}`} className="label">
          Notes
        </label>
        <textarea id={`notes${id}`} name="notes" rows={2} defaultValue={supplier?.notes ?? ""} className="input" />
      </div>
      {supplier && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="is_active" defaultChecked={supplier.is_active} />
          Still buying from them
        </label>
      )}
    </div>
  );
}
