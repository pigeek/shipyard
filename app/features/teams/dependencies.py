import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.features.teams import service
from app.features.teams.models import ROLE_RANK, Team, TeamMembership, TeamRole
from app.features.users.dependencies import current_active_user
from app.features.users.models import User


async def get_team_context(
    team_id: uuid.UUID = Path(...),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> tuple[Team, TeamMembership]:
    result = await service.get_team_for_user(session, team_id, user)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return result


def require_role(minimum: TeamRole):
    """Dependency factory: require at least ``minimum`` role on the team."""

    async def checker(
        context: tuple[Team, TeamMembership] = Depends(get_team_context),
    ) -> tuple[Team, TeamMembership]:
        _team, membership = context
        if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient team role",
            )
        return context

    return checker
