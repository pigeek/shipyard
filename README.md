# Shipyard (FastAPI)

A FastAPI SaaS boilerplate with **configurable SSR + REST surfaces**, admin, user
management, multi-tenant teams, Stripe billing, and async background tasks.

Surfaces are implicit: a feature is exposed by the routers it defines —
`api.py` → REST under `/api/v1`, `views.py` → SSR HTML under `/`. Both are thin
adapters over a shared `service.py`, so business logic lives in one place.

## Use this as a template

This repo is a **seed**: kick off a new project from it without forking the name.

1. Click **Use this template** on GitHub (or `gh repo create my-app --template <owner>/shipyard`).
   The template button gives the new repo a fresh, single-commit history.
2. Clone it and run the one-shot bootstrap, then delete the script:

   ```bash
   python scripts/init.py --name my-app --display "My App"
   rm scripts/init.py
   ```

`scripts/init.py` renames `shipyard`/`Shipyard` (package, DB, S3 bucket, auth
cookie, app name) across every tracked file, resets the version to `0.1.0`,
writes a `.env` from `.env.example` with a freshly generated `SECRET_KEY`, and
clears the seed's project-status note. Pass `--fresh-git` if you cloned rather
than using the template button and want a clean history. It only touches
git-tracked files and prints exactly what it changed.

## Stack

FastAPI · SQLAlchemy 2.0 (async) · Alembic · fastapi-users (JWT + cookie) ·
SQLAdmin · arq (Redis) · Jinja2 + HTMX · PostgreSQL · Redis · Stripe ·
Vite + React SPA (`/app`).

## Auth & frontends

One identity core, multiple shells (see `docs/adr/0001-frontend-auth-shells.md`):

- **SSR** (Jinja+HTMX) on a httpOnly cookie session, plus a same-origin **React
  SPA at `/app`** on the same cookie — no token in JS.
- **Bearer + refresh tokens** for mobile/native/third-party, with server-side
  revocation (`/api/v1/auth/jwt/{login,refresh,logout,logout-all}`).
- **Transport-aware CSRF**: cookie-authenticated `/api/v1` mutations need a
  double-submit `X-CSRF-Token`; bearer requests are exempt.
- Active transports, CORS origins, and OAuth providers are all **configuration**
  (`.env`); a provider/transport with no config simply isn't mounted.

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

### Frontend (React SPA at `/app`)

The SPA is a Vite + React bundle served same-origin by FastAPI. Build it (the
Docker image and CI do this automatically):

```bash
npm --prefix frontend install
npm --prefix frontend run build      # → app/web/spa (served at /app)
npm --prefix frontend run dev        # or: Vite dev server, proxying /api to :8000
```

If the bundle isn't built, `/app` simply 404s and the SPA tests skip — the SSR
site is fully functional on its own.

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
