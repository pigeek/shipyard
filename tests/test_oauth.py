import pytest
from app.features.users.oauth import oauth_enabled
from httpx_oauth.clients.google import GoogleOAuth2

pytestmark = pytest.mark.asyncio


async def test_oauth_disabled_by_default(client):
    # No provider credentials configured → no OAuth routes are mounted.
    assert oauth_enabled() is False
    r = await client.get("/api/v1/auth/google/authorize")
    assert r.status_code == 404


async def test_google_client_produces_authorization_url():
    # The provider integration itself is wired correctly (independent of whether
    # it's mounted): a configured client yields a Google consent URL.
    google = GoogleOAuth2("client-id", "client-secret")
    url = await google.get_authorization_url("http://localhost:8000/cb", "state-token")
    assert "accounts.google.com" in url
    assert "client_id=client-id" in url


async def test_oauth_account_table_exists(db):
    # The user DB now joins an oauth_account table; creating it must succeed and
    # ordinary registration must still work alongside it (covered elsewhere).
    from sqlalchemy import inspect

    def _tables(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    conn = await db.connection()
    tables = await conn.run_sync(_tables)
    assert "oauth_account" in tables
