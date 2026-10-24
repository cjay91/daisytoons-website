# Part 4 spec: cart, checkout and payments

Goal: a customer can pay and an order is created reliably.

Done when: a test payment creates exactly one paid order, reduces stock, and sends an email, even if the gateway sends its notification twice.

## Decisions

| Item | Choice |
| --- | --- |
| Payment gateway | PayHere hosted checkout (LKR, cards and wallets). A built-in fake gateway is used for local development and tests, because PayHere can't reach a laptop. |
| Delivery fee | Rs 400 in Colombo district, Rs 650 elsewhere in Sri Lanka, free when the goods subtotal is Rs 10,000 or more |
| Gift wrap | Rs 250 per order, optional, with a gift message of up to 300 characters |
| Reservation time | 30 minutes from checkout to payment |
| Email | SMTP. Locally, Mailpit catches every email at http://localhost:8025. A real sender is picked at launch (Part 7). |

All of these are settings, so they can change without code changes.

## Cart

- A cart belongs to a logged-in customer, or to a guest identified by a random cart token the storefront keeps and sends as the `X-Cart-Token` header.
- When a guest with a cart logs in, the guest cart's items are merged into the customer's cart.
- Items can only be added for active products, up to the stock currently available (on hand minus reserved), at most 20 of one product.
- The cart shows the live price of each product. Prices are copied into the order at checkout.

| Method and path | What it does |
| --- | --- |
| `POST /cart` | Get or create the cart. Returns the cart token for guests. |
| `GET /cart` | Items, subtotal, gift wrap fee and the delivery fee range |
| `PUT /cart/items/{product_id}` | Set a quantity (0 removes the item) |
| `PATCH /cart` | Gift wrap on or off, gift message |

## Checkout and orders

`POST /checkout` takes the contact details (email required for guests), the delivery address with its district, and uses the current cart. In one transaction it:

1. Checks every item is still active and in stock, and locks those stock rows.
2. Creates a `pending` order with a random order number (`DT-7KQ2XM`), copies of names, prices and the address, the gift options and the totals.
3. Reserves the stock (reserved goes up; on hand doesn't change yet).
4. Cancels any earlier unpaid order from the same cart, releasing its stock.

It returns the order number, a private order key for the confirmation page, and the fields the storefront posts to the payment page.

Order totals: goods subtotal + gift wrap fee + delivery fee.

### Order states

```
pending -> paid -> packing -> shipped -> delivered
pending -> cancelled            paid/packing -> cancelled
paid, packing, shipped, delivered -> refunded
```

Any other move is refused, with one exception: a payment that arrives after its order expired can move it from cancelled to paid (see below). Every move is recorded in an `order_events` table with the time and a note.

## Payment

1. The storefront posts the checkout fields to PayHere's hosted page. Card details are typed there, never on our site.
2. PayHere calls our `POST /payments/payhere/notify` with the result. We check its signature (an MD5 hash built with the merchant secret), the merchant, the amount and the currency before trusting it. Every notification is stored in `payment_events`.
3. On success (`status_code` 2) the order becomes `paid`, the reserved stock is taken off on hand (logged as a `sale` stock adjustment per item), the cart is emptied, and the confirmation email is sent.
4. On cancel or failure (-1, -2) a pending order is cancelled and its stock released.
5. The customer's browser returns to the storefront, which shows the order using the order key.

### Duplicates and races

The handler locks the order row and checks its state, so a second "paid" notification for a paid order changes nothing and sends no second email (the order records when its email was sent). A success notification for an order that already expired re-reserves the stock if it's still available and marks the order paid; if the stock is gone, the order stays cancelled and is flagged for a manual refund.

## Expiry

A small worker process checks every minute for pending orders past their 30 minutes, cancels them and releases their stock. The same job can be run by hand: `python -m app.cli release-expired-orders`.

## Tables

| Table | Change |
| --- | --- |
| `carts`, `cart_items` | New |
| `orders` | Adds customer name and phone, gift wrap, gift wrap fee, gift message, order key, cart link, expiry, paid time, payment reference, email-sent time, needs-attention flag |
| `order_events` | New: status history |
| `payment_events` | New: every gateway notification, with its raw fields |
| `stock_adjustments` | New reason: `sale` |

The delivery address uses Sri Lanka's 25 districts, so the fee can be worked out reliably.
