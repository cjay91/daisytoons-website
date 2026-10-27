// Shop details and terms used on the policy pages and in the footer. Keep the prices in step
// with the API's settings (DELIVERY_FEE_COLOMBO, DELIVERY_FEE_OTHER, FREE_DELIVERY_OVER,
// GIFT_WRAP_FEE, RESERVATION_MINUTES in backend/app/config.py).
export const SHOP = {
  name: "Daisytoons",
  email: process.env.SHOP_EMAIL ?? "orders@daisytoons.lk",
  deliveryColombo: 400,
  deliveryOther: 650,
  freeDeliveryOver: 10000,
  giftWrap: 250,
  holdMinutes: 30,
  // Working days from dispatch.
  deliveryDaysColombo: "1–2",
  deliveryDaysOther: "2–5",
  returnDays: 7,
  policiesUpdated: "27 October 2026",
};

export const POLICIES = [
  { href: "/shipping", label: "Delivery" },
  { href: "/returns", label: "Returns and refunds" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];
