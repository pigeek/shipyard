import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.features.files.models import FileStatus


class StartUploadRequest(BaseModel):
    """Begin a direct-to-bucket upload: returns a scoped presigned POST form."""

    filename: str
    content_type: str
    # Optionally scope the file to a team the caller belongs to (else owner-scoped).
    team_id: uuid.UUID | None = None


class UploadCredentialOut(BaseModel):
    """The scoped, short-lived presigned upload form the client POSTs the object to."""

    url: str
    fields: dict[str, str]
    max_bytes: int
    expires_at: str | None = None


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    filename: str
    content_type: str
    size: int
    status: FileStatus
    owner_id: uuid.UUID | None
    team_id: uuid.UUID | None
    created_at: datetime


class StartUploadResponse(BaseModel):
    file: FileRead
    upload: UploadCredentialOut


class DownloadUrlResponse(BaseModel):
    url: str
