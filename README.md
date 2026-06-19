# Shipyard (FastAPI)

A FastAPI SaaS boilerplate with **configurable SSR + REST surfaces**, admin, user
management, multi-tenant teams, Stripe billing, and async background tasks.

Surfaces are implicit: a feature is exposed by the routers it defines —
`api.py` → REST under `/api/v1`, `views.py` → SSR HTML under `/`. Both are thin
adapters over a shared `service.py`, so business logic lives in one place.

## Stack

FastAPI · SQLAlchemy 2.0 (async) · Alembic · fastapi-users (JWT + cookie) ·
SQLAdmin · arq (Redis) · Jinja2 + HTMX · PostgreSQL · Redis · Stripe.

## Quick start (Docker)

```bash
cp .env.example .env          # edit SECRET_KEY, Stripe keys, etc.
docker compose up --build     # api + worker + postgres + redis
```

The entrypoint waits for Postgres and runs `alembic upgrade head` automatically.

- App / SSR: http://localhost:8000
- REST docs: http://localhost:8000/docs
- Admin:     http://localhost:8000/admin
- Health:    http://localhost:8000/health

## Local development

```bash
uv venv && uv pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload        # web
arq app.worker.WorkerSettings        # background worker (separate shell)
```

Create the first superuser:

```bash
python -m app.cli createsuperuser admin@example.com
```

## Project layout

```
app/
  core/       config, db, redis/arq, registry, models, health
  features/   users, teams, billing, notifications  (self-contained modules)
  admin/      SQLAdmin mount + superuser auth backend
  web/        shared Jinja layout, static, CSRF, templating
  main.py     app factory (auto-discovers + mounts features)
  worker.py   arq worker (collects tasks + cron from features)
```

## Adding a feature

Create `app/features/<name>/` with any of `models.py`, `schemas.py`,
`service.py`, and the surfaces you want — `api.py` (REST), `views.py` (SSR),
`admin.py` (admin), `tasks.py` (arq). Export a `FeatureModule` named `feature`
in `__init__.py`; the registry discovers and mounts it automatically.

See `docs/PLAN.md` for the full design.
