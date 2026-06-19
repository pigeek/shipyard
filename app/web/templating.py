from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.templating import Jinja2Templates, _TemplateResponse

from app.core.config import settings
from app.web.csrf import get_csrf_token

APP_DIR = Path(__file__).resolve().parent.parent
WEB_TEMPLATES = APP_DIR / "web" / "templates"


def _template_dirs() -> list[str]:
    """Shared layout dir plus every feature's own templates/ dir."""
    dirs = [WEB_TEMPLATES]
    for tdir in sorted((APP_DIR / "features").glob("*/templates")):
        dirs.append(tdir)
    return [str(d) for d in dirs]


templates = Jinja2Templates(directory=_template_dirs())
templates.env.globals["app_name"] = settings.app_name


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> _TemplateResponse:
    """Render a Jinja template, auto-injecting csrf_token and the request."""
    ctx = {
        "csrf_token": get_csrf_token(request),
        "current_user": getattr(request.state, "current_user", None),
        **(context or {}),
    }
    return templates.TemplateResponse(request, name, ctx, status_code=status_code, headers=headers)


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
