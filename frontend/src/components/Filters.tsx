import Form from "next/form";

import type { ProductFilters } from "@/lib/catalog";
import type { Tag } from "@/lib/types";

const SORTS = [
  ["name", "Name"],
  ["newest", "Newest"],
  ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"],
] as const;

export function Filters({ tags, current }: { tags: Tag[]; current: ProductFilters }) {
  const occasions = tags.filter((tag) => tag.kind === "occasion");
  const recipients = tags.filter((tag) => tag.kind === "recipient");
  const active = Boolean(current.occasion || current.recipient || current.min_price || current.max_price);
  return (
    <details open={active || undefined} className="card group p-4 lg:open:pb-4">
      <summary className="cursor-pointer select-none text-sm font-semibold">
        Filter and sort{active ? " (on)" : ""}
      </summary>
    <Form action="/shop" className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
      <div className="sm:col-span-2">
        <label className="label" htmlFor="filter-q">
          Search
        </label>
        <input id="filter-q" name="q" type="search" defaultValue={current.q} className="input" />
      </div>
      <Select id="occasion" label="Occasion" value={current.occasion} options={occasions.map((t) => [t.slug, t.name])} />
      <Select id="recipient" label="For" value={current.recipient} options={recipients.map((t) => [t.slug, t.name])} />
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="label" htmlFor="min_price">
            Min Rs
          </label>
          <input id="min_price" name="min_price" type="number" min={0} inputMode="numeric" defaultValue={current.min_price} className="input" />
        </div>
        <div>
          <label className="label" htmlFor="max_price">
            Max Rs
          </label>
          <input id="max_price" name="max_price" type="number" min={0} inputMode="numeric" defaultValue={current.max_price} className="input" />
        </div>
      </div>
      <Select id="sort" label="Sort" value={current.sort} options={SORTS.map(([v, l]) => [v, l])} placeholder={null} />
      <div className="flex gap-2 sm:col-span-2 lg:col-span-6">
        <button className="btn">Show gifts</button>
        <a href="/shop" className="btn-outline">
          Clear
        </a>
      </div>
    </Form>
    </details>
  );
}

function Select({
  id,
  label,
  value,
  options,
  placeholder = "Any",
}: {
  id: string;
  label: string;
  value?: string;
  options: (readonly [string, string])[];
  placeholder?: string | null;
}) {
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <select id={id} name={id} defaultValue={value ?? ""} className="input">
        {placeholder !== null && <option value="">{placeholder}</option>}
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </div>
  );
}
