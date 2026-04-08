from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.http.v1.dependencies import (
    get_cleanup_file_handler,
    get_create_download_url_handler,
    get_create_upload_url_handler,
    get_internal_file_handler,
    get_register_uploaded_file_handler,
)
from app.application.files.commands.cleanup_file import CleanupFileCommand, CleanupFileHandler
from app.application.files.commands.create_download_url import (
    CreateDownloadUrlCommand,
    CreateDownloadUrlHandler,
)
from app.application.files.commands.create_upload_url import (
    CreateUploadUrlCommand,
    CreateUploadUrlHandler,
)
from app.application.files.commands.register_uploaded_file import (
    RegisterUploadedFileCommand,
    RegisterUploadedFileHandler,
)
from app.application.files.queries.get_file import (
    GetInternalFileHandler,
    GetInternalFileQuery,
)
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.file import (
    CleanupFileRequest,
    CreateDownloadUrlResponse,
    CreateUploadUrlRequest,
    CreateUploadUrlResponse,
    FileResponse,
    RegisterUploadedFileRequest,
)

router = APIRouter(
    prefix="/internal/files",
    tags=["internal-files"],
    dependencies=[Depends(require_internal_service)],
)


@router.post(
    "/upload-url",
    response_model=CreateUploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_url(
    payload: CreateUploadUrlRequest,
    handler: CreateUploadUrlHandler = Depends(get_create_upload_url_handler),
) -> CreateUploadUrlResponse:
    result = await handler(
        CreateUploadUrlCommand(
            owner_service=payload.owner_service,
            owner_id=payload.owner_id,
            filename=payload.filename,
            content_type=payload.content_type,
            category=payload.category,
        )
    )
    return CreateUploadUrlResponse.from_result(result)


@router.get("/{file_id}", response_model=FileResponse)
async def get_file_by_id(
    file_id: UUID,
    owner_service: str = Query(..., min_length=1),
    handler: GetInternalFileHandler = Depends(get_internal_file_handler),
) -> FileResponse:
    result = await handler(
        GetInternalFileQuery(
            file_id=file_id,
            owner_service=owner_service,
        )
    )
    return FileResponse.from_view(result)


@router.get("/{file_id}/download-url", response_model=CreateDownloadUrlResponse)
async def create_download_url(
    file_id: UUID,
    owner_service: str = Query(..., min_length=1),
    owner_id: UUID | None = Query(default=None),
    handler: CreateDownloadUrlHandler = Depends(get_create_download_url_handler),
) -> CreateDownloadUrlResponse:
    result = await handler(
        CreateDownloadUrlCommand(
            file_id=file_id,
            owner_service=owner_service,
            owner_id=owner_id,
        )
    )
    return CreateDownloadUrlResponse.from_result(result)


@router.post("/{file_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def register_uploaded_file(
    file_id: UUID,
    payload: RegisterUploadedFileRequest,
    handler: RegisterUploadedFileHandler = Depends(get_register_uploaded_file_handler),
) -> Response:
    await handler(
        RegisterUploadedFileCommand(
            file_id=file_id,
            size_bytes=payload.size_bytes,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{file_id}/cleanup", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_file(
    file_id: UUID,
    payload: CleanupFileRequest,
    handler: CleanupFileHandler = Depends(get_cleanup_file_handler),
) -> Response:
    await handler(
        CleanupFileCommand(
            file_id=file_id,
            reason=payload.reason,
            requested_by_service=payload.requested_by_service,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
