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
├── api/            HTTP routes (thin: they call services)
└── cli.py          Command-line tasks, such as creating the first admin
migrations/         Alembic migrations
tests/              pytest suite (needs Postgres)
```

See `docs/specs/part-2-data-model-auth.md` for the tables, endpoints and role rules.

## Run locally without Docker

Start the database with `docker compose up db` from the repo root, then:

```bash
uv sync
uv run alembic upgrade head
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
