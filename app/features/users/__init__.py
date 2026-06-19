from app.core.config import settings
from app.core.registry import FeatureModule
from app.features.users.admin import UserAdmin
from app.features.users.api import router as api_router
from app.features.users.views import router as ssr_router

feature = FeatureModule(
    name="users",
    api_router=api_router,
    # The SSR auth pages rely on the cookie transport; a bearer-only deployment
    # (auth_cookie_enabled=False) does not expose them (ADR 0001 §6).
    ssr_router=ssr_router if settings.auth_cookie_enabled else None,
    admin_views=[UserAdmin],
)
