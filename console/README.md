# console

The staff console: orders, packing, shipping, stock, suppliers, purchase orders and daily sales (and later, agent approvals). Next.js 16 with TypeScript and Tailwind. See `docs/specs/part-6-ops-console.md`.

```bash
npm install
npm run dev        # http://localhost:3001
npm run lint
npm run typecheck
npm run build
node e2e/fulfil.mjs # with the stack running, sample products imported and the console started
```

The console's server calls the API at `API_URL` (default http://localhost:8000). Set `STOREFRONT_URL` for the link to the customer's order page and `IMAGE_BASE_URL` for product photos.
