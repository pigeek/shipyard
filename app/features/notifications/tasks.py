import uuid

from app.core.config import settings
from app.core.db import async_session_maker
from app.features.notifications.service import send_email
from app.features.users.service import get_user_by_id


async def send_welcome_email(ctx: dict, user_id: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        await send_email(
            session,
            to=user.email,
            subject=f"Welcome to {settings.app_name}",
            html=f"<p>Welcome aboard, {user.email}!</p>",
            template="welcome",
        )


async def send_verification_email(ctx: dict, user_id: str, token: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        link = f"{settings.base_url}/auth/verify?token={token}"
        await send_email(
            session,
            to=user.email,
            subject="Verify your email",
            html=(f'<p>Confirm your email address:</p><p><a href="{link}">Verify email</a></p>'),
            template="verify",
        )


async def send_password_reset_email(ctx: dict, user_id: str, token: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        link = f"{settings.base_url}/auth/reset?token={token}"
        await send_email(
            session,
            to=user.email,
            subject="Reset your password",
            html=(f'<p>Reset your password:</p><p><a href="{link}">Choose a new password</a></p>'),
            template="password_reset",
        )
