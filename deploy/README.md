# Going live

The whole shop runs on one server with Docker: the shop, the staff console, the API, the
background worker, Postgres, Redis, nightly backups, and Caddy in front for HTTPS. Product
photos and backups live in S3-compatible storage (Cloudflare R2 is assumed below).

What you need before you start, and roughly what each costs:

| What | Suggested | Cost |
| --- | --- | --- |
| A server: 2 CPUs, 4 GB memory, 80 GB disk, Ubuntu 24.04 | DigitalOcean (Singapore), Hetzner, Vultr | about $12–25 a month |
| A domain | daisytoons.lk from LK Domain Registry, or any registrar | yearly fee |
| Storage for photos and backups | Cloudflare R2 | free up to 10 GB |
| Sending email | Brevo, Postmark, Zoho Mail or Amazon SES | free or a few dollars a month |
| A live PayHere merchant account | payhere.lk | per-payment fee |
| Optional: error tracking | Sentry (free plan) | free |
| Optional: uptime alerts | UptimeRobot or Better Stack (free plan) | free |

## 1. Accounts and DNS

1. **Domain.** Point three DNS **A records** at the server's IP address: the shop (`daisytoons.lk`, plus `www`), `console.daisytoons.lk` and `api.daisytoons.lk`.
2. **Cloudflare R2.** Create two buckets: `daisytoons-images` (public, with a custom domain such as `images.daisytoons.lk`) and `daisytoons-backups` (private). Create two API tokens: one with read and write access to the images bucket, and one with read and write access to the backups bucket only.
3. **Email.** Set up your email service for your domain, including its SPF and DKIM DNS records so order emails don't land in spam. Note the SMTP host, port, username and password.
4. **PayHere.** In the live merchant dashboard, add your shop's domain and note the merchant ID and merchant secret. The notify URL is `https://api.daisytoons.lk/payments/payhere/notify`; the shop sends it with each payment.

## 2. The server

```bash
# As root on a fresh Ubuntu server
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

git clone https://github.com/cjay91/daisytoons-website.git /srv/daisytoons
cd /srv/daisytoons
cp deploy/env.example deploy/.env
chmod 600 deploy/.env
nano deploy/.env    # fill in every value; make secrets with: openssl rand -hex 32
```

## 3. Start it

```bash
cd /srv/daisytoons
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env ps
```

The first start takes a few minutes. Caddy gets the HTTPS certificates as soon as the DNS records
point at the server. Then:

```bash
alias dt='docker compose -f /srv/daisytoons/deploy/docker-compose.prod.yml --env-file /srv/daisytoons/deploy/.env'

# The first admin. You set up two-step login at your first console login.
dt exec api python -m app.cli create-admin --email you@daisytoons.lk --name "Your Name"

# Your products and photos, from the import/ folder (see the main README)
dt exec api python -m app.cli import-products /import/products.csv --images /import --dry-run
dt exec api python -m app.cli import-products /import/products.csv --images /import
```

## 4. Check before you announce it

- [ ] `https://daisytoons.lk` loads, with a padlock, on your phone.
- [ ] `https://api.daisytoons.lk/health/ready` says `"status":"ok"`.
- [ ] Log in to `https://console.daisytoons.lk`, set up two-step login, and add your staff.
- [ ] Place a real order for a cheap item with your own card. Check the confirmation email arrives, the order shows in the console, and you can ship it with a tracking number.
- [ ] Refund that order in the PayHere dashboard, then record the refund in the console.
- [ ] Run a backup by hand and **restore it** (below).
- [ ] Read the policy pages (`/shipping`, `/returns`, `/privacy`, `/terms`) and change anything that doesn't match how you work. The wording lives in `frontend/src/app/<page>/page.tsx` and the numbers in `frontend/src/lib/shop.ts`.

## Backups

The `backup` container dumps the database to the backups bucket at 02:30 every night and deletes
dumps older than 30 days. Product photos are already in R2, which keeps its own copies.

```bash
dt exec backup backup.sh                   # back up now
dt exec backup aws s3 ls s3://daisytoons-backups/db/ --endpoint-url "$S3_ENDPOINT_URL"
```

**Restore drill** (do this once at launch, then every few months): restore the newest backup into a
spare database and check it, without touching the live shop.

```bash
dt exec db createdb -U daisytoons restore_check
dt exec backup restore.sh latest postgresql://daisytoons:$POSTGRES_PASSWORD@db:5432/restore_check
dt exec db psql -U daisytoons -d restore_check -c "select count(*) from orders"
dt exec db dropdb -U daisytoons restore_check
```

**Restoring for real** (the database is lost or broken):

```bash
dt stop api worker storefront console
dt exec backup restore.sh latest postgresql://daisytoons:$POSTGRES_PASSWORD@db:5432/daisytoons
dt start api worker storefront console
```

`scripts/test-backup-restore.sh` runs the same backup and restore against the local stack, and CI
runs it on every push.

To be told if a night's backup doesn't happen, create a free check at healthchecks.io (expected
daily) and put its ping URL in `BACKUP_PING_URL`.

## Monitoring

- **Uptime.** In UptimeRobot or Better Stack, add checks every 5 minutes for `https://daisytoons.lk`, `https://console.daisytoons.lk/login` and `https://api.daisytoons.lk/health/ready`. The last one fails if the database is down or the background worker has stopped (the worker cancels unpaid orders and retries emails).
- **Errors.** Create a Sentry project and put its DSN in `SENTRY_DSN`. The API, the worker and both web apps report errors to it. Customers' names, emails and addresses are not sent.
- **Logs.** `dt logs -f api worker` (or any service).

## Updating the shop

```bash
cd /srv/daisytoons && git pull
dt up -d --build
```

Database migrations run automatically when the API starts. The shop is unavailable for the
minute or so it takes to restart.

## Security notes

- Only ports 80 and 443 are open. The database, Redis and the API's staff endpoints can't be reached from the internet; the API is public only for PayHere's notifications and health checks.
- Every staff account needs two-step login (an authenticator app). If someone loses their phone, an admin resets it on the Staff page, or on the server: `dt exec api python -m app.cli reset-two-factor --email them@daisytoons.lk`.
- Logins, sign-ups and checkouts are rate limited per visitor.
- `deploy/.env` holds every secret. Keep it only on the server (and in your password manager), never in git.
- Run `apt update && apt upgrade` on the server monthly, or turn on unattended upgrades.
