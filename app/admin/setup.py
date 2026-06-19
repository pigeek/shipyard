from collections.abc import Sequence

from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import AdminAuth
from app.core.config import settings
from app.core.db import engine
from app.core.registry import FeatureModule


def setup_admin(app: FastAPI, features: Sequence[FeatureModule]) -> Admin:
    """Mount SQLAdmin and register every feature's admin views."""
    admin = Admin(
        app,
        engine,
        title=f"{settings.app_name} Admin",
        authentication_backend=AdminAuth(secret_key=settings.secret_key),
    )
    for feature in features:
        for view in feature.admin_views:
            admin.add_view(view)
    return admin
