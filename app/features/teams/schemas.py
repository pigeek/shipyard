import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.features.teams.models import TeamRole


class TeamCreate(BaseModel):
    name: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class MemberRead(BaseModel):
    user_id: uuid.UUID
    email: str
    role: TeamRole


class MemberCreate(BaseModel):
    email: EmailStr
    role: TeamRole = TeamRole.member


class RoleUpdate(BaseModel):
    role: TeamRole
