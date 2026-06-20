from arq import cron

from app.core.config import settings
from app.core.db import async_session_maker
from app.features.files import service


async def cleanup_orphaned_uploads(ctx: dict) -> int:
    """Periodic sweep: drop pending file rows whose presigned form expired
    without the object ever landing in the bucket. Returns the count removed."""
    async with async_session_maker() as session:
        return await service.cleanup_orphaned_uploads(
            session, max_age_seconds=settings.orphan_upload_max_age
        )


# Run hourly; rows are only removed once past orphan_upload_max_age (default 24h).
cleanup_orphaned_uploads_cron = cron(cleanup_orphaned_uploads, minute=0)
