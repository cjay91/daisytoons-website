import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";
import { rupees } from "@/lib/money";
import { SHOP } from "@/lib/shop";

export const metadata: Metadata = {
  title: "Delivery",
  description: `How ${SHOP.name} delivers across Sri Lanka, what it costs and how long it takes.`,
};

export default function ShippingPage() {
  return (
    <PolicyPage title="Delivery">
      <p>We deliver to every district in Sri Lanka.</p>
      <h2>What it costs</h2>
      <ul>
        <li>Colombo district: {rupees(SHOP.deliveryColombo)}</li>
        <li>Everywhere else: {rupees(SHOP.deliveryOther)}</li>
        <li>Free on orders over {rupees(SHOP.freeDeliveryOver)}</li>
        <li>Gift wrap with a handwritten card: {rupees(SHOP.giftWrap)} per order</li>
      </ul>
      <p>You see the delivery fee at checkout before you pay.</p>
      <h2>How long it takes</h2>
      <p>
        We pack and send orders within one working day of payment. After that, delivery usually takes {SHOP.deliveryDaysColombo}{" "}
        working days in Colombo and {SHOP.deliveryDaysOther} working days elsewhere. Around holidays such as Avurudu and Christmas
        it can take a little longer, so order early.
      </p>
      <h2>Tracking</h2>
      <p>
        When your order leaves us, we email you the courier&apos;s name and tracking number. You can also see them on your order
        page, from the link in your confirmation email or in your account.
      </p>
      <h2>Sending a gift</h2>
      <p>
        Gift orders go out without prices in the parcel. Add your message at checkout and we&apos;ll write it on the card. Please
        give a phone number the courier can reach, as they may call before delivering.
      </p>
      <h2>If no one is home</h2>
      <p>
        The courier will usually call and try again. If a parcel comes back to us because the address was wrong or no one could
        be reached, we&apos;ll contact you to arrange another delivery, which may cost another delivery fee.
      </p>
    </PolicyPage>
  );
}
