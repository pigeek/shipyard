"""Direct-to-bucket upload lifecycle for the files feature.

Tests use STORAGE_PROVIDER=memory (the conftest default). The browser's direct
POST to the bucket is simulated by writing the object through the shared storage
seam, since the memory backend issues a sentinel form real browsers can't use.
"""

import pytest
from app.core.storage import get_storage

FAKE_BYTES = b"\xff\xd8\xff\xe0fake-bytes-payload"


async def _register_and_token(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    r = await client.post(
        "/api/v1/auth/jwt/login", data={"username": email, "password": "supersecret1"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _start(client, headers, filename="doc.pdf", content_type="application/pdf", team_id=None):
    body = {"filename": filename, "content_type": content_type}
    if team_id is not None:
        body["team_id"] = team_id
    return await client.post("/api/v1/files", json=body, headers=headers)


async def _simulate_landed_object(upload, data=FAKE_BYTES, content_type="application/pdf"):
    """Stand in for the browser's direct POST to the private bucket."""
    await get_storage().upload(upload["fields"]["key"], data, content_type)


async def _create_team(client, headers, name="Acme"):
    r = await client.post("/api/v1/teams", json={"name": name}, headers=headers)
    return r.json()["id"]


# --- start-upload -------------------------------------------------------------


async def test_start_upload_creates_pending_and_returns_form(client):
    headers = await _register_and_token(client, "f1@b.com")
    resp = await _start(client, headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    file = body["file"]
    assert file["status"] == "pending"
    assert file["owner_id"] is not None
    assert file["team_id"] is None
    assert file["filename"] == "doc.pdf"

    upload = body["upload"]
    assert upload["fields"]["key"] == file["key"]
    assert upload["fields"]["Content-Type"] == "application/pdf"
    assert upload["max_bytes"] == 10 * 1024 * 1024


async def test_confirm_upload_records_object_and_marks_stored(client):
    headers = await _register_and_token(client, "f2@b.com")
    body = (await _start(client, headers)).json()
    await _simulate_landed_object(body["upload"])

    confirm = await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)
    assert confirm.status_code == 200, confirm.text
    final = confirm.json()
    assert final["status"] == "stored"
    assert final["size"] == len(FAKE_BYTES)
    assert final["content_type"] == "application/pdf"


async def test_confirm_without_object_is_409(client):
    headers = await _register_and_token(client, "f3@b.com")
    body = (await _start(client, headers)).json()
    # No upload simulated -> object absent -> confirm must refuse.
    confirm = await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)
    assert confirm.status_code == 409


async def test_confirm_is_idempotent(client):
    headers = await _register_and_token(client, "f4@b.com")
    body = (await _start(client, headers)).json()
    await _simulate_landed_object(body["upload"])
    first = await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)
    assert first.status_code == 200
    again = await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "stored"


# --- listing / download / delete ---------------------------------------------


async def test_list_excludes_pending_and_shows_stored(client):
    headers = await _register_and_token(client, "f5@b.com")
    # one pending (never uploaded), one stored
    await _start(client, headers, filename="ghost.pdf")
    body = (await _start(client, headers, filename="real.pdf")).json()
    await _simulate_landed_object(body["upload"])
    await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)

    listed = await client.get("/api/v1/files", headers=headers)
    assert listed.status_code == 200
    names = [f["filename"] for f in listed.json()]
    assert names == ["real.pdf"]


async def test_download_url_is_presigned_never_public(client):
    headers = await _register_and_token(client, "f6@b.com")
    body = (await _start(client, headers)).json()
    await _simulate_landed_object(body["upload"])
    await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)

    resp = await client.get(f"/api/v1/files/{body['file']['id']}/download-url", headers=headers)
    assert resp.status_code == 200
    # memory backend signs as memory://; never a bare public http object URL.
    assert resp.json()["url"].startswith("memory://")


