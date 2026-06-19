import re

import pytest

pytestmark = pytest.mark.asyncio


def _token_for(app_with_pool, function):
    """Pull the token an email task was enqueued with (args = (user_id, token))."""
    for fn, args, _kwargs in app_with_pool.state.arq_pool.jobs:
        if fn == function:
            return args[1]
    raise AssertionError(f"{function} was not enqueued")


async def test_verify_email_landing_page(client, app_with_pool):
    await client.post(
        "/api/v1/auth/register", json={"email": "verify@b.com", "password": "supersecret1"}
    )
    token = _token_for(app_with_pool, "send_verification_email")

    r = await client.get(f"/auth/verify?token={token}")
    assert r.status_code == 200
    assert "verified" in r.text.lower()


async def test_verify_invalid_token_shows_error(client):
    r = await client.get("/auth/verify?token=not-a-real-token")
    assert r.status_code == 400
    assert "invalid" in r.text.lower()


async def test_reset_password_landing_flow(client, app_with_pool):
    await client.post(
        "/api/v1/auth/register", json={"email": "reset@b.com", "password": "supersecret1"}
    )
    await client.post("/api/v1/auth/forgot-password", json={"email": "reset@b.com"})
    token = _token_for(app_with_pool, "send_password_reset_email")

    form = await client.get(f"/auth/reset?token={token}")
    assert form.status_code == 200
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    assert f'name="token" value="{token}"' in form.text

    r = await client.post(
        "/auth/reset",
        data={"token": token, "password": "brandnewpass1", "csrf_token": csrf},
    )
    assert r.status_code == 200
    assert "has been reset" in r.text.lower()

    # The new password works.
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "reset@b.com", "password": "brandnewpass1"},
    )
    assert r.status_code == 200
