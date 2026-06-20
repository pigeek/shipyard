"""Serve the same-origin React SPA at /app (ADR 0001 §5, Phase 7.4).

The SPA is an **app-level** concern, mounted like /admin — not a feature surface.
Vite builds a static bundle into ``app/web/spa`` (``base: "/app/"``), so:

- ``/app/assets/*`` is served straight from disk, and
- every other ``/app/*`` path returns ``index.html`` so the client-side router
  owns navigation (deep links, refreshes).

If the bundle hasn't been built (e.g. an SSR-only deployment, or local dev before
``pnpm run build``), nothing is mounted and ``/app`` simply 404s — consistent with
the implicit-surface philosophy.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

SPA_DIR = Path(__file__).resolve().parent / "spa"
SPA_INDEX = SPA_DIR / "index.html"
SPA_ASSETS = SPA_DIR / "assets"


def spa_is_built() -> bool:
    return SPA_INDEX.is_file()


def mount_spa(app: FastAPI) -> bool:
    """Mount the SPA if its bundle exists. Returns whether it was mounted."""
    if not spa_is_built():
        return False

    if SPA_ASSETS.is_dir():
        app.mount("/app/assets", StaticFiles(directory=SPA_ASSETS), name="spa-assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    async def spa_index(path: str = "") -> Response:
        # Serve real files that live at the bundle root (favicon, etc.);
        # otherwise hand back index.html for client-side routing.
        if path:
            candidate = (SPA_DIR / path).resolve()
            if candidate.is_file() and SPA_DIR in candidate.parents:
                return FileResponse(candidate)
        return FileResponse(SPA_INDEX)

    return True