async def test_delete_removes_row_and_object(client):
    headers = await _register_and_token(client, "f7@b.com")
    body = (await _start(client, headers)).json()
    await _simulate_landed_object(body["upload"])
    await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=headers)

    resp = await client.delete(f"/api/v1/files/{body['file']['id']}", headers=headers)
    assert resp.status_code == 204
    with pytest.raises(KeyError):
        await get_storage().download(body["file"]["key"])
    after = await client.get(f"/api/v1/files/{body['file']['id']}/download-url", headers=headers)
    assert after.status_code == 404


# --- tenancy ------------------------------------------------------------------


async def test_team_scoped_upload_visible_to_member_not_outsider(client):
    owner = await _register_and_token(client, "owner@b.com")
    outsider = await _register_and_token(client, "out@b.com")
    team_id = await _create_team(client, owner)

    body = (await _start(client, owner, filename="team.pdf", team_id=team_id)).json()
    assert body["file"]["team_id"] == team_id
    assert body["file"]["owner_id"] is None
    assert body["upload"]["fields"]["key"].startswith(f"teams/{team_id}/")
    await _simulate_landed_object(body["upload"])
    await client.post(f"/api/v1/files/{body['file']['id']}/confirm", headers=owner)

    # The outsider cannot see or reach the team file.
    assert (await client.get("/api/v1/files", headers=outsider)).json() == []
    blocked = await client.get(f"/api/v1/files/{body['file']['id']}/download-url", headers=outsider)
    assert blocked.status_code == 404


async def test_start_upload_for_foreign_team_is_404(client):
    owner = await _register_and_token(client, "owner2@b.com")
    outsider = await _register_and_token(client, "out2@b.com")
    team_id = await _create_team(client, owner)
    resp = await _start(client, outsider, team_id=team_id)
    assert resp.status_code == 404


# --- presigned-POST policy (S3 backend, no boto3/network) ---------------------


async def test_s3_presigned_upload_pins_type_and_size():
    """The S3 presigned POST must pin the content type and a content-length-range
    so the bucket itself rejects oversized / wrong-type uploads. Built without
    boto3/network by bypassing __init__ and stubbing the signing client."""
    from app.core.storage import S3Backend

    captured: dict = {}

    class _FakeSigner:
        def generate_presigned_post(self, Bucket, Key, Fields, Conditions, ExpiresIn):
            captured.update(conditions=Conditions, fields=Fields, key=Key)
            return {"url": "http://minio:9000/shipyard", "fields": {**Fields, "key": Key}}

    backend = object.__new__(S3Backend)  # skip __init__ (no boto3, no network)
    backend._signing_client = _FakeSigner()
    backend._bucket = "shipyard"

    cred = await backend.presigned_upload("users/u/k.pdf", "image/png", max_bytes=12345, expires=60)
    assert {"Content-Type": "image/png"} in captured["conditions"]
    assert ["content-length-range", 1, 12345] in captured["conditions"]
    assert captured["key"] == "users/u/k.pdf"
    assert cred.max_bytes == 12345
    assert cred.expires_at is not None


# --- orphan cleanup -----------------------------------------------------------


async def test_cleanup_removes_orphaned_pending(client, db):
    from app.features.files import service

    headers = await _register_and_token(client, "f8@b.com")
    await _start(client, headers)  # pending, object never landed

    removed = await service.cleanup_orphaned_uploads(db, max_age_seconds=-1)
    assert removed >= 1
    assert (await client.get("/api/v1/files", headers=headers)).json() == []


async def test_cleanup_keeps_landed_but_unconfirmed(client, db):
    from app.features.files import service

    headers = await _register_and_token(client, "f9@b.com")
    body = (await _start(client, headers)).json()
    await _simulate_landed_object(body["upload"])  # landed but not confirmed

    removed = await service.cleanup_orphaned_uploads(db, max_age_seconds=-1)
    assert removed == 0  # object exists -> not an orphan, left for confirm/reconcile
