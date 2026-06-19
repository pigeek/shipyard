from app.core.registry import FeatureModule
from app.features.users.admin import UserAdmin
from app.features.users.api import router as api_router
from app.features.users.views import router as ssr_router

feature = FeatureModule(
    name="users",
    api_router=api_router,
    ssr_router=ssr_router,
    admin_views=[UserAdmin],
)
