# Shipyard — project guide for Claude

FastAPI SaaS boilerplate with **configurable SSR + REST surfaces**, admin, user
management, multi-tenant teams, Stripe billing, and async background tasks.

## Core principle: implicit per-feature surfaces

A feature is a self-contained package under `app/features/<name>/`. It exposes
web surfaces **by which routers it defines** — there is no central surface
config:

- `api.py` (router) → mounted at `/api/v1/<feature>` (REST/JSON)
- `views.py` (router) → mounted at `/<feature>` (SSR HTML, Jinja + HTMX)
- `admin.py` (ModelViews) → registered with SQLAdmin
- `tasks.py` → arq task functions / cron

Each feature's `__init__.py` exports a `feature = FeatureModule(...)`. The
registry (`app/core/registry.py`) auto-discovers and the app factory
(`app/main.py`) mounts them. REST and SSR are **thin adapters over a shared
`service.py`** — business logic lives once, never duplicated across surfaces.

## Stack

FastAPI · SQLAlchemy 2.0 async · Alembic · fastapi-users (JWT bearer + cookie) ·
SQLAdmin · **arq** (Redis; not Celery) · Jinja2 + HTMX · PostgreSQL · Redis ·
Stripe. Tooling: uv, ruff, mypy, pytest.

## Layout

```
app/core/       config, db, redis/arq, registry, models (Base/UUID/Timestamp), health
app/features/   users, teams, billing, notifications
app/admin/      SQLAdmin mount + superuser auth backend
app/web/        shared Jinja layout, static, CSRF, templating
app/main.py     app factory (discovers + mounts features, admin, redirect handler)
app/worker.py   arq worker (collects tasks/cron from features)
alembic/        async migrations (GUID rendered as portable sa.Uuid via render_item)
tests/          pytest (auth REST+SSR, teams/roles, billing webhook idempotency)
docs/PLAN.md    full design + Phase 7+ gap-closing plan
docs/adr/       architecture decisions
```

## Auth model (important)

- Two transports both active: **cookie** (SSR, httpOnly `shipyardauth`) and
  **bearer** (REST). API accepts either.
- SSR protected routes use `ssr_required_user` → redirects logged-out browsers to
  `/auth/login?next=...` (303). REST uses `current_active_user` → 401.
- CSRF is currently enforced **only on SSR Jinja form posts** (`verify_csrf`).
  The API has no CSRF gate yet — see Phase 7.1 (transport-aware CSRF) before
  shipping any cookie-auth SPA.

## Conventions

- Service layer holds logic; routers stay thin. Tenant-scoped queries filter by
  team membership (see `teams/service.py`).
- New feature: create the package, export `FeatureModule`; nothing else to wire.
- Keep ruff + mypy clean. Library typing friction (fastapi-users/stripe/sqladmin)
  handled with string columns / targeted ignores.

## Commands

```bash
uv venv && VIRTUAL_ENV=.venv uv pip install -e ".[dev]"   # install (note VIRTUAL_ENV)
.venv/bin/ruff check app && .venv/bin/mypy app            # lint + types
.venv/bin/python -m pytest -q                             # tests (slow: Argon2)
docker compose up --build                                 # full stack (api/worker/pg/redis)
python -m app.cli createsuperuser <email> <password>      # admin user (avoid .local TLD)
```

Admin at `/admin`, REST docs at `/docs`, SSR app at `/`.

## Status

Phases 0–6 + SSR redirect-to-login: **done, tested, committed**, and verified
running in Docker. Next work is **Phase 7+** (frontend shells & auth hardening)
in `docs/PLAN.md`, per `docs/adr/0001-frontend-auth-shells.md` — design is
written, implementation not started.
