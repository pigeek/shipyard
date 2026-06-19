from fastapi import APIRouter

from app.features.users.manager import fastapi_users, jwt_backend
from app.features.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter()

# Login / logout (JWT bearer) for REST clients.
router.include_router(fastapi_users.get_auth_router(jwt_backend), prefix="/auth/jwt", tags=["auth"])
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
