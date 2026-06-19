# ruff: noqa: E402, I001 - env must be set before importing app modules
import os

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")  # shared in-memory (StaticPool)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.core.db import async_session_maker, engine  # noqa: E402
from app.core.models import Base  # noqa: E402
from app.core.registry import discover_features  # noqa: E402

# Import every feature's models before create_all.
discover_features()


class _FakeArqPool:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, function: str, *args, **kwargs) -> None:
        self.jobs.append((function, args, kwargs))


@pytest_asyncio.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def app_with_pool(db):
    from app.main import app

    app.state.arq_pool = _FakeArqPool()
    return app


@pytest_asyncio.fixture
async def client(app_with_pool):
    transport = httpx.ASGITransport(app=app_with_pool)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
