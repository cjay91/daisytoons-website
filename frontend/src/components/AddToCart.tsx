"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { addToCart, type FormState } from "@/app/actions";

export function AddToCart({ productId, available }: { productId: number; available: number }) {
  const [state, action, pending] = useActionState<FormState, FormData>(addToCart, {});
  const max = Math.min(available, 20);
  const [quantity, setQuantity] = useState(1);

  if (available === 0) {
    return <p className="rounded-xl bg-accent-soft p-4 text-sm font-medium">Sold out for now.</p>;
  }
  return (
    <form action={action} className="flex flex-col gap-3">
      <input type="hidden" name="product_id" value={productId} />
      <div className="flex items-center gap-3">
        <label htmlFor="quantity" className="text-sm font-medium">
          Quantity
        </label>
        <select
          id="quantity"
          name="quantity"
          value={quantity}
          onChange={(event) => setQuantity(Number(event.target.value))}
          className="input w-24"
        >
          {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        {available <= 5 && <span className="text-sm text-brand">Only {available} left</span>}
      </div>
      <button className="btn w-full py-3 sm:w-auto" disabled={pending}>
        {pending ? "Adding…" : "Add to cart"}
      </button>
      <p aria-live="polite" className="text-sm">
        {state.error && <span className="text-danger">{state.error}</span>}
        {state.ok && !pending && (
          <span className="text-ok">
            Added. <Link href="/cart" className="font-semibold underline">View cart</Link>
          </span>
        )}
      </p>
    </form>
  );
}
