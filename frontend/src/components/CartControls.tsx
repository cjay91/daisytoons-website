"use client";

import { startTransition, useActionState, useRef, useState, type RefObject } from "react";

import { setQuantity, suggestGiftMessages, updateGiftOptions, type FormState, type GiftMessageState } from "@/app/actions";

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

export function GiftOptions({
  giftWrap,
  message,
  fee,
  helper,
}: {
  giftWrap: boolean;
  message: string;
  fee: string;
  helper: boolean;
}) {
  const [state, action, pending] = useActionState<FormState, FormData>(updateGiftOptions, {});
  const textarea = useRef<HTMLTextAreaElement>(null);
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
          ref={textarea}
        />
        <p className="mt-1 text-xs text-muted">Printed on a card with the wrapped gift. Up to 300 characters.</p>
      </div>
      {helper && <GiftMessageHelper textarea={textarea} />}
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

// Suggestions from the gift message agent. It sits inside the gift options form but doesn't
// submit it: the customer picks a suggestion, can edit it, and saves as usual.
function GiftMessageHelper({ textarea }: { textarea: RefObject<HTMLTextAreaElement | null> }) {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState<GiftMessageState, FormData>(suggestGiftMessages, {});
  const fields = useRef<HTMLFieldSetElement>(null);

  function suggest() {
    const form = new FormData();
    for (const input of fields.current?.querySelectorAll<HTMLInputElement | HTMLSelectElement>("[data-helper]") ?? []) {
      form.set(input.dataset.helper!, input.value);
    }
    startTransition(() => action(form));
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="self-start text-sm text-brand underline">
        Help me write it
      </button>
    );
  }
  return (
    <fieldset ref={fields} className="flex flex-col gap-2 rounded-xl bg-accent-soft p-3">
      <legend className="sr-only">Gift message ideas</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        <input data-helper="occasion" placeholder="Occasion, e.g. birthday" maxLength={100} className="input py-1.5" aria-label="Occasion" />
        <input data-helper="recipient" placeholder="Who it's for, e.g. my sister" maxLength={100} className="input py-1.5" aria-label="Who it's for" />
        <select data-helper="tone" defaultValue="warm" className="input py-1.5" aria-label="Tone">
          <option value="warm">Warm</option>
          <option value="funny">Funny</option>
          <option value="romantic">Romantic</option>
          <option value="formal">Formal</option>
          <option value="short and simple">Short and simple</option>
        </select>
        <input data-helper="details" placeholder="Anything to mention?" maxLength={500} className="input py-1.5" aria-label="Details" />
      </div>
      <button type="button" onClick={suggest} className="btn-outline self-start py-1.5" disabled={pending}>
        {pending ? "Writing…" : state.suggestions ? "Try again" : "Suggest messages"}
      </button>
      {state.error && <p className="text-sm text-danger">{state.error}</p>}
      {state.suggestions && (
        <ul className="flex flex-col gap-1.5">
          {state.suggestions.map((suggestion) => (
            <li key={suggestion}>
              <button
                type="button"
                onClick={() => {
                  if (textarea.current) textarea.current.value = suggestion;
                  textarea.current?.focus();
                }}
                className="w-full rounded-lg bg-surface p-2 text-left text-sm hover:ring-2 hover:ring-[var(--brand)]"
              >
                {suggestion}
              </button>
            </li>
          ))}
          <li className="text-xs text-muted">Pick one to use it, change it if you like, then save.</li>
        </ul>
      )}
    </fieldset>
  );
}
