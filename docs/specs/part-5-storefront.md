# Part 5 spec: storefront

Goal: the customer-facing site in Next.js.

Done when: a customer can find a gift on a phone, pay, and track the order end to end. This is checked on every push by `frontend/e2e/shop.mjs`, which runs in a phone-sized browser against the full stack.

## Pages

| Path | What it shows |
| --- | --- |
| `/` | Hero, occasion and recipient shortcuts, newest gifts |
| `/shop` | Keyword search with filters: occasion, recipient, price range, sort |
| `/occasions`, `/occasions/{slug}`, `/for/{slug}` | Gifts by occasion or by who they're for |
| `/products/{slug}` | Photos, price, stock left, add to cart, tags |
| `/cart` | Quantities, remove, gift wrap and message, delivery fees, free-delivery nudge |
| `/checkout` | Contact and delivery details (prefilled from a saved address), then the hand-off to the payment page |
| `/order/{number}?key=…` | Confirmation and tracking. Refreshes itself while a payment is confirming |
| `/login`, `/register` | Customer accounts with a password |
| `/account`, `/account/orders/{number}`, `/account/addresses` | Order history, tracking, saved addresses |

## How it talks to the API

- The browser never calls the API directly. Pages are rendered on the storefront's server, and changes (add to cart, check out, log in) are Server Actions.
- The login token and the cart token are kept in **httpOnly cookies**, so page scripts can't read them.
- Catalog reads (products, tags, districts) are cached for a few minutes. The cart, checkout and account pages are always live.
- Checkout returns the payment form; the browser posts it to PayHere (or the fake gateway locally).

## API additions

| Endpoint | Change |
| --- | --- |
| `GET /products` | Adds `q` (every word must match the name, description or a tag), `min_price`, `max_price`, `sort` (`name`, `newest`, `price_asc`, `price_desc`), and `available` on each product |
| `GET /me/orders`, `GET /me/orders/{number}` | A customer's own orders, with the status history used for tracking |
| `GET/POST /me/addresses`, `PUT/DELETE /me/addresses/{id}` | Saved addresses with a district; the first one is the default, and only one can be |

## Mobile and SEO

- Mobile-first layout; the search box sits under the header on phones.
- Page titles and descriptions, product Open Graph images, product structured data (schema.org Product with price and stock), `sitemap.xml` built from the live catalog, and `robots.txt` keeping cart, checkout and account pages out of search results.
- Product photos go through Next.js image optimisation (resized and served in modern formats).

## Left for later

- Staying logged in longer than an hour (refresh tokens). Today the login lasts 60 minutes; after that the customer is treated as a guest until they log in again.
- Shipment tracking numbers from a courier arrive with Part 6. Until then tracking shows the order's status steps.
