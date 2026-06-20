import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.features.files import service
from app.features.files.schemas import (
    DownloadUrlResponse,
    FileRead,
    StartUploadRequest,
    StartUploadResponse,
    UploadCredentialOut,
)
from app.features.files.service import FileServiceError
from app.features.users.dependencies import current_active_user
from app.features.users.models import User

router = APIRouter(prefix="/files", tags=["files"])


def _translate(exc: FileServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("", response_model=StartUploadResponse, status_code=status.HTTP_201_CREATED)
async def start_upload(
    payload: StartUploadRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> StartUploadResponse:
    """Begin a direct-to-bucket upload: create a pending file row and return a
    scoped, short-lived presigned POST form. The browser uploads the bytes
    straight to the bucket, then calls confirm-upload."""
    try:
        stored, cred = await service.start_upload(
            session,
            user=user,
            filename=payload.filename,
            content_type=payload.content_type,
            team_id=payload.team_id,
        )
    except FileServiceError as exc:
        raise _translate(exc) from exc
    return StartUploadResponse(
        file=FileRead.model_validate(stored),
        upload=UploadCredentialOut(
            url=cred.url, fields=cred.fields, max_bytes=cred.max_bytes, expires_at=cred.expires_at
        ),
    )


@router.post("/{file_id}/confirm", response_model=FileRead)
async def confirm_upload(
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> FileRead:
    try:
        stored = await service.confirm_upload(session, file_id=file_id, user=user)
    except FileServiceError as exc:
        raise _translate(exc) from exc
    return FileRead.model_validate(stored)


@router.get("", response_model=list[FileRead])
async def list_files(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[FileRead]:
    files = await service.list_files(session, user=user)
    return [FileRead.model_validate(f) for f in files]


@router.get("/{file_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> DownloadUrlResponse:
    try:
        url = await service.get_download_url(session, file_id=file_id, user=user)
    except FileServiceError as exc:
        raise _translate(exc) from exc
    return DownloadUrlResponse(url=url)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    try:
        await service.delete_file(session, file_id=file_id, user=user)
    except FileServiceError as exc:
        raise _translate(exc) from exc
