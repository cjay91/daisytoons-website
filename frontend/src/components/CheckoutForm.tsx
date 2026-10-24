"use client";

import { useActionState, useEffect, useRef } from "react";

import { placeOrder, type CheckoutState } from "@/app/actions";
import type { Address, Customer, PaymentForm } from "@/lib/types";

type Props = {
  customer: Customer | null;
  address: Address | null;
  districts: string[];
};

export function CheckoutForm({ customer, address, districts }: Props) {
  const [state, action, pending] = useActionState<CheckoutState, FormData>(placeOrder, {});
  const errors = state.fieldErrors ?? {};

  if (state.result) {
    return <PaymentRedirect payment={state.result.payment} />;
  }

  return (
    <form action={action} className="flex flex-col gap-6">
      <fieldset className="card grid gap-4 p-5 sm:grid-cols-2">
        <legend className="px-1 font-semibold">Your details</legend>
        <Field name="customer_name" label="Full name" autoComplete="name" defaultValue={address?.recipient_name ?? customer?.full_name} error={errors.customer_name} required />
        <Field name="phone" label="Mobile number" type="tel" autoComplete="tel" defaultValue={address?.phone ?? customer?.phone ?? ""} error={errors.phone} required />
        <Field
          name="email"
          label="Email for your receipt"
          type="email"
          autoComplete="email"
          defaultValue={customer?.email}
          error={errors.email}
          required={!customer}
          className="sm:col-span-2"
        />
      </fieldset>

      <fieldset className="card grid gap-4 p-5 sm:grid-cols-2">
        <legend className="px-1 font-semibold">Delivery address</legend>
        <Field name="line1" label="Address" autoComplete="address-line1" defaultValue={address?.line1} error={errors.line1} required className="sm:col-span-2" />
        <Field name="line2" label="Apartment, landmark (optional)" autoComplete="address-line2" defaultValue={address?.line2 ?? ""} className="sm:col-span-2" />
        <Field name="city" label="City or town" autoComplete="address-level2" defaultValue={address?.city} error={errors.city} required />
        <div>
          <label htmlFor="district" className="label">
            District
          </label>
          <select id="district" name="district" required defaultValue={address?.district ?? ""} className="input">
            <option value="" disabled>
              Choose a district
            </option>
            {districts.map((district) => (
              <option key={district}>{district}</option>
            ))}
          </select>
          {errors.district && <p className="mt-1 text-sm text-danger">{errors.district}</p>}
          <p className="mt-1 text-xs text-muted">Rs 400 delivery in Colombo, Rs 650 elsewhere.</p>
        </div>
        <Field name="postal_code" label="Postal code (optional)" autoComplete="postal-code" defaultValue={address?.postal_code ?? ""} />
        <div className="sm:col-span-2">
          <label htmlFor="notes" className="label">
            Delivery notes (optional)
          </label>
          <textarea id="notes" name="notes" rows={2} maxLength={1000} className="input" />
        </div>
      </fieldset>

      {state.error && (
        <p role="alert" className="rounded-lg border border-danger p-3 text-sm text-danger">
          {state.error}
        </p>
      )}
      <button className="btn py-3 text-base" disabled={pending}>
        {pending ? "Placing order…" : "Continue to payment"}
      </button>
      <p className="text-center text-xs text-muted">
        You&apos;ll pay securely on PayHere. We hold your items for 30 minutes while you pay.
      </p>
    </form>
  );
}

function Field({
  name,
  label,
  error,
  className = "",
  ...input
}: { name: string; label: string; error?: string; className?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={className}>
      <label htmlFor={name} className="label">
        {label}
      </label>
      <input id={name} name={name} className="input" aria-invalid={Boolean(error)} {...input} />
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
    </div>
  );
}

/** Posts the payment fields to the payment page, the way the gateway expects. */
function PaymentRedirect({ payment }: { payment: PaymentForm }) {
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    form.current?.submit();
  }, []);
  return (
    <form ref={form} method="post" action={payment.action_url} className="card p-8 text-center">
      {Object.entries(payment.fields).map(([name, value]) => (
        <input key={name} type="hidden" name={name} value={value} />
      ))}
      <p className="font-medium">Taking you to the secure payment page…</p>
      <button className="btn mt-4">Continue to payment</button>
    </form>
  );
}
