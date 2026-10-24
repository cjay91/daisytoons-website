"use client";

import { useActionState } from "react";

import { saveAddress, type FormState } from "@/app/actions";
import type { Address } from "@/lib/types";

export function AddressForm({ address, districts }: { address?: Address; districts: string[] }) {
  const [state, action, pending] = useActionState<FormState, FormData>(saveAddress, {});
  const errors = state.fieldErrors ?? {};
  const field = (
    name: keyof Address,
    label: string,
    { className, ...props }: React.InputHTMLAttributes<HTMLInputElement> = {},
  ) => (
    <div className={className}>
      <label htmlFor={`${name}-${address?.id ?? "new"}`} className="label">
        {label}
      </label>
      <input
        id={`${name}-${address?.id ?? "new"}`}
        name={name}
        defaultValue={(address?.[name] as string | null) ?? ""}
        className="input"
        {...props}
      />
      {errors[name] && <p className="mt-1 text-sm text-danger">{errors[name]}</p>}
    </div>
  );
  return (
    <form action={action} className="grid gap-3 sm:grid-cols-2">
      {address && <input type="hidden" name="id" value={address.id} />}
      {field("label", "Label (optional)", { placeholder: "Home, Office" })}
      {field("recipient_name", "Recipient name", { required: true, autoComplete: "name" })}
      {field("line1", "Address", { required: true, className: "sm:col-span-2", autoComplete: "address-line1" })}
      {field("line2", "Apartment, landmark (optional)", { className: "sm:col-span-2" })}
      {field("city", "City or town", { required: true })}
      <div>
        <label htmlFor={`district-${address?.id ?? "new"}`} className="label">
          District
        </label>
        <select id={`district-${address?.id ?? "new"}`} name="district" required defaultValue={address?.district ?? ""} className="input">
          <option value="" disabled>
            Choose a district
          </option>
          {districts.map((district) => (
            <option key={district}>{district}</option>
          ))}
        </select>
      </div>
      {field("postal_code", "Postal code (optional)")}
      {field("phone", "Phone (optional)", { type: "tel" })}
      <label className="flex items-center gap-2 text-sm sm:col-span-2">
        <input type="checkbox" name="is_default" defaultChecked={address?.is_default} className="size-4" />
        Use as my default address
      </label>
      <div className="flex items-center gap-3 sm:col-span-2">
        <button className="btn" disabled={pending}>
          {pending ? "Saving…" : address ? "Save changes" : "Add address"}
        </button>
        <span aria-live="polite" className="text-sm">
          {state.error && <span className="text-danger">{state.error}</span>}
          {state.ok && !pending && <span className="text-ok">Saved</span>}
        </span>
      </div>
    </form>
  );
}
