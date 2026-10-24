import type { Metadata } from "next";
import { Suspense } from "react";

import { deleteAddress } from "@/app/actions";
import { AddressForm } from "@/components/AddressForm";
import { requireLogin } from "@/lib/account";
import { api } from "@/lib/api";
import { getDistricts } from "@/lib/catalog";
import type { Address } from "@/lib/types";

export const metadata: Metadata = { title: "Addresses", robots: { index: false } };

export default function AddressesPage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <Addresses />
    </Suspense>
  );
}

async function Addresses() {
  const token = await requireLogin("/account/addresses");
  const [addresses, districts] = await Promise.all([
    api<Address[]>("/me/addresses", { token }),
    getDistricts(),
  ]);
  return (
    <div className="flex flex-col gap-6">
      {addresses.map((address) => (
        <details key={address.id} className="card p-5">
          <summary className="flex cursor-pointer flex-wrap items-center gap-2">
            <span className="font-semibold">{address.label || address.recipient_name}</span>
            {address.is_default && <span className="rounded-full bg-accent-soft px-2 text-xs font-semibold">Default</span>}
            <span className="w-full text-sm text-muted sm:w-auto">
              {address.line1}, {address.city}, {address.district}
            </span>
          </summary>
          <div className="mt-4">
            <AddressForm address={address} districts={districts} />
            <form action={deleteAddress} className="mt-3">
              <input type="hidden" name="id" value={address.id} />
              <button className="text-sm text-danger underline">Delete this address</button>
            </form>
          </div>
        </details>
      ))}
      <section className="card p-5">
        <h2 className="mb-4 font-semibold">Add an address</h2>
        <AddressForm districts={districts} />
      </section>
    </div>
  );
}
