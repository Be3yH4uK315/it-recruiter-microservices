from app.api.v1 import dependencies
from app.schemas import candidate as schemas
from app.services.candidate import CandidateService
from fastapi import APIRouter, Depends, status

router = APIRouter()


@router.post(
    "/by-telegram/{telegram_id}/resume/upload-url",
    response_model=schemas.ResumeUploadResponse,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def get_resume_upload_url(
    telegram_id: int,
    filename: str,
    content_type: str = "application/pdf",
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    """
    Получение Presigned URL для загрузки файла.
    """
    return await service.get_resume_upload_url(
        telegram_id,
        filename,
        content_type,
    )


@router.put(
    "/by-telegram/{telegram_id}/resume",
    response_model=schemas.Resume,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def replace_candidate_resume(
    telegram_id: int,
    resume_in: schemas.ResumeCreate,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    """
    Привязка загруженного файла к профилю.
    """
    return await service.update_resume(telegram_id, resume_in)


@router.delete(
    "/by-telegram/{telegram_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def delete_candidate_resume(
    telegram_id: int,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    await service.delete_resume(telegram_id)
