from fastapi_users.authentication import JWTStrategy
from fastapi_users.password import PasswordHelper

from app.core.config import settings

COOKIE_NAME = "shipyardauth"

# Shared password helper (Argon2 via pwdlib, the fastapi-users default).
password_helper = PasswordHelper()


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.access_token_lifetime_seconds,
    )
