# dfbox-dcm-be

FastAPI backend for the Digital Factory Delivery & Capacity Manager.

## Scope

This repository contains the backend foundation required before domain implementation:

- FastAPI application factory
- `/health` readiness endpoint
- `/api/v1` API boundary
- Pydantic settings loaded from environment
- async SQLAlchemy session foundation
- Alembic migration foundation
- correlation ID and structured request logging
- RFC 9457-style problem details for HTTP errors
- test layout and Docker image

Project/domain endpoints, Graph group resolution, Jira integration, and business migrations are intentionally deferred to their implementation agents and accepted decisions.

## Local development

```bash
uv sync --dev
uv run uvicorn app.main:app --reload
```

The service is available at `http://localhost:8000` and OpenAPI at `/docs`.

## Tests and checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

## Configuration

Required production settings are supplied through environment variables. Never commit `.env` files or credentials. See `.env.example` for local names only.
