# Shipyard (FastAPI) — Implementation Plan

A FastAPI SaaS boilerplate where **SSR (Jinja) and REST surfaces coexist per
feature** on separate URL trees, over a single shared business-logic layer.
Which surfaces a feature exposes is **implicit** — determined by which routers
the feature actually defines, not by any central config.

> **Status: fully implemented.** All phases below are built, linted (ruff),
> type-checked (mypy), and covered by a passing pytest suite. The task queue is
> **arq** (not Celery). See the git history for per-phase commits.

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

---

## Phase 7+ — Frontend shells & auth hardening

Closes the gaps identified in **ADR 0001 — Frontend shells and authentication
transports** (`docs/adr/0001-frontend-auth-shells.md`). Target end state:
same-origin React at `/app` on a cookie session, mobile/native on bearer+refresh,
one API, **transport-aware CSRF**. Design-only until scheduled; still phased so
each step lands green.

Ordering rule: the **security primitives (7.1–7.2) must land before the React
SPA (7.4) is exposed to real traffic**, because the SPA is the first cookie-auth
client to issue API mutations.

### Phase 7.1 — Transport-aware CSRF (blocking prerequisite)
- Add a dependency/middleware that, on `POST/PUT/PATCH/DELETE` to `/api/v1/*`,
  enforces CSRF **only when the request authenticated via the cookie** and
  **exempts bearer-authenticated requests**.
- Mechanism: double-submit token (cookie-readable CSRF cookie + `X-CSRF-Token`
  header) or required custom header; pick one and document why.
- Detect transport explicitly (presence of `Authorization` header vs session
  cookie) rather than inferring.
- Tests: cookie mutation without token → 403; with token → 200; bearer mutation
  without token → 200 (exempt); cross-site `SameSite` behaviour asserted.
- **Exit:** mobile (bearer) is unaffected; cookie clients must present a token.

### Phase 7.2 — Refresh tokens + Redis revocation
- Introduce a refresh-token flow for bearer clients (`/api/v1/auth/jwt/refresh`),
  short-lived access + longer-lived refresh.
- Swap the stateless access strategy for a Redis-backed strategy (or maintain a
  denylist) so tokens can be revoked server-side.
- Logout becomes real: revoke the active token(s); "log out everywhere" clears a
  user's refresh tokens.
- Reuse the same store for cookie-session revocation.
- **Exit:** tokens are refreshable and revocable; SSR logout and API logout both
  invalidate server-side.

### Phase 7.3 — Auth transport decision made explicit
- Make "does the API accept cookie auth" a deliberate, documented setting rather
  than implicit. Default: accept both (cookie web + bearer mobile).
- A deployment may run bearer-only by not mounting the cookie backend (no CSRF
  surface) — wire this as a config path, not a code edit.
- **Exit:** the active transports for a deployment are configuration, consistent
  with the implicit-surface philosophy.

### Phase 7.4 — React SPA shell at `/app` (app-level, not a feature)
- Add a frontend build (Vite + React) producing a static bundle.
- Serve it from FastAPI: static assets + a `/app/*` catch-all returning
  `index.html` (client-side routing). Mounted like `/admin`, not in a feature.
- Post-login redirect target becomes `/app` for the hybrid shell; `next`
  honoured within the app boundary.
- SPA bootstraps identity via `GET /api/v1/users/me` (cookie); optional inlined
  bootstrap JSON to skip the first round trip.
- CI: build the bundle; image includes it.
- **Exit:** SSR landing/auth → cookie → React app, same origin, no token in JS.

### Phase 7.5 — CORS for separate-origin / dev
- Add CORS middleware (allow-credentials, explicit origins) for the Vite dev
  server and the separate-origin SPA option.
- Document the `SameSite=None; Secure` cookie requirement for cross-origin
  cookie sessions.
- **Exit:** local React dev against the API works; separate-origin deploy is a
  documented, supported option.

### Phase 7.6 — Verify / reset landing pages per shell
- Replace the "POST this token" emails with links to real pages:
  SSR (`/auth/verify`, `/auth/reset`) and/or SPA (`/app/verify`, `/app/reset`)
  that call the API.
- Choose link target based on the deployment's active shell.
- **Exit:** email verification and password reset are click-through flows in
  whichever shell is shipped.

### Phase 7.7 — OAuth / social login (both shells)
- Wire the scaffolded OAuth backends; expose for SSR (redirect flow) and SPA
  (authorization-code flow), reusing the same user store.
- **Exit:** social login works from the web shell; tokens issued via the same
  identity core.

### Deferred / explicitly out of scope for 7.x
- WebSockets/ASGI push, i18n, Kubernetes manifests (still infra-ready, not wired).
- Native mobile app scaffolding (consumes the bearer+refresh API; not part of
  this repo).
