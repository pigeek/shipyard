# Shipyard (FastAPI) — Implementation Plan

A FastAPI SaaS boilerplate where **SSR (Jinja) and REST surfaces coexist per
feature** on separate URL trees, over a single shared business-logic layer.
Which surfaces a feature exposes is **implicit** — determined by which routers
the feature actually defines, not by any central config.

---

## 1. Confirmed stack

| Concern            | Choice |
|--------------------|--------|
| Framework          | FastAPI |
| ORM / migrations   | SQLAlchemy 2.0 (async) / Alembic |
| Validation         | Pydantic v2 + pydantic-settings |
| Auth               | fastapi-users — JWT bearer (REST) + session cookie (SSR) |
| Admin              | SQLAdmin |
| Background tasks    | arq (async, Redis broker, built-in cron) |
| SSR                | Jinja2 + HTMX, separate URL tree, per-feature mount |
| REST               | Pydantic schemas under `/api/v1` |
| Database           | PostgreSQL 16 |
| Cache / broker      | Redis 7 |
| Billing            | Stripe (Plans, Subscriptions, Invoices, Webhooks; idempotent) |
| Tenancy            | User → TeamMembership → Team, role-based query filtering |
| Infra              | Docker Compose (dev/prod), GitHub Actions CI/CD |
| Tooling            | uv (deps), ruff (lint/format), mypy, pytest + factory pattern |

---

## 2. Core architecture principles

1. **Thin presentation, fat service.** All business logic lives in a feature's
   `service.py`. REST (`api.py`) and SSR (`views.py`) are thin adapters that call
   the same service functions. No logic is duplicated between surfaces.

2. **Two separate URL trees, never the same URL for both.**
   - REST: `/api/v1/<feature>/...` → JSON (Pydantic schemas)
   - SSR:  `/<feature>/...`        → HTML (Jinja + HTMX)
   No content negotiation, no header sniffing.

3. **Implicit surface selection.** A feature is mounted by what routers it
   actually defines — no central config. If it exposes a REST router, that
   router is served under `/api/v1/<feature>`; if it exposes an SSR router, that
   one is served under `/<feature>`. Defining only one yields only that surface.
   The code is the declaration; nothing to keep in sync.

4. **Dual-surface auth, one user store.** JWT bearer tokens for `/api/v1`;
   secure HTTP-only session cookie for the SSR tree. Both backed by the same
   fastapi-users user manager.

5. **App factory + module registry.** `create_app()` discovers feature modules,
   reads their declared surfaces, and assembles the ASGI app (routers + admin +
   middleware + lifespan for DB/Redis/arq pools).

---

## 3. The feature-module contract

Every feature is a self-contained package implementing a small protocol so the
registry can mount it uniformly.

```
app/features/<name>/
├── __init__.py        # exports FeatureModule descriptor
├── models.py          # SQLAlchemy models (Mapped[] style)
├── schemas.py         # Pydantic v2 request/response schemas
├── service.py         # ALL business logic — async, returns domain objects
├── api.py             # APIRouter (REST/JSON)        — optional
├── views.py           # APIRouter (SSR/HTML+HTMX)    — optional
├── admin.py           # SQLAdmin ModelView registrations — optional
├── tasks.py           # arq task functions + cron defs   — optional
└── templates/<name>/  # Jinja templates for SSR
```

Descriptor (conceptual):

```python
FeatureModule(
    name="users",
    api_router=api.router,          # present  → mounted under /api/v1/users
    ssr_router=views.router,        # present  → mounted under /users
    admin_views=[UserAdmin, ...],   # present  → registered with SQLAdmin
    tasks=[send_verification_email, ...],
    cron=[...],
)
```

Surfaces are implicit: a `None`/absent router simply isn't mounted. A feature
that defines only `api.py` is REST-only; one that defines only `views.py` is
SSR-only; one that defines both gets both. There is no surface config to
maintain — adding or removing a router file changes what's exposed.

---

## 4. Project structure

```
shipyard/
├── app/
│   ├── main.py                 # create_app(): registry assembly, lifespan
│   ├── core/
│   │   ├── config.py           # pydantic-settings (env-split: dev/prod/test)
│   │   ├── db.py               # async engine, session dependency, Base
│   │   ├── redis.py            # redis + arq pool providers
│   │   ├── security.py         # fastapi-users setup, JWT + cookie backends
│   │   ├── registry.py         # FeatureModule descriptor + discovery/mount
│   │   ├── models.py           # Base mixins: UUID PK, timestamps
│   │   └── health.py           # /health, /ready
│   ├── features/
│   │   ├── users/
│   │   ├── teams/
│   │   ├── billing/
│   │   └── notifications/
│   ├── admin/
│   │   └── setup.py            # SQLAdmin app + auth backend
│   ├── web/
│   │   ├── templates/          # base layout, partials, HTMX setup
│   │   └── static/
│   └── worker.py               # arq WorkerSettings (functions + cron + redis)
├── alembic/                    # migration env + versions
├── tests/                      # pytest, async fixtures, factories
├── docker/                     # entrypoints, readiness checks
├── docker-compose.yml          # dev
├── docker-compose.prod.yml     # prod
├── .github/workflows/ci.yml    # lint, type, test, build
├── pyproject.toml              # uv + ruff + mypy + pytest config
├── .env.example
└── docs/PLAN.md
```

