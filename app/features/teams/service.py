import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.teams.models import Team, TeamMembership, TeamRole
from app.features.users.models import User
from app.features.users.service import get_user_by_email


class TeamServiceError(Exception):
    """Raised for expected, user-facing team operation failures."""


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "team"
    return f"{base}-{uuid.uuid4().hex[:6]}"


async def create_team(session: AsyncSession, *, name: str, owner: User) -> Team:
    team = Team(name=name.strip() or "Untitled", slug=slugify(name))
    team.memberships.append(TeamMembership(user_id=owner.id, role=TeamRole.owner))
    session.add(team)
    await session.commit()
    await session.refresh(team)
    return team


async def list_teams_for_user(session: AsyncSession, user: User) -> list[Team]:
    result = await session.execute(
        select(Team)
        .join(TeamMembership)
        .where(TeamMembership.user_id == user.id)
        .order_by(Team.created_at)
    )
    return list(result.scalars().unique())


async def get_membership(
    session: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID
) -> TeamMembership | None:
    result = await session.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_team_for_user(
    session: AsyncSession, team_id: uuid.UUID, user: User
) -> tuple[Team, TeamMembership] | None:
    """Tenant-scoped fetch: returns (team, membership) only if the user belongs."""
    membership = await get_membership(session, team_id, user.id)
    if membership is None:
        return None
    team = await session.get(Team, team_id)
    if team is None:
        return None
    return team, membership


async def list_members(session: AsyncSession, team_id: uuid.UUID) -> list[TeamMembership]:
    result = await session.execute(
        select(TeamMembership)
        .options(selectinload(TeamMembership.user))
        .where(TeamMembership.team_id == team_id)
        .order_by(TeamMembership.created_at)
    )
    return list(result.scalars())


async def add_member(
    session: AsyncSession, *, team: Team, email: str, role: TeamRole
) -> TeamMembership:
    user = await get_user_by_email(session, email)
    if user is None:
        raise TeamServiceError("No user with that email.")
    if await get_membership(session, team.id, user.id) is not None:
        raise TeamServiceError("That user is already a member.")
    membership = TeamMembership(team_id=team.id, user_id=user.id, role=role)
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership


async def change_role(
    session: AsyncSession, *, team_id: uuid.UUID, user_id: uuid.UUID, role: TeamRole
) -> TeamMembership:
    membership = await get_membership(session, team_id, user_id)
    if membership is None:
        raise TeamServiceError("Not a member of this team.")
    if (
        membership.role == TeamRole.owner
        and role != TeamRole.owner
        and await _count_owners(session, team_id) <= 1
    ):
        raise TeamServiceError("A team must keep at least one owner.")
    membership.role = role
    await session.commit()
    await session.refresh(membership)
    return membership


async def remove_member(session: AsyncSession, *, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    membership = await get_membership(session, team_id, user_id)
    if membership is None:
        raise TeamServiceError("Not a member of this team.")
    if membership.role == TeamRole.owner and await _count_owners(session, team_id) <= 1:
        raise TeamServiceError("A team must keep at least one owner.")
    await session.delete(membership)
    await session.commit()


async def _count_owners(session: AsyncSession, team_id: uuid.UUID) -> int:
    result = await session.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.role == TeamRole.owner,
        )
    )
    return len(list(result.scalars()))
