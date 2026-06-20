from app.core.registry import FeatureModule
from app.features.files.admin import StoredFileAdmin
from app.features.files.api import router as api_router
from app.features.files.tasks import (
    cleanup_orphaned_uploads,
    cleanup_orphaned_uploads_cron,
)

feature = FeatureModule(
    name="files",
    api_router=api_router,
    admin_views=[StoredFileAdmin],
    tasks=[cleanup_orphaned_uploads],
    cron=[cleanup_orphaned_uploads_cron],
)
