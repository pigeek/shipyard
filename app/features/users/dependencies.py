from fastapi import Depends, Request

from app.features.users.manager import fastapi_users
from app.features.users.models import User

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
_optional_user = fastapi_users.current_user(active=True, optional=True)


async def load_current_user(
    request: Request, user: User | None = Depends(_optional_user)
) -> User | None:
    """SSR dependency: stash the (optional) user on request.state for templates."""
    request.state.current_user = user
    return user
