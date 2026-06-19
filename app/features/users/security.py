import uuid

import jwt
from fastapi_users import BaseUserManager, models
from fastapi_users.authentication import JWTStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.password import PasswordHelper
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings
from app.features.users.tokens import TokenStore, get_token_store

COOKIE_NAME = "shipyardauth"

ACCESS_AUDIENCE = ["fastapi-users:auth"]
REFRESH_AUDIENCE = ["fastapi-users:refresh"]


def _build_password_helper() -> PasswordHelper:
    """Argon2 via pwdlib (the fastapi-users default).

    Production uses the strong default parameters. The test suite runs with
    deliberately weak Argon2 cost parameters: hashing is otherwise the dominant
    cost of every auth test (the full suite drops from minutes to seconds).
    Never use the testing parameters outside of tests.
    """
    if settings.is_testing:
        fast = Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1)
        return PasswordHelper(PasswordHash((fast,)))
    return PasswordHelper()


# Shared password helper.
password_helper = _build_password_helper()


class RevocableJWTStrategy(JWTStrategy):
    """JWTStrategy that tags every token with a ``jti`` and honours the
    server-side denylist, so tokens can be revoked before they expire."""

    def __init__(self, store: TokenStore, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.store = store

    async def write_token(self, user: models.UP) -> str:
        jti = uuid.uuid4().hex
        ttl = self.lifetime_seconds or settings.access_token_lifetime_seconds
        await self.store.track(str(user.id), jti, ttl)
        data = {"sub": str(user.id), "aud": self.token_audience, "jti": jti}
        return generate_jwt(data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm)

    async def read_token(
        self, token: str | None, user_manager: BaseUserManager[models.UP, models.ID]
    ) -> models.UP | None:
        if token is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return None
        user_id = data.get("sub")
        jti = data.get("jti")
        if user_id is None:
            return None
        if jti is not None and await self.store.is_revoked(jti):
            return None
        try:
            parsed_id = user_manager.parse_id(user_id)
            return await user_manager.get(parsed_id)
        except Exception:
            return None

    async def destroy_token(self, token: str, user: models.UP) -> None:
        """Revoke the token server-side (real logout)."""
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return
        jti = data.get("jti")
        if jti is not None:
            ttl = self.lifetime_seconds or settings.access_token_lifetime_seconds
            await self.store.revoke(jti, ttl)


def get_jwt_strategy() -> RevocableJWTStrategy:
    """Short-lived, revocable access-token strategy."""
    return RevocableJWTStrategy(
        store=get_token_store(),
        secret=settings.secret_key,
        lifetime_seconds=settings.access_token_lifetime_seconds,
        token_audience=ACCESS_AUDIENCE,
    )


def get_refresh_strategy() -> RevocableJWTStrategy:
    """Longer-lived, revocable refresh-token strategy (separate audience)."""
    return RevocableJWTStrategy(
        store=get_token_store(),
        secret=settings.secret_key,
        lifetime_seconds=settings.refresh_token_lifetime_seconds,
        token_audience=REFRESH_AUDIENCE,
    )
