"""OAuth social login (Phase 7.7).

A provider is wired only when its credentials are configured — consistent with
the implicit-surface philosophy: no creds → no OAuth routes. The same identity
core backs OAuth and password login (linked accounts live in ``oauth_account``,
associated to existing users by email).

The OAuth router is mounted with the **cookie** backend when cookie auth is on,
so a successful web (SSR/SPA) sign-in lands the browser on a session cookie; a
bearer-only deployment falls back to the JWT backend for token clients.
"""

from httpx_oauth.clients.google import GoogleOAuth2

from app.core.config import settings

google_oauth_client: GoogleOAuth2 | None = None
if settings.google_oauth_client_id and settings.google_oauth_client_secret:
    google_oauth_client = GoogleOAuth2(
        settings.google_oauth_client_id,
        settings.google_oauth_client_secret,
    )


def oauth_enabled() -> bool:
    return google_oauth_client is not None
