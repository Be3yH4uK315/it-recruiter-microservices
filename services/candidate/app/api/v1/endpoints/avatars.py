from app.api.v1 import dependencies
from app.schemas import candidate as schemas
from app.services.candidate import CandidateService
from fastapi import APIRouter, Depends, status

router = APIRouter()


@router.put(
    "/by-telegram/{telegram_id}/avatar",
    response_model=schemas.Avatar,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def replace_candidate_avatar(
    telegram_id: int,
    avatar_in: schemas.AvatarCreate,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    """
    Устанавливает новый аватар (file_id).
    Старый удаляет через Outbox.
    """
    return await service.update_avatar(telegram_id, avatar_in)


@router.delete(
    "/by-telegram/{telegram_id}/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def delete_candidate_avatar(
    telegram_id: int,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    await service.delete_avatar(telegram_id)
