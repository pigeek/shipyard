"""Server-side token state: refresh tokens and revocation (ADR 0001 §4).

Stateless JWTs cannot be revoked before they expire, which breaks "log out",
"log out everywhere", and leaked-token containment. We keep JWTs (good for the
bearer/mobile path and horizontal scaling) but add a small server-side store:

- every issued access/refresh token carries a ``jti`` claim that is *tracked*
  per user, and
- a ``jti`` can be placed on a *denylist*; a denylisted token fails validation
  even though its signature is still valid and unexpired.

The store is backed by Redis in production and by an in-process dict in testing
(no Redis dependency in the unit suite). Both implement :class:`TokenStore`.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class TokenStore(Protocol):
    async def track(self, user_id: str, jti: str, ttl: int) -> None:
        """Record a freshly issued token so it can be revoked later."""
        ...

    async def is_revoked(self, jti: str) -> bool:
        """True if this token id has been denylisted."""
        ...

    async def revoke(self, jti: str, ttl: int) -> None:
        """Denylist a single token id (e.g. on logout)."""
        ...

    async def revoke_user(self, user_id: str, ttl: int) -> None:
        """Denylist every tracked token for a user ("log out everywhere")."""
        ...


class MemoryTokenStore:
    """In-process store for tests/dev. TTLs are ignored — fine for a short-lived
    process; production uses Redis where TTLs prune expired state."""

    def __init__(self) -> None:
        self._user_jtis: dict[str, set[str]] = {}
        self._revoked: set[str] = set()

    async def track(self, user_id: str, jti: str, ttl: int) -> None:
        self._user_jtis.setdefault(user_id, set()).add(jti)

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    async def revoke(self, jti: str, ttl: int) -> None:
        self._revoked.add(jti)

    async def revoke_user(self, user_id: str, ttl: int) -> None:
        self._revoked.update(self._user_jtis.get(user_id, set()))


class RedisTokenStore:
    """Redis-backed store. A user's live token ids live in a set; revocation
    writes a short-lived denylist key per ``jti`` (TTL ≥ the token's remaining
    lifetime, after which the token is expired anyway)."""

    def __init__(self, redis: object) -> None:
        self._redis = redis  # redis.asyncio.Redis

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"auth:user:{user_id}:jtis"

    @staticmethod
    def _revoked_key(jti: str) -> str:
        return f"auth:revoked:{jti}"

    async def track(self, user_id: str, jti: str, ttl: int) -> None:
        await self._redis.sadd(self._user_key(user_id), jti)  # type: ignore[attr-defined]
        await self._redis.expire(self._user_key(user_id), ttl)  # type: ignore[attr-defined]

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._redis.exists(self._revoked_key(jti)))  # type: ignore[attr-defined]

    async def revoke(self, jti: str, ttl: int) -> None:
        await self._redis.set(self._revoked_key(jti), "1", ex=max(ttl, 1))  # type: ignore[attr-defined]

    async def revoke_user(self, user_id: str, ttl: int) -> None:
        jtis = await self._redis.smembers(self._user_key(user_id))  # type: ignore[attr-defined]
        for raw in jtis:
            jti = raw.decode() if isinstance(raw, bytes) else raw
            await self.revoke(jti, ttl)
        await self._redis.delete(self._user_key(user_id))  # type: ignore[attr-defined]


_store: TokenStore | None = None


def get_token_store() -> TokenStore:
    """Singleton token store: in-memory under tests, Redis otherwise."""
    global _store
    if _store is None:
        if settings.is_testing:
            _store = MemoryTokenStore()
        else:
            import redis.asyncio as redis

            _store = RedisTokenStore(redis.from_url(settings.redis_url))
    return _store
