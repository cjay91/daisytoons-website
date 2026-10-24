# backend

The API and business logic: products and inventory, orders, and payments. FastAPI on Python 3.13, managed with [uv](https://docs.astral.sh/uv/). Data lives in Postgres through SQLAlchemy 2, with Alembic for migrations.

```
app/
├── main.py         App factory and router wiring
├── config.py       Settings, read from environment variables
├── db.py           Database engine and sessions
├── models/         SQLAlchemy models (tables)
├── schemas.py      Request and response bodies
├── services/       Business logic, shared by the API, console and agents
├── permissions.py  Which staff role may do what
├── security.py     Password hashing and login tokens
├── errors.py       App errors and the shared JSON error shape
├── storage.py      Image storage (S3-compatible), plus an in-memory version for tests
├── images.py       Checks an upload really is a JPEG, PNG or WebP
├── importer.py     The CSV product import
├── text.py         Helpers such as making a slug from a name
├── pricing.py      Delivery and gift wrap charges, Sri Lanka's districts
├── payhere.py      PayHere payment form hash and notification signature checks
├── email.py        Outgoing email (SMTP), plus an in-memory version for tests
├── worker.py       Background jobs: expire unpaid orders, retry failed emails
├── api/            HTTP routes (thin: they call services)
└── cli.py          Command-line tasks: create-admin, init-storage, import-products,
                    release-expired-orders
migrations/         Alembic migrations
tests/              pytest suite (needs Postgres)
```

The specs in `docs/specs/` list the tables, endpoints and role rules for each part.

## Run locally without Docker

Start the database and image storage with `docker compose up db storage` from the repo root, then:

```bash
uv sync
uv run alembic upgrade head
uv run python -m app.cli init-storage
uv run uvicorn app.main:app --reload
```

The API is then at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

## Create the first admin

```bash
uv run python -m app.cli create-admin --email you@example.com --name "Your Name"
# or, with the Docker stack running:
docker compose exec api python -m app.cli create-admin --email you@example.com --name "Your Name"
```

It asks for a password (or reads `ADMIN_PASSWORD`). Admins add other staff through `POST /staff/members`.

## Import products

```bash
uv run python -m app.cli import-products ../docs/templates/products-sample.csv \
    --images ../docs/templates/sample-images --dry-run
```

Drop `--dry-run` to save. The columns and rules are in `docs/specs/part-3-catalog-inventory.md`; start from `docs/templates/products-template.csv`. If any row has a problem, nothing is imported and every problem is listed with its line number. Running the same file again updates products by SKU and only logs real stock changes.

## Changing the database

1. Edit or add models in `app/models/`.
2. Generate a migration: `uv run alembic revision --autogenerate -m "add gift wrap to orders"`.
3. Read the generated file in `migrations/versions/` and fix anything autogenerate got wrong.
4. Apply it: `uv run alembic upgrade head`.

The test suite fails if a model changes without a matching migration.

## Checks

The tests need Postgres running (`docker compose up db`). They create and drop their own `daisytoons_test` databases; set `TEST_DATABASE_URL` to use a different server.

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (use --check in CI)
uv run pytest                # tests
```
