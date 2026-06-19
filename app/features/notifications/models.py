import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDMixin


class EmailStatus(enum.StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class EmailLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_logs"

    recipient: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    template: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[EmailStatus] = mapped_column(
        SAEnum(EmailStatus, name="email_status"), default=EmailStatus.pending
    )
    error: Mapped[str | None] = mapped_column(Text, default=None)
