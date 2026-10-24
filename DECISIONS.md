# Decisions

Choices we may want to revisit, with the reason we made them. Newest first.

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
- **Still open:** payment gateway, courier, hosting, S3-compatible storage provider.
