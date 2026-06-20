"""Integration tests for the S3/MinIO storage seam against a *live* MinIO.

These talk to real MinIO over the network (no mocks), so they prove the parts
the unit tests can't: that the presigned POST policy is actually enforced by the
bucket, that path-style addressing works, and that a browser-style direct upload
round-trips. They are auto-skipped unless MinIO is reachable on localhost:9000
(i.e. `docker compose up`), so the fast unit suite is unaffected.

Run explicitly with:  .venv/bin/python -m pytest tests/integration -q
"""

import socket
import uuid

import httpx
import pytest

from app.core.config import settings
from app.core.storage import S3Backend


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


MINIO_UP = _reachable("localhost", 9000)
pytestmark = pytest.mark.skipif(not MINIO_UP, reason="MinIO not reachable on localhost:9000")


@pytest.fixture
def backend(monkeypatch):
    """A real S3Backend pointed at the compose MinIO, using a throwaway bucket so
    runs never collide with the app's bucket or each other."""
    bucket = f"itest-{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://localhost:9000")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "http://localhost:9000")
    monkeypatch.setattr(settings, "s3_bucket", bucket)
    monkeypatch.setattr(settings, "s3_access_key", "minioadmin")
    monkeypatch.setattr(settings, "s3_secret_key", "minioadmin")
    monkeypatch.setattr(settings, "s3_region", "us-east-1")
    return S3Backend()


async def test_ensure_bucket_is_idempotent(backend):
    await backend.ensure_bucket()
    await backend.ensure_bucket()  # second call must not raise


async def test_put_download_head_delete_roundtrip(backend):
    await backend.ensure_bucket()
    key = "users/itest/hello.txt"
    payload = b"hello minio integration"

    await backend.upload(key, payload, "text/plain")

    assert await backend.download(key) == payload
    head = await backend.head(key)
    assert head is not None
    assert head.size == len(payload)
    assert head.content_type == "text/plain"

    await backend.delete(key)
    assert await backend.head(key) is None


async def test_presigned_get_url_is_fetchable(backend):
    await backend.ensure_bucket()
    key = "users/itest/read.bin"
    payload = b"\x00\x01\x02 readable via presigned GET"
    await backend.upload(key, payload, "application/octet-stream")

    url = await backend.presigned_url(key, expires=60)
    assert url.startswith("http://localhost:9000/")
    async with httpx.AsyncClient() as http:
        resp = await http.get(url)
    assert resp.status_code == 200
    assert resp.content == payload


async def test_presigned_post_upload_roundtrip(backend):
    """The full browser path: get a scoped POST form, upload bytes straight to the
    bucket with it, then confirm the object landed and reads back identically."""
    await backend.ensure_bucket()
    key = "users/itest/direct-upload.pdf"
    payload = b"%PDF-1.4 direct-to-bucket bytes"

    cred = await backend.presigned_upload(key, "application/pdf", max_bytes=1_000_000, expires=120)
    assert cred.url.startswith("http://localhost:9000/")

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            cred.url,
            data=cred.fields,
            files={"file": ("direct-upload.pdf", payload, "application/pdf")},
        )
    assert resp.status_code in (200, 204), resp.text

    head = await backend.head(key)
    assert head is not None
    assert head.size == len(payload)
    assert await backend.download(key) == payload


async def test_presigned_post_rejects_oversized(backend):
    """The content-length-range policy must make MinIO itself reject a too-large
    upload — size is enforced by the bucket, not the app."""
    await backend.ensure_bucket()
    key = "users/itest/too-big.bin"
    cred = await backend.presigned_upload(key, "application/octet-stream", max_bytes=8, expires=120)

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            cred.url,
            data=cred.fields,
            files={"file": ("too-big.bin", b"x" * 64, "application/octet-stream")},
        )
    assert resp.status_code >= 400  # policy violation
    assert await backend.head(key) is None  # nothing landed


async def test_presigned_post_rejects_wrong_content_type(backend):
    """The pinned Content-Type condition must reject a mismatched type."""
    await backend.ensure_bucket()
    key = "users/itest/wrong-type.png"
    cred = await backend.presigned_upload(key, "image/png", max_bytes=1_000_000, expires=120)

    fields = dict(cred.fields)
    fields["Content-Type"] = "application/zip"  # contradicts the signed policy
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            cred.url,
            data=fields,
            files={"file": ("wrong-type.png", b"not a png", "application/zip")},
        )
    assert resp.status_code >= 400
    assert await backend.head(key) is None
