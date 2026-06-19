import pytest

pytestmark = pytest.mark.asyncio


async def _register_and_login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "supersecret1"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_login_returns_token_pair(client):
    body = await _register_and_login(client, "ref1@b.com")
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    r = await client.get("/api/v1/users/me", headers=_auth(body["access_token"]))
    assert r.status_code == 200


async def test_refresh_issues_new_pair_and_rotates(client):
    body = await _register_and_login(client, "ref2@b.com")
    r = await client.post("/api/v1/auth/jwt/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200, r.text
    new = r.json()
    # New access token works...
    r = await client.get("/api/v1/users/me", headers=_auth(new["access_token"]))
    assert r.status_code == 200
    # ...and the old refresh token is now revoked (no reuse).
    r = await client.post("/api/v1/auth/jwt/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


async def test_logout_revokes_access_token(client):
    body = await _register_and_login(client, "ref3@b.com")
    token = body["access_token"]
    assert (await client.get("/api/v1/users/me", headers=_auth(token))).status_code == 200
    r = await client.post("/api/v1/auth/jwt/logout", headers=_auth(token))
    assert r.status_code == 204
    # The revoked token no longer authenticates.
    assert (await client.get("/api/v1/users/me", headers=_auth(token))).status_code == 401


async def test_logout_all_revokes_every_token(client):
    body = await _register_and_login(client, "ref4@b.com")
    access = body["access_token"]
    r = await client.post("/api/v1/auth/jwt/logout-all", headers=_auth(access))
    assert r.status_code == 204
    # Both the access token and the refresh token issued earlier are dead.
    assert (await client.get("/api/v1/users/me", headers=_auth(access))).status_code == 401
    r = await client.post("/api/v1/auth/jwt/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401
