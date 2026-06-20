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
app/core/       config, db, redis/arq, registry, models (Base/UUID/Timestamp), storage, health
app/features/   users, teams, billing, notifications, files
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

- Two transports, both active by default: **cookie** (SSR, httpOnly
  `shipyardauth`) and **bearer** (REST). API accepts either.
- SSR protected routes use `ssr_required_user` → redirects logged-out browsers to
  `/auth/login?next=...` (303). REST uses `current_active_user` → 401.
- CSRF is **transport-aware** (ADR 0001 / Phase 7.1). SSR Jinja form posts use a
  session token (`verify_csrf`). The REST API uses a double-submit cookie
  (`ApiCsrfMiddleware`, `app/web/api_csrf.py`): mutating `/api/v1/*` requests
  authenticated via the **cookie** must send a matching `X-CSRF-Token` header;
  **bearer** requests are exempt.
- Bearer tokens are **revocable with refresh** (`auth_router.py`, `tokens.py`):
  `/api/v1/auth/jwt/{login,refresh,logout,logout-all}`. A `jti` + server-side
  store (Redis in prod, in-memory under tests) back revocation; SSR logout
  revokes the session token too.
- Active transports are configuration (`auth_cookie_enabled` /
  `auth_bearer_enabled`): the cookie-only deployment drops the bearer router; the
  bearer-only deployment drops the SSR auth pages + CSRF surface.
- Social login (Phase 7.7) is mounted only when a provider is configured
  (`GOOGLE_OAUTH_*`); linked accounts live in `oauth_account`.

## Object storage (S3 / MinIO)

- `app/core/storage.py` is an **infra seam** (parallels `core/redis.py`): a
  `StorageBackend` Protocol with `S3Backend` (boto3, AWS S3 in prod / MinIO in
  dev) and `MemoryBackend` (tests + keyless dev), behind a `get_storage()`
  `lru_cache` factory keyed on `settings.storage_provider` (`memory` default; the
  compose stack sets `s3`). boto3 calls run in `asyncio.to_thread`.
- Private-bucket pattern: objects are never public. **Reads** go through
  short-lived presigned GET URLs; **writes** go through a scoped, short-lived
  presigned **POST** form the browser submits directly (bytes never transit the
  API). The POST policy pins content-type + content-length-range, so the bucket
  itself rejects oversized/wrong-type uploads. Two boto3 clients exist so URLs
  are signed for a host the *browser* can reach (`s3_public_endpoint_url`).
- The `files` feature (`app/features/files/`) is the usable surface over the
  seam: `StoredFile` model (configurable scope — nullable `owner_id` **and**
  `team_id`; access honors whichever is set), REST lifecycle under
  `/api/v1/files` (`POST` start → `POST /{id}/confirm` → `GET /{id}/download-url`
  → `GET` list → `DELETE`), a read-only admin view, and an hourly arq cron
  (`cleanup_orphaned_uploads`) that drops never-confirmed `pending` rows past
  `orphan_upload_max_age`. Bucket creation happens on app startup for non-memory
  providers (`main.py` lifespan).

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
.venv/bin/python -m pytest -q                             # tests (fast: ~1s, in-memory SQLite)
npm --prefix frontend install && npm --prefix frontend run build   # build SPA → app/web/spa
docker compose up --build                                 # full stack (api/worker/pg/redis)
python -m app.cli createsuperuser <email> <password>      # admin user (avoid .local TLD)
```

Admin at `/admin`, REST docs at `/docs`, SSR app at `/`, React SPA at `/app`
(only when the bundle is built; the SPA tests skip otherwise).

Tests run in ~1s: they use a shared in-memory SQLite (StaticPool, `core/db.py`)
and weak Argon2 params in the testing env (`users/security.py`). Don't reintroduce
a file-based test DB or default Argon2 cost in tests — that was the 2.5-min suite.

## Status

Phases 0–6 + **Phase 7 (frontend shells & auth hardening, all of 7.1–7.7)** +
**object storage (S3/MinIO seam + `files` feature)**: **done, lint + mypy +
pytest green** (51 tests, migrations verified up/down). See `docs/PLAN.md` and
`docs/adr/0001-frontend-auth-shells.md`. The React SPA bundle is a build
artifact (built in CI / the Docker image), not committed.
