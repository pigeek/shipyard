import contextlib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.core.db import get_async_session
from app.features.teams import service
from app.features.teams.dependencies import get_team_context_ssr, require_role_ssr
from app.features.teams.models import ROLE_RANK, Team, TeamMembership, TeamRole
from app.features.teams.service import TeamServiceError
from app.features.users.dependencies import ssr_required_user
from app.features.users.models import User
from app.web.csrf import verify_csrf
from app.web.templating import render

router = APIRouter(tags=["teams-ssr"])


@router.get("/teams")
async def teams_list(
    request: Request,
    user: User = Depends(ssr_required_user),
    session: AsyncSession = Depends(get_async_session),
):
    teams = await service.list_teams_for_user(session, user)
    return render(request, "teams/list.html", {"teams": teams})


@router.post("/teams")
async def teams_create(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    user: User = Depends(ssr_required_user),
    session: AsyncSession = Depends(get_async_session),
):
    form = await request.form()
    team = await service.create_team(session, name=str(form.get("name", "")), owner=user)
    return RedirectResponse(f"/teams/{team.id}", status_code=303)


@router.get("/teams/{team_id}")
async def team_detail(
    request: Request,
    context: tuple[Team, TeamMembership] = Depends(get_team_context_ssr),
    session: AsyncSession = Depends(get_async_session),
):
    team, membership = context
    members = await service.list_members(session, team.id)
    can_manage = ROLE_RANK[membership.role] >= ROLE_RANK[TeamRole.admin]
    return render(
        request,
        "teams/detail.html",
        {
            "team": team,
            "members": members,
            "my_role": membership.role.value,
            "can_manage": can_manage,
            "roles": [r.value for r in TeamRole],
        },
    )


@router.post("/teams/{team_id}/members")
async def team_add_member(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    context: tuple[Team, TeamMembership] = Depends(require_role_ssr(TeamRole.admin)),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    form = await request.form()
    role_value = str(form.get("role", TeamRole.member.value))
    try:
        await service.add_member(
            session,
            team=team,
            email=str(form.get("email", "")),
            role=TeamRole(role_value),
        )
    except (TeamServiceError, ValueError):
        # Re-render detail with an error flash.
        members = await service.list_members(session, team.id)
        return render(
            request,
            "teams/detail.html",
            {
                "team": team,
                "members": members,
                "my_role": _membership.role.value,
                "can_manage": True,
                "roles": [r.value for r in TeamRole],
                "flash": "Could not add member (unknown email or already a member).",
                "flash_level": "error",
            },
            status_code=400,
        )
    return RedirectResponse(f"/teams/{team.id}", status_code=303)


@router.post("/teams/{team_id}/members/{user_id}/remove")
async def team_remove_member(
    user_id: uuid.UUID,
    request: Request,
    _csrf: None = Depends(verify_csrf),
    context: tuple[Team, TeamMembership] = Depends(require_role_ssr(TeamRole.admin)),
    session: AsyncSession = Depends(get_async_session),
):
    team, _membership = context
    with contextlib.suppress(TeamServiceError):
        await service.remove_member(session, team_id=team.id, user_id=user_id)
    return RedirectResponse(f"/teams/{team.id}", status_code=303)
