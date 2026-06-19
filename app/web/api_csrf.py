"""Transport-aware CSRF protection for the REST API (`/api/v1`).

The API accepts two auth transports (see ADR 0001): a session **cookie** (used by
the SSR site and the same-origin React SPA) and a **bearer** token (used by
mobile/native/third-party clients). Cookies are auto-sent cross-site and are
therefore CSRF-able; bearer tokens are not (an attacker cannot set an
``Authorization`` header cross-site).

This middleware enforces a double-submit CSRF token on **mutating** API requests
**only when the request authenticated via the cookie**, and **exempts bearer
requests**. Transport is detected explicitly: an ``Authorization`` header means
bearer (exempt); otherwise the presence of the session cookie means cookie auth.

Mechanism — double-submit cookie:
- A readable (non-httpOnly) ``csrftoken`` cookie is issued on responses that
  don't already carry one. JS clients read it and echo it back.
- A protected request must send an ``X-CSRF-Token`` header whose value matches
  that cookie. Same-origin policy stops other origins reading the cookie, and
  CORS stops them setting the header, so only a same-origin client can comply.

This is independent of the session-based CSRF used by SSR Jinja form posts
(`app/web/csrf.py`); the two surfaces protect different request shapes.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.features.users.security import COOKIE_NAME as AUTH_COOKIE_NAME

CSRF_COOKIE_NAME = "csrftoken"
CSRF_HEADER_NAME = "x-csrf-token"
API_PREFIX = "/api/v1"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class ApiCsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._must_enforce(request) and not self._token_valid(request):
            return JSONResponse({"detail": "CSRF token missing or invalid"}, status_code=403)
        response = await call_next(request)
        self._ensure_cookie(request, response)
        return response

    @staticmethod
    def _must_enforce(request: Request) -> bool:
        if request.method in SAFE_METHODS:
            return False
        if not request.url.path.startswith(API_PREFIX):
            return False
        # Bearer transport is explicit and not CSRF-able → exempt.
        if request.headers.get("authorization"):
            return False
        # Only cookie-authenticated mutations need a CSRF token. Unauthenticated
        # requests are left to the endpoint's own auth (which will 401).
        return AUTH_COOKIE_NAME in request.cookies

    @staticmethod
    def _token_valid(request: Request) -> bool:
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not cookie_token or not header_token:
            return False
        return secrets.compare_digest(cookie_token, header_token)

    @staticmethod
    def _ensure_cookie(request: Request, response: Response) -> None:
        if CSRF_COOKIE_NAME in request.cookies:
            return
        response.set_cookie(
            CSRF_COOKIE_NAME,
            secrets.token_urlsafe(32),
            max_age=settings.access_token_lifetime_seconds,
            httponly=False,  # must be readable by JS for the double-submit echo
            secure=settings.cookie_secure,
            samesite="lax",
        )
