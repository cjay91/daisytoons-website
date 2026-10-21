# backend

The API and business logic: products and inventory, orders, and payments. FastAPI on Python 3.13, managed with [uv](https://docs.astral.sh/uv/).

```
app/
├── main.py      App factory and router wiring
├── config.py    Settings, read from environment variables
├── api/         HTTP routes (thin: they call services)
└── services/    Business logic, shared by the API, console and agents
tests/           pytest suite
```

## Run locally without Docker

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The API is then at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

## Checks

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (use --check in CI)
uv run pytest                # tests
```
