"use client";

import { startTransition, useActionState } from "react";

import { setQuantity, updateGiftOptions, type FormState } from "@/app/actions";

export function QuantityControl({ productId, quantity, max }: { productId: number; quantity: number; max: number }) {
  const [state, action, pending] = useActionState<FormState, FormData>(setQuantity, {});
  const limit = Math.max(Math.min(max, 20), quantity);
  return (
    <form action={action} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="product_id" value={productId} />
      <label className="sr-only" htmlFor={`qty-${productId}`}>
        Quantity
      </label>
      <select
        id={`qty-${productId}`}
        name="quantity"
        defaultValue={quantity}
        disabled={pending}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
        className="input w-20 py-1.5"
      >
        {Array.from({ length: limit }, (_, i) => i + 1).map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      <button formAction={remove} className="text-sm text-muted underline hover:text-danger" disabled={pending}>
        Remove
      </button>
      {state.error && <p className="w-full text-sm text-danger">{state.error}</p>}
    </form>
  );

  function remove(form: FormData) {
    form.set("quantity", "0");
    startTransition(() => action(form));
  }
}

export function GiftOptions({ giftWrap, message, fee }: { giftWrap: boolean; message: string; fee: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(updateGiftOptions, {});
  return (
    <form action={action} className="card flex flex-col gap-3 p-4">
      <label className="flex items-center gap-3 font-medium">
        <input type="checkbox" name="gift_wrap" defaultChecked={giftWrap} className="size-5 accent-[var(--brand)]" />
        Gift wrap this order ({fee})
      </label>
      <div>
        <label htmlFor="gift_message" className="label">
          Gift message (optional)
        </label>
        <textarea
          id="gift_message"
          name="gift_message"
          maxLength={300}
          rows={3}
          defaultValue={message}
          placeholder="Happy birthday! Love, Amma"
          className="input"
        />
        <p className="mt-1 text-xs text-muted">Printed on a card with the wrapped gift. Up to 300 characters.</p>
      </div>
      <div className="flex items-center gap-3">
        <button className="btn-outline" disabled={pending}>
          {pending ? "Saving…" : "Save gift options"}
        </button>
        <span aria-live="polite" className="text-sm">
          {state.error && <span className="text-danger">{state.error}</span>}
          {state.ok && !pending && <span className="text-ok">Saved</span>}
        </span>
      </div>
    </form>
  );
}