---

## 5. Phased build

Each phase ends green (lint + types + tests pass) and is a logical commit point.

### Phase 0 — Skeleton & tooling
- `pyproject.toml` (uv), ruff, mypy, pytest config.
- `core/config.py` with env-split settings; `.env.example`.
- `core/db.py` async engine + session dependency; `core/models.py` base mixins
  (UUID PK, created/updated timestamps).
- `core/redis.py` Redis + arq pool providers.
- `core/registry.py` FeatureModule descriptor + `create_app()` assembly.
- `core/health.py` health/readiness endpoints.
- Alembic wired to async engine + Base metadata.
- Bare `main.py` booting an empty-feature app.
- **Exit:** app boots, `/health` returns 200, empty migration runs.

### Phase 1 — Users & dual-surface auth
- User model (UUID PK, email login, is_active/verified/superuser, Stripe
  customer id placeholder).
- fastapi-users wiring: user manager, **JWT bearer backend** (REST) +
  **cookie backend** (SSR), shared user DB adapter.
- REST `api.py`: register, login, logout, verify, request/confirm password
  reset, me/profile — under `/api/v1/auth` + `/api/v1/users`.
- SSR `views.py`: login/register/profile pages + HTMX partials — under `/auth`,
  `/users`. Session-cookie protected.
- Email verification + password-reset tokens enqueue email via arq.
- **Exit:** can register/login/verify/reset over both REST and SSR.

### Phase 2 — Admin (SQLAdmin)
- `admin/setup.py`: mount SQLAdmin, auth backend gated on superuser.
- `users/admin.py`: UserAdmin view.
- Registry collects `admin_views` from all features automatically.
- **Exit:** `/admin` lists/edits users; non-superusers blocked.

### Phase 3 — Teams & multi-tenancy
- Models: Team, TeamMembership (role: owner/admin/member).
- Service: create team, invite/add member, change role, remove; tenant-scoped
  query helpers (filter by team_id).
- Dependencies: `current_team`, role-requirement guards (REST + SSR variants).
- REST + SSR surfaces for team CRUD and membership management.
- Admin views for Team/TeamMembership.
- **Exit:** team CRUD + role enforcement on both surfaces; queries tenant-scoped.

### Phase 4 — Billing (Stripe)
- Models: Plan, Subscription, Invoice, WebhookEvent.
- Service: checkout/subscription lifecycle; webhook handler with DB-level
  idempotency (get-or-create on stripe_event_id, unique constraint).
- REST surface for plans/subscription/checkout + `/api/v1/billing/webhook`.
- arq tasks for post-webhook processing.
- Admin views for billing models.
- Stripe webhook test fixtures (JSON samples) + factory tests.
- **Exit:** subscribe flow + idempotent webhook processing tested.

### Phase 5 — Notifications
- EmailLog model (recipient, template, status, timestamps).
- Email service (provider abstraction; console backend in dev, SMTP/API in prod).
- arq tasks send email and write EmailLog audit rows.
- Wire users (verify/reset) and billing (receipts) to it.
- Admin view for EmailLog.
- **Exit:** outgoing email logged + auditable; async send via arq.

### Phase 6 — Infra & CI/CD
- Dockerfiles (app + worker), `docker-compose.yml` (api, worker, postgres,
  redis), `docker-compose.prod.yml`.
- Entrypoint with DB readiness check + `alembic upgrade head`.
- GitHub Actions: ruff, mypy, pytest (with services), image build.
- README quick-start (clone → up → migrate → run).
- **Exit:** `docker compose up` brings the full stack online from clean clone.

---

## 6. Cross-cutting concerns

- **Surface exposure is implicit:** mounting follows the routers a feature
  defines. A feature is REST-only, SSR-only, or both purely by which router
  modules exist — there is no surface config.
- **arq monitoring:** no Flower equivalent; expose queue stats via a small admin
  page / health metric (Prometheus optional, later).
- **Testing:** pytest-asyncio, transactional test DB, factory-style fixtures;
  cover service layer once, then thin surface tests per feature.
- **Security:** secrets from env only; Argon2 password hashing (pwdlib via
  fastapi-users); HTTP-only/secure/samesite cookies for SSR sessions; CSRF
  protection on SSR form posts.
- **Deferred (infra-ready, not pre-wired):** OAuth/social login, WebSockets/ASGI
  push, i18n, Kubernetes manifests.

---

## 7. Open items to revisit during build

- arq job observability depth (basic CLI vs admin page vs Prometheus).
- CSRF strategy for the SSR tree (token in session + hidden field).
- Admin views follow the same implicit rule (a feature's `admin.py` registers if
  present); confirm that's the desired behavior vs. a separate gate.
