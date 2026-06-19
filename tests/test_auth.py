import re

import pytest

pytestmark = pytest.mark.asyncio


async def test_rest_register_login_me(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "supersecret1"},
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "a@b.com", "password": "supersecret1"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


async def test_register_enqueues_welcome_and_verification(client, app_with_pool):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "queue@b.com", "password": "supersecret1"},
    )
    enqueued = {job[0] for job in app_with_pool.state.arq_pool.jobs}
    assert "send_welcome_email" in enqueued
    assert "send_verification_email" in enqueued


async def test_ssr_register_sets_cookie_and_profile(client):
    form = await client.get("/auth/register")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)

    r = await client.post(
        "/auth/register",
        data={"email": "ssr@b.com", "password": "supersecret1", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert any(k.lower() == "set-cookie" for k in r.headers)

    # httpx keeps the cookie; the SSR profile page should now be authorized.
    r = await client.get("/users/me")
    assert r.status_code == 200
    assert "ssr@b.com" in r.text


async def test_protected_route_requires_auth(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401
