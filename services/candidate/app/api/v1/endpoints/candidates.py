from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException, Request

from app.schemas import candidate as schemas
from app.services.candidate import CandidateService
from app.api.v1 import dependencies

router = APIRouter()

@router.post(
    "/",
    response_model=schemas.Candidate,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate(
    candidate_in: schemas.CandidateCreate,
    service: CandidateService = Depends(dependencies.get_candidate_service),
    current_user_tg_id: int = Depends(dependencies.get_current_user_tg_id),
):
    """
    Создание профиля кандидата.
    """
    if current_user_tg_id and candidate_in.telegram_id != current_user_tg_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot create profile for another user",
        )
    return await service.create_candidate(candidate_in)

@router.get("/", response_model=schemas.PaginatedCandidatesResponse)
async def get_candidates(
    request: Request,
    offset: int = 0,
    limit: int = Query(default=20, ge=1, le=100),
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    """
    Получение списка кандидатов (Admin/Debug).
    """
    total, data = await service.repo.get_paginated(limit, offset)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data,
    }

@router.get("/{candidate_id}", response_model=schemas.Candidate)
async def read_candidate(
    candidate_id: UUID,
    service: CandidateService = Depends(dependencies.get_candidate_service),
    viewer_id: Optional[int] = Depends(dependencies.get_current_user_tg_id),
):
    """
    Получение профиля по ID.
    Контакты скрываются автоматически в зависимости от прав работодателя (viewer_id).
    """
    return await service.get_candidate_by_id(
        candidate_id,
        viewer_tg_id=viewer_id,
    )

@router.get("/by-telegram/{telegram_id}", response_model=schemas.Candidate)
async def read_candidate_by_telegram(
    telegram_id: int,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    return await service.get_candidate_by_telegram(telegram_id=telegram_id)

@router.patch(
    "/by-telegram/{telegram_id}",
    response_model=schemas.Candidate,
    dependencies=[Depends(dependencies.verify_candidate_ownership)],
)
async def update_candidate_by_telegram_id(
    telegram_id: int,
    candidate_in: schemas.CandidateUpdate,
    service: CandidateService = Depends(dependencies.get_candidate_service),
):
    """
    Обновление профиля.
    Триггерит событие обновления, которое слушает Search Service.
    """
    candidate = await service.get_candidate_by_telegram(telegram_id)
    return await service.update_candidate(candidate.id, candidate_in)