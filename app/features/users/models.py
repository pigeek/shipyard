from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    __tablename__ = "users"

    # Stripe customer id, populated lazily on first checkout.
    stripe_customer_id: Mapped[str | None] = mapped_column(default=None, nullable=True, index=True)
