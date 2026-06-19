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


async def test_ssr_protected_redirects_to_login(client):
    # Logged-out SSR page bounces to login with a next= param (not a 401).
    r = await client.get("/users/me", follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/auth/login?next=")
    assert "%2Fusers%2Fme" in location


async def test_login_honors_next(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "next@b.com", "password": "supersecret1"},
    )
    form = await client.get("/auth/login?next=/teams")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    assert 'name="next" value="/teams"' in form.text

    r = await client.post(
        "/auth/login",
        data={
            "email": "next@b.com",
            "password": "supersecret1",
            "csrf_token": csrf,
            "next": "/teams",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/teams"


async def test_login_rejects_offsite_next(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "safe@b.com", "password": "supersecret1"},
    )
    form = await client.get("/auth/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    r = await client.post(
        "/auth/login",
        data={
            "email": "safe@b.com",
            "password": "supersecret1",
            "csrf_token": csrf,
            "next": "//evil.com",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
