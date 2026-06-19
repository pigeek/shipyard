from app.core.registry import FeatureModule
from app.features.teams.admin import TeamAdmin, TeamMembershipAdmin
from app.features.teams.api import router as api_router
from app.features.teams.views import router as ssr_router

feature = FeatureModule(
    name="teams",
    api_router=api_router,
    ssr_router=ssr_router,
    admin_views=[TeamAdmin, TeamMembershipAdmin],
)
