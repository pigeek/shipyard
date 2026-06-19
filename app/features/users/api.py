from fastapi import APIRouter

from app.core.config import settings
from app.features.users.auth_router import router as jwt_auth_router
from app.features.users.manager import cookie_backend, fastapi_users, jwt_backend
from app.features.users.oauth import google_oauth_client
from app.features.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter()

# Login / refresh / logout (JWT bearer + refresh) for REST clients. Only mounted
# when the bearer transport is enabled for this deployment (ADR 0001 §6).
if settings.auth_bearer_enabled:
    router.include_router(jwt_auth_router)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
router.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

# Social login — mounted only when a provider is configured (Phase 7.7). The
# OAuth callback signs the user in via the cookie backend (web shell) when cookie
# auth is enabled, otherwise via the bearer backend (token clients).
if google_oauth_client is not None:
    _oauth_backend = cookie_backend if settings.auth_cookie_enabled else jwt_backend
    router.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client,
            _oauth_backend,
            settings.secret_key,
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/auth/google",
        tags=["auth"],
    )
