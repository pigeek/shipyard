"""End-to-end test of the files feature against the *running* compose stack.

Exercises the whole path a browser would: hit the live API on localhost:8000,
get a presigned upload form, POST the bytes straight to MinIO with it, confirm,
then read the object back through a presigned download URL. Auto-skipped unless
both the API (:8000) and MinIO (:9000) are reachable (i.e. `docker compose up`).

Run explicitly with:  .venv/bin/python -m pytest tests/integration -q
"""

import socket
import uuid

import httpx
import pytest

API = "http://localhost:8000"


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


STACK_UP = _reachable("localhost", 8000) and _reachable("localhost", 9000)
pytestmark = pytest.mark.skipif(not STACK_UP, reason="compose stack (api:8000 + minio:9000) not up")


async def _register_and_token(http: httpx.AsyncClient) -> dict[str, str]:
    email = f"e2e-{uuid.uuid4().hex[:12]}@example.com"
    password = "supersecret1"
    r = await http.post(f"{API}/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    r = await http.post(
        f"{API}/api/v1/auth/jwt/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_health_ok():
    async with httpx.AsyncClient() as http:
        r = await http.get(f"{API}/health")
    assert r.status_code == 200


async def test_full_upload_lifecycle_through_api():
    payload = b"%PDF-1.4 end-to-end through the live stack"
    async with httpx.AsyncClient(timeout=10.0) as http:
        headers = await _register_and_token(http)

        # 1. Start: the API creates a pending row and returns a presigned POST form.
        start = await http.post(
            f"{API}/api/v1/files",
            json={"filename": "report.pdf", "content_type": "application/pdf"},
            headers=headers,
        )
        assert start.status_code == 201, start.text
        body = start.json()
        file_id = body["file"]["id"]
        upload = body["upload"]
        assert body["file"]["status"] == "pending"
        # The form must target a host the browser (this test) can actually reach.
        assert upload["url"].startswith("http://localhost:9000/")

        # 2. Upload the bytes straight to MinIO with the presigned form.
        put = await http.post(
            upload["url"],
            data=upload["fields"],
            files={"file": ("report.pdf", payload, "application/pdf")},
        )
        assert put.status_code in (200, 204), put.text

        # 3. Confirm: the API head-verifies the object and records its real size.
        confirm = await http.post(f"{API}/api/v1/files/{file_id}/confirm", headers=headers)
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["status"] == "stored"
        assert confirm.json()["size"] == len(payload)

        # 4. It now shows up in the listing.
        listed = await http.get(f"{API}/api/v1/files", headers=headers)
        assert file_id in [f["id"] for f in listed.json()]

        # 5. Download via a presigned GET URL and verify the bytes round-trip.
        dl = await http.get(f"{API}/api/v1/files/{file_id}/download-url", headers=headers)
        assert dl.status_code == 200
        url = dl.json()["url"]
        assert url.startswith("http://localhost:9000/")
        got = await http.get(url)
        assert got.status_code == 200
        assert got.content == payload

        # 6. Delete removes both row and object.
        rm = await http.delete(f"{API}/api/v1/files/{file_id}", headers=headers)
        assert rm.status_code == 204
        after = await http.get(f"{API}/api/v1/files/{file_id}/download-url", headers=headers)
        assert after.status_code == 404
