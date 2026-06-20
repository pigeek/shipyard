from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from app.admin.setup import setup_admin
from app.core.config import settings
from app.core.i18n import LOCALE_COOKIE
from app.core.i18n import is_supported as is_supported_locale
from app.core.realtime import get_realtime_hub
from app.core.redis import close_arq_pool, init_arq_pool
from app.core.registry import discover_features
from app.core.storage import get_storage
from app.features.users.dependencies import RequiresLogin, load_current_user
from app.web.api_csrf import ApiCsrfMiddleware
from app.web.spa import mount_spa
from app.web.templating import render

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_arq_pool(app)
    if settings.storage_provider != "memory":
        # Create the bucket on boot for real backends; the memory backend is a
        # no-op, so tests/keyless dev stay infra-free.
        await get_storage().ensure_bucket()
    # Start the realtime hub's pub/sub subscriber (no-op for the memory provider).
    await get_realtime_hub().start()
    yield
    await get_realtime_hub().stop()
    await close_arq_pool(app)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    if settings.cors_origins:
        # Separate-origin / Vite-dev SPA (ADR 0001 Phase 7.5). Credentialed CORS
        # requires explicit origins (no "*") and, cross-site, the session cookie
        # must be SameSite=None; Secure — see .env.example / README.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if settings.auth_cookie_enabled:
        # Transport-aware CSRF for /api/v1: only relevant when cookie auth is on
        # (bearer-only deployments have no CSRF surface). See ADR 0001.
        app.add_middleware(ApiCsrfMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.cookie_secure,
        same_site="lax",
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(RequiresLogin)
    async def _redirect_to_login(request: Request, exc: RequiresLogin):
        return RedirectResponse(f"/auth/login?next={quote(exc.next_url, safe='')}", status_code=303)

    from app.core.health import router as health_router

    app.include_router(health_router)

    @app.get("/")
    async def index(request: Request, user=Depends(load_current_user)):
        return render(request, "index.html")

    @app.get("/i18n/set")
    async def set_locale(request: Request, lng: str, next: str = "/"):
        """Switch the active locale by setting the shared ``locale`` cookie.

        Same-origin SSR and the SPA both read this cookie, so one switch covers
        both surfaces. Only same-site ``next`` paths are honored (open-redirect
        guard); unsupported locales are ignored.
        """
        target = next if next.startswith("/") and not next.startswith("//") else "/"
        response = RedirectResponse(target, status_code=303)
        if is_supported_locale(lng):
            response.set_cookie(
                LOCALE_COOKIE,
                lng,
                max_age=60 * 60 * 24 * 365,
                httponly=False,  # the SPA (JS) reads it too
                samesite="lax",
                secure=settings.cookie_secure,
            )
        return response

    features = discover_features()
    for feature in features:
        if feature.api_router is not None:
            app.include_router(feature.api_router, prefix="/api/v1")
        if feature.ssr_router is not None:
            app.include_router(feature.ssr_router)
        if feature.ws_router is not None:
            app.include_router(feature.ws_router, prefix="/ws")

    setup_admin(app, features)
    mount_spa(app)
    return app


app = create_app()
