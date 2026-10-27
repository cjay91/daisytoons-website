import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";
import { SHOP } from "@/lib/shop";

export const metadata: Metadata = {
  title: "Returns and refunds",
  description: `What to do if a ${SHOP.name} gift arrives damaged or isn't right.`,
};

export default function ReturnsPage() {
  return (
    <PolicyPage title="Returns and refunds">
      <h2>Damaged, faulty or wrong items</h2>
      <p>
        If something arrives damaged, faulty or isn&apos;t what you ordered, email us within {SHOP.returnDays} days of delivery with
        your order number and a photo. We&apos;ll send a replacement or give you a full refund, including delivery, and arrange to
        collect the item if needed.
      </p>
      <h2>Changing your mind</h2>
      <p>
        You can return unused items in their original packaging within {SHOP.returnDays} days of delivery. Email us first so we can
        tell you where to send them. Once they reach us, we refund the price of the items. Delivery fees and gift wrap aren&apos;t
        refunded, and the cost of sending the items back is yours.
      </p>
      <p>We can&apos;t take back personalised items, food, flowers or anything that has been used.</p>
      <h2>Cancelling an order</h2>
      <p>
        Email us as soon as possible. If your order hasn&apos;t been sent yet, we&apos;ll cancel it and refund you in full. Once it
        has been sent, it&apos;s treated as a return.
      </p>
      <h2>How refunds are paid</h2>
      <p>
        Refunds go back to the card or account you paid with, through our payment provider PayHere. We&apos;ll email you when we
        make the refund. Your bank usually shows it within 5 to 10 working days.
      </p>
      <p>This doesn&apos;t affect your rights under Sri Lankan consumer law.</p>
    </PolicyPage>
  );
}
