# Decisions

Choices we may want to revisit, with the reason we made them. Newest first.

## 2026-10-21: Part 2 data model and auth

- **Synchronous SQLAlchemy 2 with psycopg 3.** Simpler to write and test than async; FastAPI runs sync routes in a thread pool, which is plenty for about 100 products. Revisit if agent streaming needs async database access.
- **Customers log in with email and password** (chosen over emailed one-time links, which need an email provider first). Passwords are hashed with Argon2 via pwdlib.
- **Login tokens are JWTs sent as a Bearer header**, valid 60 minutes, with no refresh tokens yet. Customer and staff tokens are kept apart. Revisit (refresh tokens or cookie sessions) when the storefront and console add login screens.
- **Role checks live in services** (`app/permissions.py`), not only in routes, so the console and future agents get the same rules.
- **Status fields are VARCHAR with a CHECK constraint**, not native Postgres enums, because adding a value later is a simple migration.
- **Money is NUMERIC(10, 2)** in a single shop currency. The currency itself is still to be confirmed.
- **The first admin is created from the command line**; there is no public way to become staff.

## 2026-10-21: Part 1 foundations

- **Folder names.** The storefront lives in `frontend/` (the build plan calls it `storefront/`); the staff app is `console/`.
- **Python tooling.** uv for dependencies and the lockfile, ruff for linting and formatting, pytest for tests.
- **Next.js 16 with TypeScript and Tailwind** for both web apps. The storefront runs on port 3000, the console on 3001.
- **Postgres 17 with pgvector** via the `pgvector/pgvector:pg17` image. The `vector` extension is created on first start.
- **Redis 7** is in the stack now; the job queue library (ARQ or Celery) is picked when we first need background jobs.
- **Still open:** payment gateway, courier, hosting, S3-compatible storage provider.
