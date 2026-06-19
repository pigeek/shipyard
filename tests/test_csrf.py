import re

import pytest

pytestmark = pytest.mark.asyncio


async def _cookie_login(client, email):
    """Register (REST) then log in over SSR to obtain the session cookie."""
    await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    form = await client.get("/auth/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    r = await client.post(
        "/auth/login",
        data={"email": email, "password": "supersecret1", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303


async def test_cookie_mutation_without_token_is_forbidden(client):
    await _cookie_login(client, "csrf1@b.com")
    await client.get("/api/v1/users/me")  # ensures a csrftoken cookie is issued
    r = await client.patch("/api/v1/users/me", json={"password": "newsupersecret1"})
    assert r.status_code == 403


async def test_cookie_mutation_with_token_succeeds(client):
    await _cookie_login(client, "csrf2@b.com")
    await client.get("/api/v1/users/me")
    csrf_cookie = client.cookies.get("csrftoken")
    assert csrf_cookie  # readable double-submit cookie was set
    r = await client.patch(
        "/api/v1/users/me",
        json={"password": "newsupersecret1"},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert r.status_code == 200


async def test_cookie_mutation_with_mismatched_token_is_forbidden(client):
    await _cookie_login(client, "csrf3@b.com")
    await client.get("/api/v1/users/me")
    r = await client.patch(
        "/api/v1/users/me",
        json={"password": "newsupersecret1"},
        headers={"X-CSRF-Token": "not-the-real-token"},
    )
    assert r.status_code == 403


async def test_bearer_mutation_is_exempt(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "csrf4@b.com", "password": "supersecret1"}
    )
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "csrf4@b.com", "password": "supersecret1"},
    )
    token = r.json()["access_token"]
    # Bearer transport, no CSRF token → must not be rejected by the CSRF gate.
    r = await client.patch(
        "/api/v1/users/me",
        json={"password": "newsupersecret1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


async def test_safe_method_needs_no_token(client):
    await _cookie_login(client, "csrf5@b.com")
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 200
