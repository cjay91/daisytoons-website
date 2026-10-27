# Part 7 spec: launch, hardening and deployment

Goal: the shop is live and selling, operated by hand.

Done when: real customers place real orders, and the database can be restored from a backup.
The restore is checked on every push by `scripts/test-backup-restore.sh`, which backs up the
running stack, restores the backup into a new database and compares them. Going live needs the
accounts listed in `deploy/README.md`.

## Hosting

One server with Docker (chosen over managed services, for cost and simplicity). The files are in
`deploy/`:

| File | What it is |
| --- | --- |
| `docker-compose.prod.yml` | Caddy, the shop, the console, the API (2 processes), the worker, Postgres, Redis and backups |
| `Caddyfile` | HTTPS from Let's Encrypt, HSTS, compression; the API is public only for PayHere's notifications and health checks |
| `env.example` | Every setting the live shop needs |
| `backup/` | Nightly `pg_dump` to a private bucket, 30 days kept; `restore.sh` |
| `README.md` | Setting it up, the launch checklist, backups, monitoring, updates |

Both web apps have a production `Dockerfile` (Next.js standalone output, running as a non-root
user).

## Security

- **Rate limits** (Redis, shared by every API process), with a 429 and `Retry-After` when exceeded. If Redis is down, the limits are skipped so the shop keeps selling.

  | What | Limit |
  | --- | --- |
  | Login, per visitor and email | 10 per 15 minutes |
  | Login, per visitor | 50 per 15 minutes |
  | Sign-up, per visitor | 10 per hour |
  | Checkout, per visitor | 30 per hour |
  | Two-step codes, per staff member | 10 per 15 minutes |

  The web apps' servers pass the visitor's IP address to the API, so limits count per visitor.
- **Two-step login for staff** with an authenticator app (TOTP). It is required in production (`REQUIRE_STAFF_TWO_FACTOR`, which the API refuses to start without). Until it's set up, a staff login can only reach the setup page. Each code works once. Admins can reset it for someone who lost their phone, and there is `python -m app.cli reset-two-factor` for the last admin.
- **Headers.** `nosniff`, `X-Frame-Options: DENY` and a referrer policy on every response. HSTS comes from Caddy. No API docs in production, and no `X-Powered-By`.
- **Secrets.** In production the API refuses to start with development secrets, the fake payment gateway, or two-step login turned off. Every secret is in `deploy/.env` on the server.
- Existing protections from earlier parts still apply: Argon2 passwords, httpOnly cookies, role checks in services, PayHere signature checks, validated input everywhere.

## Monitoring

- `GET /health/ready` returns 503 if the database is unreachable or the worker hasn't run for 5 minutes. The worker records a heartbeat in Redis after each run.
- Sentry gets errors from the API and worker (Sentry SDK) and from both web apps (`instrumentation.ts`, using Sentry's HTTP API), with personal details left out.

## Policy pages

`/shipping`, `/returns`, `/privacy` and `/terms` on the shop, linked from the footer and listed in
the sitemap. They are drafts built on these assumptions:

- Delivery takes 1–2 working days in Colombo and 2–5 elsewhere, after dispatch within one working day.
- Returns are accepted within 7 days of delivery. Damaged or wrong items get a full refund including delivery. A change of mind gets the item price back, with the return postage paid by the customer. Personalised items, food and flowers can't be returned.
- Refunds go through PayHere and show up in 5–10 working days.
- The privacy page follows the Personal Data Protection Act, No. 9 of 2022: only the cookies the shop needs, and records kept up to 7 years for tax.
- The contact address is `SHOP_EMAIL` (orders@daisytoons.lk by default).

The owner should read them before launch, and have a lawyer check them if possible.

## Left for later

- Staying logged in longer than an hour (refresh tokens), still from Part 5.
- A courier integration, once a courier is chosen.
- Automatic server security updates and off-site copies of the backups bucket.
