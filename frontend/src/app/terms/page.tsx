import type { Metadata } from "next";
import Link from "next/link";

import { PolicyPage } from "@/components/PolicyPage";
import { SHOP } from "@/lib/shop";

export const metadata: Metadata = {
  title: "Terms",
  description: `The terms for buying from ${SHOP.name}.`,
};

export default function TermsPage() {
  return (
    <PolicyPage title="Terms">
      <p>These terms apply when you buy from {SHOP.name}. Placing an order means you agree to them.</p>
      <h2>Prices and payment</h2>
      <p>
        Prices are in Sri Lankan rupees and include any taxes that apply. Delivery and gift wrap are shown at checkout before you
        pay. You pay online through PayHere when you place the order.
      </p>
      <h2>Your order</h2>
      <p>
        When you check out, we hold the items for {SHOP.holdMinutes} minutes while you pay. Your order is confirmed when payment
        goes through and we email you. If a payment arrives after the hold has run out and the item has sold in the meantime, we
        refund you in full.
      </p>
      <p>
        If we can&apos;t fulfil an order, for example because an item turns out to be damaged in our stock, we&apos;ll tell you
        straight away and refund you.
      </p>
      <h2>Product photos</h2>
      <p>
        We photograph our own products, but colours can look different on screens, and handmade items vary a little from piece to
        piece.
      </p>
      <h2>Delivery, returns and privacy</h2>
      <p>
        See our <Link href="/shipping" className="text-brand">delivery</Link>,{" "}
        <Link href="/returns" className="text-brand">returns and refunds</Link> and{" "}
        <Link href="/privacy" className="text-brand">privacy</Link> pages.
      </p>
      <h2>Your account</h2>
      <p>Keep your password to yourself. Tell us straight away if you think someone else has used your account.</p>
      <h2>Liability</h2>
      <p>
        If something goes wrong with an order, our responsibility is limited to replacing the item or refunding what you paid for
        it. Nothing here limits rights you have under Sri Lankan law that can&apos;t be limited.
      </p>
      <h2>Law</h2>
      <p>These terms are governed by the laws of Sri Lanka.</p>
    </PolicyPage>
  );
}
