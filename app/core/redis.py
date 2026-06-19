from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, Request

from app.core.config import settings


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def init_arq_pool(app: FastAPI) -> None:
    app.state.arq_pool = await create_pool(redis_settings())


async def close_arq_pool(app: FastAPI) -> None:
    pool: ArqRedis | None = getattr(app.state, "arq_pool", None)
    if pool is not None:
        await pool.aclose()


def get_arq_pool(request: Request) -> ArqRedis:
    """FastAPI dependency returning the shared arq job queue pool."""
    return request.app.state.arq_pool


async def enqueue_job(app: FastAPI, function: str, *args, **kwargs) -> None:
    """Enqueue an arq job from anywhere that has the app reference."""
    pool: ArqRedis = app.state.arq_pool
    await pool.enqueue_job(function, *args, **kwargs)
