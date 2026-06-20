import uuid

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, TimestampMixin


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """Linked social-login account (Phase 7.7). The base FK targets ``user.id``;
    our user table is ``users``, so the foreign key is overridden here."""

    __tablename__ = "oauth_account"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    __tablename__ = "users"

    # Stripe customer id, populated lazily on first checkout.
    stripe_customer_id: Mapped[str | None] = mapped_column(default=None, nullable=True, index=True)

    # Preferred UI locale (i18n); null = negotiate from cookie / Accept-Language.
    locale: Mapped[str | None] = mapped_column(String(10), default=None, nullable=True)

    # Eager-loaded via a secondary SELECT (not a JOIN) so that existing scalar
    # User queries elsewhere don't need Result.unique() (lazy="joined" would).
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="selectin")
