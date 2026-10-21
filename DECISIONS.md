# Decisions

Choices we may want to revisit, with the reason we made them. Newest first.

## 2026-10-21: Part 1 foundations

- **Folder names.** The storefront lives in `frontend/` (the build plan calls it `storefront/`); the staff app is `console/`.
- **Python tooling.** uv for dependencies and the lockfile, ruff for linting and formatting, pytest for tests.
- **Next.js 16 with TypeScript and Tailwind** for both web apps. The storefront runs on port 3000, the console on 3001.
- **Postgres 17 with pgvector** via the `pgvector/pgvector:pg17` image. The `vector` extension is created on first start.
- **Redis 7** is in the stack now; the job queue library (ARQ or Celery) is picked when we first need background jobs.
- **Still open:** payment gateway, courier, hosting, S3-compatible storage provider.
