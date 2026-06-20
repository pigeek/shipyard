"""i18n: locale negotiation + per-request SSR translation."""

from app.core.config import settings
from app.core.i18n import _parse_accept_language, negotiate_locale

# Async tests run under asyncio_mode=auto; no module-level mark needed (this file
# mixes sync unit tests and async client tests).


class _Conn:
    """Minimal HTTPConnection stand-in for negotiate_locale unit tests."""

    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or {}
        self.headers = headers or {}


def test_accept_language_parsing_orders_by_quality():
    assert _parse_accept_language("fr-CA,fr;q=0.9,en;q=0.5") == ["fr", "fr", "en"]
    assert _parse_accept_language("") == []


def test_negotiate_precedence():
    # user preference wins over everything
    assert negotiate_locale(_Conn(cookies={"locale": "en"}), user_locale="fr") == "fr"
    # cookie beats Accept-Language
    assert (
        negotiate_locale(_Conn(cookies={"locale": "fr"}, headers={"accept-language": "en"})) == "fr"
    )
    # Accept-Language when no cookie
    assert negotiate_locale(_Conn(headers={"accept-language": "fr-FR,fr;q=0.9"})) == "fr"
    # unsupported everywhere -> default
    assert negotiate_locale(_Conn(headers={"accept-language": "de"})) == settings.default_locale


async def test_ssr_default_is_english(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Get started" in r.text
    assert 'lang="en"' in r.text


async def test_ssr_translates_via_accept_language(client):
    r = await client.get("/", headers={"Accept-Language": "fr"})
    assert "Commencer" in r.text  # "Get started"
    assert "se connecter" in r.text  # "log in"
    assert 'lang="fr"' in r.text


async def test_ssr_translates_via_cookie(client):
    client.cookies.set("locale", "fr")
    r = await client.get("/")
    assert "Commencer" in r.text
    client.cookies.delete("locale")


async def test_set_locale_route_sets_cookie_and_redirects(client):
    r = await client.get("/i18n/set?lng=fr&next=/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    set_cookie = r.headers.get("set-cookie", "")
    assert "locale=fr" in set_cookie


async def test_set_locale_ignores_unsupported_and_open_redirect(client):
    # unsupported locale: no cookie set
    r = await client.get("/i18n/set?lng=de&next=/", follow_redirects=False)
    assert "locale=" not in r.headers.get("set-cookie", "")
    # open-redirect guard: external next is coerced to "/"
    r = await client.get("/i18n/set?lng=fr&next=https://evil.test", follow_redirects=False)
    assert r.headers["location"] == "/"
