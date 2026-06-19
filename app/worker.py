"""arq worker entrypoint: collects task functions + cron jobs from features.

Run with:  arq app.worker.WorkerSettings
"""

from app.core.db import async_session_maker
from app.core.redis import redis_settings
from app.core.registry import discover_features

_features = discover_features()

_functions = [fn for feature in _features for fn in feature.tasks]
_cron_jobs = [job for feature in _features for job in feature.cron]


async def _startup(ctx: dict) -> None:
    ctx["session_maker"] = async_session_maker


async def _shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    redis_settings = redis_settings()
    functions = _functions
    cron_jobs = _cron_jobs
    on_startup = _startup
    on_shutdown = _shutdown
