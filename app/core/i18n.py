"""Internationalization: locale negotiation + gettext translation catalogs.

A small, framework-light i18n core shared by every surface:

- **SSR** (Jinja): ``web/templating.render`` negotiates a locale per request and
  injects the matching gettext callables (``_``/``_n``) into the template
  context, so ``{{ _("Text") }}`` and ``{% trans %}`` translate per request
  without any global mutation.
- **Emails** (worker, no request): translate against a user's stored locale.
- **SPA**: negotiates client-side (react-i18next), but shares the ``locale``
  cookie this module reads/writes so the choice is consistent across surfaces.

Catalogs live at ``app/locales/<locale>/LC_MESSAGES/messages.mo`` (compiled from
``.po`` with Babel — see the README). The source language (``default_locale``)
needs no catalog: it falls back to the original strings.
"""

from __future__ import annotations

import gettext as _gettext
from functools import lru_cache
from pathlib import Path

from starlette.requests import HTTPConnection

from app.core.config import settings

LOCALE_COOKIE = "locale"
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def is_supported(locale: str | None) -> bool:
    return locale is not None and locale in settings.supported_locales


@lru_cache
def get_translations(locale: str) -> _gettext.NullTranslations:
    """gettext catalog for ``locale`` (cached). Missing/source locale → identity."""
    if locale == settings.default_locale or not is_supported(locale):
        return _gettext.NullTranslations()
    try:
        return _gettext.translation("messages", localedir=str(LOCALES_DIR), languages=[locale])
    except FileNotFoundError:
        # Catalog not compiled yet — degrade to source strings rather than 500.
        return _gettext.NullTranslations()


def _parse_accept_language(header: str) -> list[str]:
    """Ordered list of base language tags from an Accept-Language header."""
    langs: list[tuple[float, str]] = []
    for part in header.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        tag, _, q = chunk.partition(";q=")
        tag = tag.strip().split("-")[0].lower()
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 1.0
        langs.append((weight, tag))
    return [tag for _, tag in sorted(langs, key=lambda t: t[0], reverse=True)]


def negotiate_locale(conn: HTTPConnection, user_locale: str | None = None) -> str:
    """Resolve the active locale: user preference → cookie → Accept-Language →
    default. Only ever returns a supported locale."""
    if is_supported(user_locale):
        return user_locale  # type: ignore[return-value]
    cookie = conn.cookies.get(LOCALE_COOKIE)
    if is_supported(cookie):
        return cookie  # type: ignore[return-value]
    for tag in _parse_accept_language(conn.headers.get("accept-language", "")):
        if is_supported(tag):
            return tag
    return settings.default_locale
