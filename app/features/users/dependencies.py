from fastapi import Depends, Request, WebSocket

from app.features.users.manager import UserManager, fastapi_users, get_user_manager
from app.features.users.models import User
from app.features.users.security import COOKIE_NAME, get_jwt_strategy

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


async def ws_current_user(
    websocket: WebSocket,
    user_manager: UserManager = Depends(get_user_manager),
) -> User | None:
    """Authenticate a WebSocket connection, returning the user or ``None``.

    Browsers can't set headers on a WebSocket, so the same-origin SSR/SPA relies
    on the httpOnly session **cookie** (sent automatically). Non-browser clients
    may instead pass the bearer token as ``?token=`` or an ``Authorization``
    header. The token is validated with the same revocable JWT strategy the REST
    API uses, so a revoked token can't open a socket.
    """
    token = websocket.cookies.get(COOKIE_NAME) or websocket.query_params.get("token")
    if token is None:
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if token is None:
        return None
    user = await get_jwt_strategy().read_token(token, user_manager)
    if user is None or not user.is_active:
        return None
    return user


async def ssr_required_user(request: Request, user: User | None = Depends(_optional_user)) -> User:
    """Like current_active_user, but redirects browsers to login when absent."""
    request.state.current_user = user
    if user is None:
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        raise RequiresLogin(target)
    return user
