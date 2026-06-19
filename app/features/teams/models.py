import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, TimestampMixin, UUIDMixin
from app.features.users.models import User


class TeamRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


# Higher number = more privilege; used by role guards.
ROLE_RANK: dict["TeamRole", int] = {
    TeamRole.member: 1,
    TeamRole.admin: 2,
    TeamRole.owner: 3,
}


class Team(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)

    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMembership(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[TeamRole] = mapped_column(
        SAEnum(TeamRole, name="team_role"), default=TeamRole.member
    )

    team: Mapped["Team"] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(lazy="joined")
