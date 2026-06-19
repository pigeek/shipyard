"""Bearer auth router with refresh tokens and server-side revocation.

Replaces fastapi-users' stock ``get_auth_router`` for the JWT backend so that:
- login returns an **access + refresh** token pair,
- ``/refresh`` exchanges a valid refresh token for a new pair (rotating the old
  refresh token, which is revoked), and
- ``/logout`` and ``/logout-all`` revoke tokens server-side (ADR 0001 §4).

Cookie/SSR sessions reuse the same access strategy and store, so SSR logout can
revoke too (see `views.py`).
"""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.jwt import decode_jwt

from app.core.config import settings
from app.features.users.dependencies import current_active_user
from app.features.users.manager import UserManager, get_user_manager
from app.features.users.models import User
from app.features.users.schemas import RefreshRequest, TokenPair
from app.features.users.security import (
    REFRESH_AUDIENCE,
    get_jwt_strategy,
    get_refresh_strategy,
    get_token_store,
)

router = APIRouter(prefix="/auth/jwt", tags=["auth"])


async def _issue_pair(user: User) -> TokenPair:
    access = await get_jwt_strategy().write_token(user)
    refresh = await get_refresh_strategy().write_token(user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair)
async def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    manager: UserManager = Depends(get_user_manager),
) -> TokenPair:
    user = await manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="LOGIN_BAD_CREDENTIALS")
    return await _issue_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    manager: UserManager = Depends(get_user_manager),
) -> TokenPair:
    strategy = get_refresh_strategy()
    user = await strategy.read_token(payload.refresh_token, manager)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_REFRESH_TOKEN"
        )
    # Rotate: revoke the presented refresh token so it can't be reused.
    try:
        data = decode_jwt(
            payload.refresh_token, settings.secret_key, REFRESH_AUDIENCE, algorithms=["HS256"]
        )
        jti = data.get("jti")
        if jti is not None:
            await get_token_store().revoke(jti, settings.refresh_token_lifetime_seconds)
    except jwt.PyJWTError:
        pass
    return await _issue_pair(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, user: User = Depends(current_active_user)) -> None:
    """Revoke the presented bearer access token."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
        await get_jwt_strategy().destroy_token(token, user)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: User = Depends(current_active_user)) -> None:
    """Revoke every tracked token for the user ("log out everywhere")."""
    await get_token_store().revoke_user(str(user.id), settings.refresh_token_lifetime_seconds)
