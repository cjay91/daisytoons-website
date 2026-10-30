# Decisions

Choices we may want to revisit, with the reason we made them. Newest first.

## 2026-10-30: Part 9 knowledge base

- **Voyage AI for embeddings** (pending the owner's choice; Anthropic recommends it for retrieval with Claude, and its free tier covers this shop). Claude has no embeddings API. The vector size is fixed at 1024, which OpenAI's models can also produce, so switching later only means re-indexing.
- **A hashing stand-in when there's no key**, so development, CI and a fresh server work without an account. It matches words, not meaning, and its scores are reported next to the real ones so the difference is visible.
- **Hybrid search with reciprocal rank fusion**, not vectors alone, because shoppers often type exact names ("teddy bear"), and keyword search also finds products before they're indexed.
- **Knowledge lives in Markdown files in the repo**, reviewed like code and indexed on deploy, rather than in the database. A test keeps the policy files in step with the storefront pages.
- **The worker re-indexes by comparing hashes every minute** instead of hooking every service that edits products, so nothing that changes a product can forget to re-index it.

## 2026-10-30: Part 8 agent harness

- **Built before the shop is live** (the owner's choice). The harness is internal and doesn't talk to customers; the plan's rule that agents are built against real data still holds for Parts 9 and 10.
- **Our own loop, not the SDK's tool runner**, because approvals pause a tool rather than run it, and every call is recorded in our own tables as it happens.
- **Claude Opus 5.5 by default**, set by `AGENT_MODEL`, with effort per agent (the test agent uses low). Costs come from a price table in `agents/model.py`; a model missing from it is costed at the highest price so limits still hold.
- **Approved tools run as the approving staff member**, so the services' own permission checks apply to them, and the audit log records both the agent run and the approver.
- **Evals run in rolled-back transactions**, so they can run against the live database with the real model without changing anything.

## 2026-10-27: Part 7 launch

- **One server with Docker** (the owner's choice), with Caddy for HTTPS, rather than managed hosting. It costs about $12–25 a month and runs the same setup as development. Moving to managed services later only means moving the containers and the database.
- **Cloudflare R2 for photos and backups**, because it's S3-compatible, has a free tier and doesn't charge for downloads. Any S3-compatible store works by changing settings.
- **Backups are nightly `pg_dump`s kept for 30 days**, not continuous archiving. At most one day of orders could be lost, which suits a small shop; PayHere and the order emails hold a second record of each sale. Revisit (WAL archiving or managed Postgres) if order volume grows.
- **Two-step login is required for every staff account, not just admins**, because packers can see customers' addresses and change stock.
- **Rate limits skip rather than block when Redis is down**, so a Redis problem can't stop sales.
- **Policy pages are drafts** written from assumptions (7-day returns, delivery times). The owner checks them before launch.

## 2026-10-27: Part 6 ops console and fulfilment

- **Couriers are typed in, not connected.** The ship form offers Domex, Pronto Lanka, Koombiyo, Prompt Xpress, Sri Lanka Post and own delivery, and takes any tracking number and link. Connecting a courier's API (pickups, live tracking, labels) waits until one is chosen in Part 7.
- **Refunds are made in the PayHere dashboard and recorded in the console**, with PayHere's reference. The console keeps the order status, stock and sales figures right.
- **Packers pack and ship; only admins cancel paid orders and refund.** Support staff can see orders and clear attention flags. Easy to change in `app/permissions.py`.
- **Cancelling an unshipped paid order puts its stock back automatically**; a refund after shipping puts stock back only if staff tick "put the items back".
- **Sales days are Sri Lanka days** (Asia/Colombo), worked out by Postgres, so the server's own time zone doesn't matter. Revenue counts on the day of payment; refunds count on the day they're recorded.
- **The console works like the storefront**: its server calls the API, and the staff token stays in an httpOnly cookie.

## 2026-10-24: Part 5 storefront

- **The storefront's server talks to the API; browsers don't.** Login and cart tokens live in httpOnly cookies set by Server Actions, so a script injected into a page can't steal them. It also means the API needs no CORS opening for the shop.
- **Catalog pages are cached for minutes, not built ahead of time.** The build never needs the API, and new products appear within a few minutes. Stock on a product page can be briefly out of date, but the cart and checkout always check live.
- **Logins last 60 minutes for now.** Refresh tokens ("stay logged in") are still to do.
- **Search is simple word matching** in names, descriptions and tags. With about 100 products that is fast and predictable; smarter search arrives with the knowledge base in Part 9.

## 2026-10-24: Part 4 cart, checkout and payments

- **PayHere is the payment gateway**: Sri Lankan, takes LKR, cards and local wallets, with a hosted payment page so card details never touch our site. Its signatures are MD5-based, which is PayHere's scheme, not our choice; we also check the merchant, amount and currency on every notification.
- **A built-in fake gateway is used locally and in tests**, because PayHere can't reach a laptop to send notifications. It signs notifications the same way PayHere does, so the real checking code runs. It is switched off when `PAYMENT_PROVIDER=payhere` and in production.
- **Delivery is Rs 400 in Colombo district, Rs 650 elsewhere, free from Rs 10,000; gift wrap is Rs 250.** All are settings. Addresses use Sri Lanka's 25 districts so the fee is never a guess.
- **Checkout holds stock for 30 minutes.** A worker process cancels unpaid orders after that. A payment that arrives late is accepted if the stock is still there, and otherwise flagged for a refund.
- **The confirmation email is sent after the payment is saved, and at most once.** If sending fails, the worker retries it.
- **Mailpit is the local email inbox.** The real email sender is picked in Part 7.

## 2026-10-21: Part 3 catalog and inventory

- **SeaweedFS is the local image store**, as an S3-compatible stand-in. MinIO was the first choice, but it no longer publishes ready-made Docker images. The code only speaks the S3 protocol (boto3), so production can use Cloudflare R2, AWS S3 or similar by changing settings. Pick the provider in Part 7.
- **Images are public URLs straight from the bucket** (`S3_PUBLIC_BASE_URL`), with long cache headers and random file names. A CDN or image resizing can sit in front later without code changes.
- **Stock on hand changes only through logged adjustments.** The Part 2 "set on_hand" field was removed from the inventory edit endpoint. Stock before the log existed got one opening log entry in the migration.
- **Tags are a fixed list staff manage** (12 occasions, 8 recipients to start), not free text, so filters stay clean. The importer rejects unknown tags instead of creating them, which catches typos.
- **The importer is all-or-nothing and matched by SKU**, so a fixed file can simply be run again.

## 2026-10-21: Part 2 data model and auth

- **Synchronous SQLAlchemy 2 with psycopg 3.** Simpler to write and test than async; FastAPI runs sync routes in a thread pool, which is plenty for about 100 products. Revisit if agent streaming needs async database access.
- **Customers log in with email and password** (chosen over emailed one-time links, which need an email provider first). Passwords are hashed with Argon2 via pwdlib.
- **Login tokens are JWTs sent as a Bearer header**, valid 60 minutes, with no refresh tokens yet. Customer and staff tokens are kept apart. Revisit (refresh tokens or cookie sessions) when the storefront and console add login screens.
- **Role checks live in services** (`app/permissions.py`), not only in routes, so the console and future agents get the same rules.
- **Status fields are VARCHAR with a CHECK constraint**, not native Postgres enums, because adding a value later is a simple migration.
- **Prices are in Sri Lankan rupees (LKR)**, stored as NUMERIC(10, 2), which holds up to Rs 99,999,999.99. Product responses include `"currency": "LKR"` so the web apps never have to guess.
- **The first admin is created from the command line**; there is no public way to become staff.

## 2026-10-21: Part 1 foundations

- **Folder names.** The storefront lives in `frontend/` (the build plan calls it `storefront/`); the staff app is `console/`.
- **Python tooling.** uv for dependencies and the lockfile, ruff for linting and formatting, pytest for tests.
- **Next.js 16 with TypeScript and Tailwind** for both web apps. The storefront runs on port 3000, the console on 3001.
- **Postgres 17 with pgvector** via the `pgvector/pgvector:pg17` image. The `vector` extension is created on first start.
- **Redis 7** is in the stack now; the job queue library (ARQ or Celery) is picked when we first need background jobs.
- **Still open:** payment gateway, courier, hosting, S3-compatible storage provider. (Since decided: PayHere in Part 4; one Docker server and Cloudflare R2 in Part 7. The courier is still open.)
