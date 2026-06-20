import uuid

from app.core.config import settings
from app.core.db import async_session_maker
from app.core.i18n import get_translations
from app.features.notifications.service import send_email
from app.features.users.models import User
from app.features.users.service import get_user_by_id


def _gettext(user: User):
    """gettext bound to a user's stored locale (emails run outside a request)."""
    return get_translations(user.locale or settings.default_locale).gettext


async def send_welcome_email(ctx: dict, user_id: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        _ = _gettext(user)
        await send_email(
            session,
            to=user.email,
            subject=_("Welcome aboard!"),
            html=f"<p>{_('Welcome aboard!')} ({user.email})</p>",
            template="welcome",
        )


async def send_verification_email(ctx: dict, user_id: str, token: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        _ = _gettext(user)
        link = f"{settings.base_url}/auth/verify?token={token}"
        await send_email(
            session,
            to=user.email,
            subject=_("Verify your email"),
            html=(
                f"<p>{_('Confirm your email address:')}</p>"
                f'<p><a href="{link}">{_("Verify email")}</a></p>'
            ),
            template="verify",
        )


async def send_password_reset_email(ctx: dict, user_id: str, token: str) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_id(session, uuid.UUID(user_id))
        if user is None:
            return
        _ = _gettext(user)
        link = f"{settings.base_url}/auth/reset?token={token}"
        await send_email(
            session,
            to=user.email,
            subject=_("Reset your password"),
            html=(
                f"<p>{_('Reset your password:')}</p>"
                f'<p><a href="{link}">{_("Choose a new password")}</a></p>'
            ),
            template="password_reset",
        )
