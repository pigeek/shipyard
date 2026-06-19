import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.features.teams import service
from app.features.teams.models import ROLE_RANK, Team, TeamMembership, TeamRole
from app.features.users.dependencies import current_active_user, ssr_required_user
from app.features.users.models import User


async def _load_context(
    session: AsyncSession, team_id: uuid.UUID, user: User
) -> tuple[Team, TeamMembership]:
    result = await service.get_team_for_user(session, team_id, user)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return result


async def get_team_context(
    team_id: uuid.UUID = Path(...),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> tuple[Team, TeamMembership]:
    return await _load_context(session, team_id, user)


async def get_team_context_ssr(
    team_id: uuid.UUID = Path(...),
    user: User = Depends(ssr_required_user),
    session: AsyncSession = Depends(get_async_session),
) -> tuple[Team, TeamMembership]:
    """Same as get_team_context but redirects logged-out browsers to login."""
    return await _load_context(session, team_id, user)


def _check_role(
    context: tuple[Team, TeamMembership], minimum: TeamRole
) -> tuple[Team, TeamMembership]:
    _team, membership = context
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient team role")
    return context


def require_role(minimum: TeamRole):
    """Dependency factory (REST): require at least ``minimum`` role on the team."""

    async def checker(
        context: tuple[Team, TeamMembership] = Depends(get_team_context),
    ) -> tuple[Team, TeamMembership]:
        return _check_role(context, minimum)

    return checker


def require_role_ssr(minimum: TeamRole):
    """Dependency factory (SSR): role guard that redirects logged-out browsers."""

    async def checker(
        context: tuple[Team, TeamMembership] = Depends(get_team_context_ssr),
    ) -> tuple[Team, TeamMembership]:
        return _check_role(context, minimum)

    return checker
