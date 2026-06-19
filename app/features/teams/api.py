import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.features.teams import service
from app.features.teams.dependencies import get_team_context, require_role
from app.features.teams.models import Team, TeamMembership, TeamRole
from app.features.teams.schemas import (
    MemberCreate,
    MemberRead,
    RoleUpdate,
    TeamCreate,
    TeamRead,
)
from app.features.teams.service import TeamServiceError
from app.features.users.dependencies import current_active_user
from app.features.users.models import User

router = APIRouter(prefix="/teams", tags=["teams"])


def _member_read(membership: TeamMembership) -> MemberRead:
    return MemberRead(user_id=membership.user_id, email=membership.user.email, role=membership.role)


@router.get("", response_model=list[TeamRead])
async def list_teams(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await service.list_teams_for_user(session, user)


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await service.create_team(session, name=payload.name, owner=user)


@router.get("/{team_id}", response_model=list[MemberRead])
async def list_members(
    context: tuple[Team, TeamMembership] = Depends(get_team_context),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    members = await service.list_members(session, team.id)
    return [_member_read(m) for m in members]


@router.post(
    "/{team_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    payload: MemberCreate,
    context: tuple[Team, TeamMembership] = Depends(require_role(TeamRole.admin)),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    try:
        membership = await service.add_member(
            session, team=team, email=payload.email, role=payload.role
        )
    except TeamServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.refresh(membership, ["user"])
    return _member_read(membership)


@router.patch("/{team_id}/members/{user_id}", response_model=MemberRead)
async def update_member_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    context: tuple[Team, TeamMembership] = Depends(require_role(TeamRole.admin)),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    try:
        membership = await service.change_role(
            session, team_id=team.id, user_id=user_id, role=payload.role
        )
    except TeamServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.refresh(membership, ["user"])
    return _member_read(membership)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    context: tuple[Team, TeamMembership] = Depends(require_role(TeamRole.admin)),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    try:
        await service.remove_member(session, team_id=team.id, user_id=user_id)
    except TeamServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
