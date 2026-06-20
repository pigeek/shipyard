import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import UploadCredential, get_storage
from app.features.files.models import FileStatus, StoredFile
from app.features.teams import service as teams_service
from app.features.users.models import User


class FileServiceError(Exception):
    """Domain error carrying an HTTP status for the router to translate."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _build_key(*, owner_id: uuid.UUID | None, team_id: uuid.UUID | None, filename: str) -> str:
    """Namespace objects by their scope so keys never collide across tenants."""
    scope = f"teams/{team_id}" if team_id is not None else f"users/{owner_id}"
    return f"{scope}/{uuid.uuid4().hex}_{filename}"


async def _assert_team_member(session: AsyncSession, team_id: uuid.UUID, user: User) -> None:
    membership = await teams_service.get_membership(session, team_id, user.id)
    if membership is None:
        raise FileServiceError("Team not found", status_code=404)


def _can_access(stored: StoredFile, user: User, team_ids: set[uuid.UUID]) -> bool:
    if stored.owner_id is not None and stored.owner_id == user.id:
        return True
    return stored.team_id is not None and stored.team_id in team_ids


async def _user_team_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    teams = await teams_service.list_teams_for_user(session, user)
    return {team.id for team in teams}


async def start_upload(
    session: AsyncSession,
    *,
    user: User,
    filename: str,
    content_type: str,
    team_id: uuid.UUID | None = None,
) -> tuple[StoredFile, UploadCredential]:
    """Create a pending row and hand back a scoped, short-lived presigned POST.
    The object bytes go straight to the bucket — they never transit the API."""
    if team_id is not None:
        await _assert_team_member(session, team_id, user)
    owner_id = None if team_id is not None else user.id
    key = _build_key(owner_id=owner_id, team_id=team_id, filename=filename)
    stored = StoredFile(
        key=key,
        filename=filename,
        content_type=content_type,
        owner_id=owner_id,
        team_id=team_id,
        status=FileStatus.pending,
    )
    session.add(stored)
    await session.commit()
    await session.refresh(stored)

    cred = await get_storage().presigned_upload(
        key, content_type, max_bytes=settings.max_upload_size
    )
    return stored, cred


async def _get_accessible(session: AsyncSession, file_id: uuid.UUID, user: User) -> StoredFile:
    stored = await session.get(StoredFile, file_id)
    if stored is None:
        raise FileServiceError("File not found", status_code=404)
    team_ids = await _user_team_ids(session, user)
    if not _can_access(stored, user, team_ids):
        raise FileServiceError("File not found", status_code=404)
    return stored


async def confirm_upload(session: AsyncSession, *, file_id: uuid.UUID, user: User) -> StoredFile:
    """Finalize a direct upload: verify the object actually landed (the client's
    word is not enough), record its real size/content-type, flip to 'stored'.
    Idempotent — confirming an already-stored file is a no-op."""
    stored = await _get_accessible(session, file_id, user)
    if stored.status == FileStatus.stored:
        return stored

    head = await get_storage().head(stored.key)
    if head is None:
        raise FileServiceError("Upload not found", status_code=409)

    stored.content_type = head.content_type
    stored.size = head.size
    stored.status = FileStatus.stored
    await session.commit()
    await session.refresh(stored)
    return stored


async def list_files(session: AsyncSession, *, user: User) -> list[StoredFile]:
    """Stored files the user can see: their own plus their teams'. Pending
    (never-confirmed) placeholders are excluded."""
    team_ids = await _user_team_ids(session, user)
    conditions = [StoredFile.owner_id == user.id]
    if team_ids:
        conditions.append(StoredFile.team_id.in_(team_ids))
    result = await session.execute(
        select(StoredFile)
        .where(StoredFile.status == FileStatus.stored)
        .where(or_(*conditions))
        .order_by(StoredFile.created_at.desc())
    )
    return list(result.scalars())


async def get_download_url(session: AsyncSession, *, file_id: uuid.UUID, user: User) -> str:
    stored = await _get_accessible(session, file_id, user)
    return await get_storage().presigned_url(stored.key)


async def delete_file(session: AsyncSession, *, file_id: uuid.UUID, user: User) -> None:
    stored = await _get_accessible(session, file_id, user)
    # Best-effort object delete; the row goes regardless.
    with contextlib.suppress(Exception):
        await get_storage().delete(stored.key)
    await session.delete(stored)
    await session.commit()


async def cleanup_orphaned_uploads(session: AsyncSession, *, max_age_seconds: int) -> int:
    """Delete pending rows whose presigned form expired without the object ever
    landing. Returns the number removed. Used by the periodic sweep (tasks.py)."""
    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    result = await session.execute(
        select(StoredFile)
        .where(StoredFile.status == FileStatus.pending)
        .where(StoredFile.created_at < cutoff)
    )
    storage = get_storage()
    removed = 0
    for stored in result.scalars():
        if await storage.head(stored.key) is not None:
            # The object landed but confirm was never called — promote instead of drop.
            continue
        await session.delete(stored)
        removed += 1
    await session.commit()
    return removed
