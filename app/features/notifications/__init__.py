from app.core.registry import FeatureModule
from app.features.notifications.admin import EmailLogAdmin
from app.features.notifications.tasks import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)

feature = FeatureModule(
    name="notifications",
    admin_views=[EmailLogAdmin],
    tasks=[send_welcome_email, send_verification_email, send_password_reset_email],
)
