import pytest

pytestmark = pytest.mark.asyncio


async def _register_and_token(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "supersecret1"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_team_lifecycle_and_roles(client):
    owner = await _register_and_token(client, "owner@b.com")
    await _register_and_token(client, "bob@b.com")

    r = await client.post("/api/v1/teams", json={"name": "Acme"}, headers=owner)
    assert r.status_code == 201
    team_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "bob@b.com", "role": "member"},
        headers=owner,
    )
    assert r.status_code == 201
    bob_id = r.json()["user_id"]

    r = await client.patch(
        f"/api/v1/teams/{team_id}/members/{bob_id}",
        json={"role": "admin"},
        headers=owner,
    )
    assert r.json()["role"] == "admin"

    members = await client.get(f"/api/v1/teams/{team_id}", headers=owner)
    assert len(members.json()) == 2


async def test_non_member_gets_404(client):
    owner = await _register_and_token(client, "owner2@b.com")
    outsider = await _register_and_token(client, "out@b.com")
    team_id = (await client.post("/api/v1/teams", json={"name": "Secret"}, headers=owner)).json()[
        "id"
    ]

    r = await client.get(f"/api/v1/teams/{team_id}", headers=outsider)
    assert r.status_code == 404


async def test_member_cannot_manage(client):
    owner = await _register_and_token(client, "owner3@b.com")
    await _register_and_token(client, "carol@b.com")
    carol = await _register_and_token(client, "carol@b.com")  # same token
    team_id = (await client.post("/api/v1/teams", json={"name": "T"}, headers=owner)).json()["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "carol@b.com", "role": "member"},
        headers=owner,
    )

    # Member tries to add someone -> 403
    await _register_and_token(client, "dave@b.com")
    r = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "dave@b.com", "role": "member"},
        headers=carol,
    )
    assert r.status_code == 403


async def test_last_owner_cannot_be_removed(client):
    owner = await _register_and_token(client, "solo@b.com")
    team_id = (await client.post("/api/v1/teams", json={"name": "Solo"}, headers=owner)).json()[
        "id"
    ]
    me = (await client.get("/api/v1/users/me", headers=owner)).json()["id"]

    r = await client.request("DELETE", f"/api/v1/teams/{team_id}/members/{me}", headers=owner)
    assert r.status_code == 400
