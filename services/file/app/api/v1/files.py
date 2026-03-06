from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.v1.dependencies import get_current_user_tg_id, get_service
from app.schemas.file import DownloadUrlResponse, FileResponse
from app.services.file import FileService

router = APIRouter()


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    owner_id: int = Depends(get_current_user_tg_id),
    service: FileService = Depends(get_service),
):
    """
    Загрузка файла. Требует Header 'Authorization: Bearer <token>'
    """
    return await service.upload_file(file, owner_id, file_type)


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
