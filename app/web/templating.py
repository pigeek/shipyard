from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.templating import Jinja2Templates, _TemplateResponse

from app.core.config import settings
from app.core.i18n import get_translations, negotiate_locale
from app.web.csrf import get_csrf_token
from app.web.spa import spa_is_built

APP_DIR = Path(__file__).resolve().parent.parent
WEB_TEMPLATES = APP_DIR / "web" / "templates"


def _template_dirs() -> list[str]:
    """Shared layout dir plus every feature's own templates/ dir."""
    dirs = [WEB_TEMPLATES]
    for tdir in sorted((APP_DIR / "features").glob("*/templates")):
        dirs.append(tdir)
    return [str(d) for d in dirs]


templates = Jinja2Templates(directory=_template_dirs())
# i18n: enable {% trans %} / {{ _() }}. Translations are injected per-request in
# render() (not installed globally), so concurrent requests can't race on locale.
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_null_translations(newstyle=True)  # type: ignore[attr-defined]
templates.env.globals["app_name"] = settings.app_name
# Whether the React SPA is available to link to from SSR pages (Phase 7.4).
templates.env.globals["spa_enabled"] = spa_is_built()
# Whether to show the "Continue with Google" button on auth pages (Phase 7.7).
# Computed from settings here (not imported from the users feature) to avoid a
# web→feature import cycle; it mirrors users.oauth.oauth_enabled().
templates.env.globals["oauth_google_enabled"] = bool(
    settings.google_oauth_client_id and settings.google_oauth_client_secret
)


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> _TemplateResponse:
    """Render a Jinja template, auto-injecting csrf_token, i18n, and the request."""
    current_user = getattr(request.state, "current_user", None)
    locale = negotiate_locale(request, getattr(current_user, "locale", None))
    trans = get_translations(locale)
    ctx = {
        "csrf_token": get_csrf_token(request),
        "current_user": current_user,
        # Per-request gettext callables (newstyle) — used by {{ _() }} / {% trans %}.
        "_": trans.gettext,
        "gettext": trans.gettext,
        "_n": trans.ngettext,
        "ngettext": trans.ngettext,
        "current_locale": locale,
        "supported_locales": settings.supported_locales,
        **(context or {}),
    }
    return templates.TemplateResponse(request, name, ctx, status_code=status_code, headers=headers)


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
