from app.core.registry import FeatureModule
from app.features.notifications.admin import EmailLogAdmin
from app.features.notifications.api import router as api_router
from app.features.notifications.tasks import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from app.features.notifications.ws import router as ws_router

feature = FeatureModule(
    name="notifications",
    api_router=api_router,
    ws_router=ws_router,
    admin_views=[EmailLogAdmin],
    tasks=[send_welcome_email, send_verification_email, send_password_reset_email],
)
