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


class RequiresLogin(Exception):
    """Raised by SSR routes when no user is authenticated.

    An app-level handler turns this into a redirect to the login page,
    rather than the 401 that REST clients receive.
    """

    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


async def ssr_required_user(request: Request, user: User | None = Depends(_optional_user)) -> User:
    """Like current_active_user, but redirects browsers to login when absent."""
    request.state.current_user = user
    if user is None:
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        raise RequiresLogin(target)
    return user
