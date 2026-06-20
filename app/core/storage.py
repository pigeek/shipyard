"""Object storage seam — AWS S3 in prod, MinIO in dev, in-memory for tests.

Pure infrastructure (parallels ``core/db.py`` / ``core/redis.py``): a backend
Protocol with two implementations behind a ``get_storage()`` factory keyed on
``settings.storage_provider``. No feature logic lives here — features call
``get_storage()`` and use the seam.

The private-bucket pattern: objects are never public. Reads go through
short-lived presigned GET URLs; writes go through scoped, short-lived presigned
POST forms the browser submits directly (the bytes never transit the API).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class UploadCredential:
    """A short-lived, single-key, write-only form the browser POSTs the object to
    directly. For the memory backend this is a sentinel real browsers never use —
    only the S3/MinIO backend produces a usable form."""

    url: str
    fields: dict[str, str] = field(default_factory=dict)
    max_bytes: int = 0
    expires_at: str | None = None


@dataclass
class ObjectHead:
    """Result of a head probe: the object exists and carries this content type."""

    content_type: str
    size: int


class StorageBackend(Protocol):
    async def ensure_bucket(self) -> None: ...
    async def upload(self, key: str, data: bytes, content_type: str) -> None: ...
    async def download(self, key: str) -> bytes: ...
    async def presigned_url(self, key: str, expires: int | None = None) -> str: ...
    async def presigned_upload(
        self, key: str, content_type: str, max_bytes: int, expires: int | None = None
    ) -> UploadCredential: ...
    async def head(self, key: str) -> ObjectHead | None: ...
    async def delete(self, key: str) -> None: ...


class S3Backend:
    """AWS S3 in prod, MinIO in dev. The bucket is private; reads go through
    short-lived presigned URLs. boto3 is synchronous, so every call is offloaded
    to a thread to keep the event loop free."""

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        common = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
            # Path-style URLs (/<bucket>/<key>) — presigned URLs routed by path
            # through a reverse proxy on the public host; a bucket subdomain would
            # neither resolve nor match the tunnel certificate.
            "config": Config(s3={"addressing_style": "path"}),
        }
        self._client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, **common)
        # Presigned URLs must use a host the *browser* can reach. With MinIO in
        # compose, the API talks to http://minio:9000 but the browser needs
        # http://localhost:9000 — so sign with a second, public-endpoint client.
        public_endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        self._signing_client = boto3.client("s3", endpoint_url=public_endpoint, **common)
        self._bucket = settings.s3_bucket

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except Exception:
                self._client.create_bucket(Bucket=self._bucket)

        await asyncio.to_thread(_ensure)

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def download(self, key: str) -> bytes:
        def _get() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

        return await asyncio.to_thread(_get)

    async def presigned_url(self, key: str, expires: int | None = None) -> str:
        return await asyncio.to_thread(
            self._signing_client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires or settings.presigned_url_ttl,
        )

    async def presigned_upload(
        self, key: str, content_type: str, max_bytes: int, expires: int | None = None
    ) -> UploadCredential:
        """A presigned POST scoped to exactly this key. The policy conditions make
        the bucket itself reject anything over max_bytes or of the wrong content
        type, so size/type are enforced even though the bytes never hit the API."""
        ttl = expires or settings.upload_credential_ttl
        resp = await asyncio.to_thread(
            self._signing_client.generate_presigned_post,
            self._bucket,
            key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=ttl,
        )
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl)).isoformat()
        return UploadCredential(
            url=resp["url"], fields=resp["fields"], max_bytes=max_bytes, expires_at=expires_at
        )

    async def head(self, key: str) -> ObjectHead | None:
        def _head() -> ObjectHead | None:
            try:
                resp = self._client.head_object(Bucket=self._bucket, Key=key)
            except Exception:
                return None
            return ObjectHead(
                content_type=resp.get("ContentType") or "application/octet-stream",
                size=int(resp.get("ContentLength") or 0),
            )

        return await asyncio.to_thread(_head)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)


class MemoryBackend:
    """In-process storage for tests and keyless local dev."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = (data, content_type)

    async def download(self, key: str) -> bytes:
        if key not in self._objects:
            raise KeyError(key)
        return self._objects[key][0]

    async def presigned_url(self, key: str, expires: int | None = None) -> str:
        return f"memory://{settings.s3_bucket}/{key}"

    async def presigned_upload(
        self, key: str, content_type: str, max_bytes: int, expires: int | None = None
    ) -> UploadCredential:
        # Sentinel: real browsers can't POST here. Tests simulate the landed
        # object via upload(); local dev uses MinIO (S3Backend).
        return UploadCredential(
            url=f"memory://{settings.s3_bucket}/",
            fields={"key": key, "Content-Type": content_type},
            max_bytes=max_bytes,
            expires_at=None,
        )

    async def head(self, key: str) -> ObjectHead | None:
        obj = self._objects.get(key)
        if obj is None:
            return None
        data, content_type = obj
        return ObjectHead(content_type=content_type, size=len(data))

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)


@lru_cache
def get_storage() -> StorageBackend:
    if settings.storage_provider == "memory":
        return MemoryBackend()
    return S3Backend()
