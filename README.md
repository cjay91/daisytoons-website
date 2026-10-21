# Daisytoons website

The gift shop website, kept in one repository.

## Layout

```
daisytoons-website/
├── frontend/            Storefront the customers use (Next.js)
├── console/             Staff console for orders, stock and fulfillment (Next.js)
├── backend/             API and business logic (FastAPI, Python)
├── docs/                Project documents, including the build plan
├── docker-compose.yml   Local stack: Postgres + pgvector, Redis, API
└── DECISIONS.md         Choices we may revisit
```

- **frontend/** and **console/** talk to the backend only through its API. They never reach the database directly.
- **backend/** owns the data and the rules: products, stock, orders and payment handling. Card details are taken by the payment gateway's hosted checkout page, never by our servers.

## Getting started

You need Docker, Node.js 22 and (for backend work outside Docker) [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
docker compose up
```

That starts Postgres (port 5432), Redis (6379) and the API at http://localhost:8000. Check it with http://localhost:8000/health, or browse the API docs at http://localhost:8000/docs. The API reloads when you edit files in `backend/app/`.

The web apps run outside Docker:

```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
cd console && npm install && npm run dev    # http://localhost:3001
```

## Checks

CI runs on every push (`.github/workflows/ci.yml`): backend lint, format and tests; lint, typecheck and build for both web apps; and a smoke test that starts the Compose stack and calls `/health`. To run the same checks locally, see `backend/README.md`, or run `npm run lint`, `npm run typecheck` and `npm run build` in each web app.

See `docs/Gift Shop Build Plan.pdf` for the full build plan.
