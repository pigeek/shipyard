import enum
import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDMixin


class FileStatus(enum.StrEnum):
    # The presigned form was issued but we have not verified the object landed.
    pending = "pending"
    # Confirmed: the object exists in the bucket (size/content-type recorded).
    stored = "stored"


class StoredFile(UUIDMixin, TimestampMixin, Base):
    """A single object in the bucket plus its metadata. Scoping is configurable
    (ADR/feature decision): a file may be owned by a user, a team, or both.
    Access checks honor whichever scope columns are set."""

    __tablename__ = "stored_files"

    # The object key in the bucket. Unique so two rows never alias one object.
    key: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[FileStatus] = mapped_column(
        SAEnum(FileStatus, name="file_status"), default=FileStatus.pending, index=True
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), default=None, index=True
    )
