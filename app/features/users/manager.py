import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_async_session
from app.features.users.models import OAuthAccount, User
from app.features.users.security import (
    COOKIE_NAME,
    get_jwt_strategy,
    password_helper,
)


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        await self._enqueue(request, "send_welcome_email", str(user.id))
        # Kick off email verification right after registration.
        if not user.is_verified:
            await self.request_verify(user, request)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        await self._enqueue(request, "send_verification_email", str(user.id), token)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        await self._enqueue(request, "send_password_reset_email", str(user.id), token)

    @staticmethod
    async def _enqueue(request: Request | None, function: str, *args: object) -> None:
        if request is None:
            return
        pool = getattr(request.app.state, "arq_pool", None)
        if pool is not None:
            await pool.enqueue_job(function, *args)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db, password_helper)


bearer_transport = BearerTransport(tokenUrl="api/v1/auth/jwt/login")
cookie_transport = CookieTransport(
    cookie_name=COOKIE_NAME,
    cookie_max_age=settings.access_token_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)

jwt_backend = AuthenticationBackend(
    name="jwt", transport=bearer_transport, get_strategy=get_jwt_strategy
)
cookie_backend = AuthenticationBackend(
    name="cookie", transport=cookie_transport, get_strategy=get_jwt_strategy
)


def _enabled_backends() -> list[AuthenticationBackend]:
    """Which transports the API authenticates with — a deployment choice
    (ADR 0001 §6). The config validator guarantees at least one is enabled."""
    backends: list[AuthenticationBackend] = []
    if settings.auth_bearer_enabled:
        backends.append(jwt_backend)
    if settings.auth_cookie_enabled:
        backends.append(cookie_backend)
    return backends


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, _enabled_backends())
