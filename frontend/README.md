# frontend

The customer-facing storefront: browsing and search, product pages, cart, checkout and customer accounts. Next.js 16 with TypeScript and Tailwind. See `docs/specs/part-5-storefront.md`.

It needs the API running (`docker compose up` at the repo root). Pages are rendered on this app's server, which calls the API; login and cart tokens are kept in httpOnly cookies.

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
node e2e/shop.mjs  # a full purchase in a phone-sized browser; needs the stack and sample products
```

Settings (in `.env.local` or the environment): `API_URL` (default `http://localhost:8000`), `SITE_URL` (default `http://localhost:3000`) and `IMAGE_BASE_URL` (default `http://localhost:8333/daisytoons-images`).

```
src/
├── app/            Pages (one folder per URL) and actions.ts (cart, checkout, login)
├── components/     Shared pieces: header, product grid, cart controls, checkout form
└── lib/            API client, cached catalog reads, session cookies, types
e2e/shop.mjs        End-to-end check, run in CI
```
