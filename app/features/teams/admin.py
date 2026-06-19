from sqladmin import ModelView

from app.features.teams.models import Team, TeamMembership


class TeamAdmin(ModelView, model=Team):
    name = "Team"
    name_plural = "Teams"
    icon = "fa-solid fa-users-rectangle"
    column_list = [Team.id, Team.name, Team.slug, Team.created_at]
    column_searchable_list = [Team.name, Team.slug]
    column_sortable_list = [Team.name, Team.created_at]


class TeamMembershipAdmin(ModelView, model=TeamMembership):
    name = "Membership"
    name_plural = "Memberships"
    icon = "fa-solid fa-user-tag"
    column_list = [
        TeamMembership.id,
        TeamMembership.team_id,
        TeamMembership.user_id,
        TeamMembership.role,
    ]
