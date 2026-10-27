# Part 6 spec: ops console and fulfilment

Goal: the staff app in `console/` for running the shop day to day: orders, packing, shipping, stock, suppliers and sales.

Done when: a paid order can go from the queue to shipped with tracking without touching the database. This is checked on every push by `console/e2e/fulfil.mjs`. A customer pays for a gift-wrapped order, an admin logs in, packs it from the queue, reads the pick list and packing slip, ships it with a tracking number, and the tracking email arrives in Mailpit. The test then restocks a product through a purchase order and opens the sales summary.

## Who can do what

The API checks every request (`backend/app/permissions.py`). The console only hides what a role can't use.

| | Admin | Packer | Support |
| --- | :-: | :-: | :-: |
| See orders, pick lists and slips | ✓ | ✓ | ✓ |
| Pack, ship, mark delivered, resend tracking | ✓ | ✓ | |
| Clear an order's attention flag | ✓ | | ✓ |
| Cancel paid orders, record refunds | ✓ | | |
| Change stock, bin locations, reorder points; receive purchase orders | ✓ | ✓ | |
| Products, prices, tags, photos | ✓ | | |
| Suppliers and purchase orders | ✓ | | |
| Sales summary, staff accounts | ✓ | | |

## Pages

| Path | What it does |
| --- | --- |
| `/login` | Staff log in; the token is kept in an httpOnly cookie for 60 minutes |
| `/` | Counts of orders to pack, being packed and needing attention; today's sales for admins |
| `/orders` | The queue: paid orders oldest first, with tabs for other statuses, search and "Start packing selected" |
| `/orders/{number}` | Items, gift message, customer, payment, shipment, history (with who did what), and the buttons for the next steps |
| `/orders/{number}/slip` | A printable page: the address label and the packing slip with gift message |
| `/packing`, `/packing/slips` | The pick list for every order being packed, sorted by bin; all their slips to print at once |
| `/products`, `/products/new`, `/products/{id}` | Every product with stock; edit details, tags and photos; add, remove or count stock; stock history |
| `/stock` | Products at or below their reorder point, with what's already on order, and a button to order the rest |
| `/suppliers`, `/purchase-orders`, `/purchase-orders/{id}` | Suppliers; purchase orders from draft to sent to received |
| `/reports` | Daily sales in Sri Lanka time: revenue, orders, items, average order, refunds, best sellers, and the last 14 days |
| `/staff` | Staff accounts and roles |

## Order flow

```
paid ──pack──> packing ──ship (courier + tracking)──> shipped ──> delivered
  │               │                                      │           │
  └──cancel───────┴──> cancelled (stock back, refund)    └──refund───┴──> refunded
```

- **Shipping** records the courier, tracking number and an optional tracking link, then emails the customer. If the email fails, the worker retries it every minute. The storefront's order page shows the tracking number too.
- **Cancelling** an unshipped paid order puts its items back in stock (logged as "order cancelled") and records a full refund. An unpaid order just releases its held stock.
- **Refunds** can be partial (the order stays where it is) or full (the order becomes refunded). A full refund can put the items back in stock, logged as "returned" for a shipped order. Refunds can't add up to more than was paid.
- A payment that arrived after its order expired (Part 4) shows under "Needs attention"; recording its refund clears the flag.
- **Money goes back through the PayHere dashboard for now.** Staff make the refund there and record it in the console with PayHere's reference. PayHere's refund API needs its own app credentials, so connecting it is left for later.

## API additions

| Endpoint | What it does |
| --- | --- |
| `GET /staff/orders` | The queue. Filters: `status`, `q` (number, name, email, phone), `needs_attention`, `limit`, `offset` |
| `GET /staff/orders/{number}` | Full order with history, payment notifications, shipment, refunds and `actions` (what this person can do now) |
| `POST /staff/orders/pack` | Start packing several orders; safe to repeat |
| `POST /staff/orders/{number}/pack`, `/ship`, `/deliver`, `/resend-tracking` | Fulfilment steps |
| `POST /staff/orders/{number}/cancel`, `/refunds`, `/resolve-attention` | Cancellations, refunds, clearing a flag |
| `GET /staff/pick-list` | Items to pick for orders being packed (or `?order=` some), added up per product, sorted by bin |
| `GET /staff/couriers` | Couriers offered in the ship form (any other name can be typed) |
| `GET /staff/products`, `GET /staff/products/{id}` | Every product, including ones not on sale, with stock |
| `GET /staff/stock/low` | Products to reorder, with quantities on order |
| `GET/POST /staff/suppliers`, `PUT /staff/suppliers/{id}` | Suppliers |
| `GET/POST /staff/purchase-orders`, `GET/PUT /staff/purchase-orders/{id}` | Purchase orders (only drafts can be changed) |
| `POST /staff/purchase-orders/{id}/send`, `/receive`, `/cancel` | Receiving adds every item to stock, logged as "received" |
| `GET /staff/reports/daily?day=` | The daily sales summary |

## Data model

- `shipments`: one per order, with courier, tracking number and link, who shipped it, and when the customer was emailed and the parcel delivered.
- `refunds`: amount, reason, PayHere reference, whether stock went back, and who recorded it.
- `order_events.staff_id`: who made each status change (empty when the system did).
- `suppliers.is_active`, `purchase_orders.sent_at` and `received_at`.
- A new stock reason, `order_cancelled`.

## Left for later

- Courier APIs (booking pickups, live tracking, printed courier labels). Couriers are typed in for now; pick one in Part 7 and connect it.
- Refunds through the PayHere API, if the merchant account allows it.
- Partial deliveries from a supplier (today a purchase order is received in full).
