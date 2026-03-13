from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.v1.dependencies import get_current_user_tg_id, get_service
from app.schemas.file import (
    DownloadUrlResponse,
    FileResponse,
    FileTypeEnum,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.file import FileService

router = APIRouter()


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    file_type: FileTypeEnum = Form(...),
    owner_id: int = Depends(get_current_user_tg_id),
    service: FileService = Depends(get_service),
):
    """Загрузка файла через бэкенд с проверкой Magic Bytes."""
    return await service.upload_file(file, owner_id, file_type)


@router.post("/{file_type}/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    file_type: FileTypeEnum,
    request: UploadUrlRequest,
    owner_tg_id: int = Depends(get_current_user_tg_id),
    service: FileService = Depends(get_service),
):
    """Получение Presigned URL для прямой загрузки клиентом."""
    return await service.generate_upload_url(
        owner_id=str(owner_tg_id),
        filename=request.filename,
        content_type=request.content_type,
        file_type=file_type,
    )


@router.get("/{file_id}/url", response_model=DownloadUrlResponse)
async def get_presigned_url(file_id: UUID, service: FileService = Depends(get_service)):
    url = await service.get_download_url(file_id)
    if not url:
        raise HTTPException(status_code=404, detail="File not found")
    return {"download_url": url}


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    owner_id: int = Depends(get_current_user_tg_id),
    service: FileService = Depends(get_service),
):
    await service.delete_file(file_id, owner_id)
    return {"status": "deleted"}
