from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.db import async_session_maker
from app.features.users.security import password_helper
from app.features.users.service import get_user_by_email

ADMIN_SESSION_KEY = "admin_user_id"


class AdminAuth(AuthenticationBackend):
    """Session-based admin login restricted to superusers."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))
        async with async_session_maker() as session:
            user = await get_user_by_email(session, email)
        if user is None or not user.is_active or not user.is_superuser:
            return False
        verified, _ = password_helper.verify_and_update(password, user.hashed_password)
        if not verified:
            return False
        request.session[ADMIN_SESSION_KEY] = str(user.id)
        return True

    async def logout(self, request: Request) -> bool:
        request.session.pop(ADMIN_SESSION_KEY, None)
        return True

    async def authenticate(self, request: Request) -> bool:
        return ADMIN_SESSION_KEY in request.session
