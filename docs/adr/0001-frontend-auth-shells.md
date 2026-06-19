# ADR 0001 — Frontend shells and authentication transports

- **Status:** Accepted
- **Date:** 2026-06-19
- **Context owners:** Shipyard maintainers

## Context

Shipyard exposes features over two surfaces that are mounted implicitly by the
routers a feature defines: **REST** (`/api/v1/*`, JSON) and **SSR** (Jinja+HTMX
at the root). Authentication is handled by fastapi-users with **two transports
active at once**:

- a **cookie** transport (httpOnly JWT, `shipyardauth`) used by SSR, and
- a **bearer** transport (`Authorization: Bearer`) used by API clients.

The API authenticates a request if *either* transport validates, so the same
principal is reachable from a browser session or a token client.

We need the boilerplate to support, in a **single deployment**, a spectrum of
frontends:

1. **SSR-only** — Jinja end to end (already shipped).
2. **SSR front door + React app** — public/marketing + auth in SSR; the
   authenticated product is a React SPA.
3. **Client-owned auth** — a React web app and/or a native mobile app that drive
   authentication themselves against the REST API.

Shells 2 and 3 must be able to **coexist** (e.g. a cookie-session web SPA *and* a
bearer-token mobile app talking to the same API).

### Forces

- **Token-in-JS is an XSS liability.** A first-party web SPA is safest with an
  httpOnly cookie session (no token reachable from JavaScript).
- **Cookies are CSRF-able; bearer tokens are not.** A browser auto-sends cookies
  cross-site; an attacker cannot set an `Authorization` header cross-site.
- **Mobile/native cannot use cookies ergonomically** and needs long-lived
  sessions → bearer + refresh tokens.
- **Stateless JWT cannot be revoked** before expiry; "log out everywhere" and
  leaked-token containment need server-side state.
- **Cross-origin frontends** force CORS + `SameSite=None; Secure` cookies;
  **same-origin** serving avoids all of it.

## Decision

Adopt a **one identity core, multiple shells** model with a clear default:

1. **Default web target = same-origin React served by FastAPI at `/app`**, using
   the **cookie** session. The SSR layer owns the public site and the auth pages
   (`/`, `/auth/*`); after login the user is redirected into `/app`. The SPA
   calls `/api/v1/*` and the cookie rides along automatically — no token in JS.

2. **Mobile / native / third-party = bearer + refresh tokens.** These clients
   drive `POST /api/v1/auth/jwt/login`, store tokens client-side, and send
   `Authorization: Bearer`. This shell may run **alongside** the cookie web SPA
   against the same endpoints.

3. **CSRF protection is transport-aware, not global.** A mutation
   (`POST/PUT/PATCH/DELETE`) is required to present a valid CSRF token **only
   when the request was authenticated via the cookie**. Bearer-authenticated
   mutations are **exempt** (not CSRF-able). This single rule is what lets the
   cookie web SPA and the bearer mobile app share identical endpoints safely.

4. **Sessions gain refresh + revocation.** Introduce refresh tokens for bearer
   clients and a Redis-backed strategy (or denylist) so tokens can be revoked
   server-side; the cookie session reuses the same user store and revocation
   path.

5. **The React SPA shell is an app-level concern, not a feature surface.** It is
   mounted like `/admin` (static bundle + `/app/*` catch-all to `index.html`),
   not inside a feature package. The per-feature registry continues to model only
   `{REST, SSR}`.

6. **Which shells a deployment ships is a configuration choice**, consistent with
   the implicit-surface philosophy: a "client-owned auth" deployment simply does
   not mount the SSR auth views and lets React/mobile use REST; an "SSR-only"
   deployment does not build/serve the `/app` bundle.

## Consequences

**Positive**

- Smallest attack surface for the common case: first-party web has no token in
  JS; mobile uses standard bearer+refresh.
- Web and mobile coexist on one API with no endpoint duplication.
- Same-origin default removes CORS and cross-site-cookie complexity in
  production.
- Revocation/refresh close real session-management gaps for both transports.

**Negative / costs**

- Transport-aware CSRF is a security-sensitive primitive that must be
  implemented and tested carefully (the failure modes are silent).
- Refresh + Redis revocation add moving parts (Redis becomes part of the auth
  path, not just the queue/cache).
- Serving a React bundle adds a frontend build to CI and the image.
- Email verification/reset need real landing pages per active shell.

**Neutral**

- The API stays transport-agnostic; only the *shell* and the CSRF gate are
  transport-aware.

## Alternatives considered

- **Bearer-only API (no cookie acceptance).** Removes the CSRF surface entirely,
  but forces the web SPA to store tokens in JS (XSS risk) or reintroduce a
  cookie anyway. Rejected as the default; still available by not mounting the
  cookie backend.
- **Separate-origin SPA (own deployment).** Cleaner deploy separation, but
  requires CORS + `SameSite=None; Secure` and a cross-site cookie story.
  Supported, but not the default.
- **Session store instead of JWT.** Server-side sessions give revocation for
  free but complicate horizontal scaling and the bearer/mobile path. We instead
  keep JWT and add a Redis strategy where revocation is needed.

## Follow-up

See `docs/PLAN.md` → "Phase 7+ — Frontend shells & auth hardening" for the
phased plan that closes the gaps this ADR implies.
