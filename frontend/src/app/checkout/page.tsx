import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { CheckoutForm } from "@/components/CheckoutForm";
import { api } from "@/lib/api";
import { getDistricts } from "@/lib/catalog";
import { rupees } from "@/lib/money";
import { getCart, getCustomer, liveToken } from "@/lib/session";
import type { Address } from "@/lib/types";

export const metadata: Metadata = { title: "Checkout", robots: { index: false } };

export default function CheckoutPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">Checkout</h1>
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <Checkout />
      </Suspense>
    </>
  );
}

async function Checkout() {
  // The cart reads cookies first, so nothing here runs at build time.
  const [cart, customer] = await Promise.all([getCart(), getCustomer()]);
  if (cart.items.length === 0) redirect("/cart");
  const districts = await getDistricts();
  const token = await liveToken();
  const addresses = token ? await api<Address[]>("/me/addresses", { token }) : [];
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_22rem]">
      <div>
        {!customer && (
          <p className="mb-4 text-sm text-muted">
            Have an account?{" "}
            <Link href="/login?next=/checkout" className="font-medium text-brand">
              Log in
            </Link>{" "}
            to use your saved address. Or just continue as a guest.
          </p>
        )}
        <CheckoutForm customer={customer} address={addresses.find((a) => a.is_default) ?? null} districts={districts} />
      </div>
      <aside className="card h-fit p-5">
        <h2 className="mb-4 font-semibold">Your order</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {cart.items.map((item) => (
            <li key={item.product_id} className="flex justify-between gap-3">
              <span>
                {item.quantity} × {item.name}
              </span>
              <span className="font-medium">{rupees(item.line_total)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-col gap-1 border-t border-line pt-4 text-sm">
          <p className="flex justify-between">
            <span className="text-muted">Items</span> {rupees(cart.subtotal)}
          </p>
          {cart.gift_wrap && (
            <p className="flex justify-between">
              <span className="text-muted">Gift wrap</span> {rupees(cart.gift_wrap_fee)}
            </p>
          )}
          <p className="flex justify-between">
            <span className="text-muted">Delivery</span>
            {Number(cart.delivery_fee_colombo) === 0 ? "Free" : "Depends on district"}
          </p>
        </div>
        <Link href="/cart" className="mt-4 inline-block text-sm text-brand">
          Edit cart
        </Link>
      </aside>
    </div>
  );
}
