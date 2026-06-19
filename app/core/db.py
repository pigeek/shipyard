from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _engine_kwargs() -> dict[str, Any]:
    """Engine options, with SQLite (test/dev) configured for a shared
    in-memory database: a single connection via StaticPool so every session —
    including the app's request handlers and the test fixtures — sees the same
    schema and data. This is what makes the test suite fast (no file fsync)."""
    if settings.database_url.startswith("sqlite"):
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    return {"pool_pre_ping": True}


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug and not settings.is_testing,
    **_engine_kwargs(),
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with async_session_maker() as session:
        yield session
