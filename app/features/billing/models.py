import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDMixin


class Plan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plans"

    stripe_price_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)  # in the currency's smallest unit
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    interval: Mapped[str] = mapped_column(String(16), default="month")
    is_active: Mapped[bool] = mapped_column(default=True)


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(32), default="incomplete")
    current_period_end: Mapped[datetime | None] = mapped_column(default=None)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)


class Invoice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    amount_paid: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text, default=None)


class WebhookEvent(UUIDMixin, TimestampMixin, Base):
    """Idempotency ledger: the unique stripe_event_id makes replays no-ops."""

    __tablename__ = "webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(120))
    payload: Mapped[str | None] = mapped_column(Text, default=None)
    processed: Mapped[bool] = mapped_column(default=False)
