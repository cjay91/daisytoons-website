import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { GiftOptions, QuantityControl } from "@/components/CartControls";
import { rupees } from "@/lib/money";
import { getAgentStatus, getCart } from "@/lib/session";

export const metadata: Metadata = { title: "Your cart", robots: { index: false } };

export default function CartPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">Your cart</h1>
      <Suspense fallback={<p className="text-muted">Loading your cart…</p>}>
        <CartContents />
      </Suspense>
    </>
  );
}

async function CartContents() {
  const [cart, assistant] = await Promise.all([getCart(), getAgentStatus()]);
  if (cart.items.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="text-muted">Your cart is empty.</p>
        <Link href="/shop" className="btn mt-4">
          Find a gift
        </Link>
      </div>
    );
  }
  const problem = cart.items.find((item) => item.quantity > item.available);
  const free = Number(cart.delivery_fee_colombo) === 0;
  const toFree = Number(cart.free_delivery_over) - Number(cart.subtotal);
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_22rem]">
      <div className="flex flex-col gap-6">
        <ul className="card divide-y divide-line">
          {cart.items.map((item) => (
            <li key={item.product_id} className="flex gap-4 p-4">
              <Link href={`/products/${item.slug}`} className="relative size-20 shrink-0 overflow-hidden rounded-xl bg-accent-soft sm:size-24">
                {item.image_url && <Image src={item.image_url} alt={item.name} fill sizes="96px" className="object-cover" />}
              </Link>
              <div className="flex flex-1 flex-col gap-2">
                <div className="flex justify-between gap-2">
                  <Link href={`/products/${item.slug}`} className="font-medium hover:text-brand">
                    {item.name}
                  </Link>
                  <span className="font-semibold">{rupees(item.line_total)}</span>
                </div>
                <p className="text-sm text-muted">{rupees(item.unit_price)} each</p>
                {item.quantity > item.available && (
                  <p className="text-sm text-danger">
                    {item.available === 0 ? "No longer available. Please remove it." : `Only ${item.available} left. Please lower the quantity.`}
                  </p>
                )}
                <QuantityControl productId={item.product_id} quantity={item.quantity} max={item.available} />
              </div>
            </li>
          ))}
        </ul>
        <GiftOptions
          giftWrap={cart.gift_wrap}
          message={cart.gift_message}
          fee={rupees(cart.gift_wrap_price)}
          helper={!!assistant?.enabled}
        />
      </div>

      <aside className="card h-fit p-5">
        <h2 className="mb-4 font-semibold">Summary</h2>
        <dl className="flex flex-col gap-2 text-sm">
          <Row label={`Items (${cart.item_count})`} value={rupees(cart.subtotal)} />
          {cart.gift_wrap && <Row label="Gift wrap" value={rupees(cart.gift_wrap_fee)} />}
          <Row
            label="Delivery"
            value={free ? "Free" : `${rupees(cart.delivery_fee_colombo)} Colombo, ${rupees(cart.delivery_fee_other)} elsewhere`}
          />
        </dl>
        {!free && toFree > 0 && (
          <p className="mt-3 rounded-lg bg-accent-soft p-2 text-xs">
            Add {rupees(toFree)} more for free delivery.
          </p>
        )}
        {problem ? (
          <p className="mt-4 text-sm text-danger">Fix the items marked above to check out.</p>
        ) : (
          <Link href="/checkout" className="btn mt-5 w-full py-3">
            Check out
          </Link>
        )}
      </aside>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}
