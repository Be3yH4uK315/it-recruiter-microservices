from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.http.v1.dependencies import (
    get_candidate_for_employer_handler,
    get_candidate_profile_by_telegram_handler,
    get_candidate_profile_handler,
    get_candidate_statistics_handler,
    get_create_candidate_handler,
    get_many_candidates_handler,
    get_update_candidate_handler,
)
from app.application.candidates.commands.create_candidate import CreateCandidateHandler
from app.application.candidates.commands.update_candidate import UpdateCandidateHandler
from app.application.candidates.queries.get_candidate_for_employer import (
    GetCandidateForEmployerHandler,
    GetCandidateForEmployerQuery,
)
from app.application.candidates.queries.get_candidate_profile import (
    GetCandidateProfileHandler,
)
from app.application.candidates.queries.get_candidate_profile_by_telegram import (
    GetCandidateProfileByTelegramHandler,
)
from app.application.candidates.queries.get_candidate_statistics import (
    GetCandidateStatisticsHandler,
)
from app.application.candidates.queries.get_many_candidates import (
    GetManyCandidatesHandler,
)
from app.infrastructure.auth.internal import (
    CandidateRegistrationSubject,
    CandidateSubject,
    require_candidate_registration_subject,
    require_candidate_subject,
    require_internal_service,
)
from app.schemas.candidate import (
    CandidateBatchRequest,
    CandidateBatchResponse,
    CandidateEmployerViewResponse,
    CandidateProfileResponse,
    CandidateResponse,
    CandidateStatisticsResponse,
    CreateCandidateRequest,
    UpdateCandidateRequest,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate(
    payload: CreateCandidateRequest,
    subject: CandidateRegistrationSubject = Depends(require_candidate_registration_subject),
    handler: CreateCandidateHandler = Depends(get_create_candidate_handler),
) -> CandidateResponse:
    result = await handler(payload.to_command(telegram_id=subject.telegram_id))
    return CandidateResponse.from_domain(result)


@router.get("/by-telegram/{telegram_id}", response_model=CandidateProfileResponse)
async def get_candidate_by_telegram(
    telegram_id: int,
    subject: CandidateRegistrationSubject = Depends(require_candidate_registration_subject),
    handler: GetCandidateProfileByTelegramHandler = Depends(
        get_candidate_profile_by_telegram_handler
    ),
) -> CandidateProfileResponse:
    if telegram_id != subject.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(telegram_id)
    return CandidateProfileResponse.from_view(result)


@router.get("/{candidate_id}", response_model=CandidateProfileResponse)
async def get_candidate(
    candidate_id: UUID,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: GetCandidateProfileHandler = Depends(get_candidate_profile_handler),
) -> CandidateProfileResponse:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(candidate_id)
    return CandidateProfileResponse.from_view(result)


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    payload: UpdateCandidateRequest,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: UpdateCandidateHandler = Depends(get_update_candidate_handler),
) -> CandidateResponse:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(payload.to_command(candidate_id=candidate_id))
    return CandidateResponse.from_domain(result)


@router.post(
    "/batch",
    response_model=CandidateBatchResponse,
    dependencies=[Depends(require_internal_service)],
)
async def get_many_candidates(
    payload: CandidateBatchRequest,
    handler: GetManyCandidatesHandler = Depends(get_many_candidates_handler),
) -> CandidateBatchResponse:
    result = await handler(payload.candidate_ids)
    return CandidateBatchResponse.from_domain_many(result)


@router.get(
    "/{candidate_id}/statistics",
    response_model=CandidateStatisticsResponse,
)
async def get_candidate_statistics(
    candidate_id: UUID,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: GetCandidateStatisticsHandler = Depends(get_candidate_statistics_handler),
) -> CandidateStatisticsResponse:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(candidate_id)
    return CandidateStatisticsResponse.from_result(result)


@router.get(
    "/{candidate_id}/employer-view",
    response_model=CandidateEmployerViewResponse,
    dependencies=[Depends(require_internal_service)],
)
async def get_candidate_for_employer(
    candidate_id: UUID,
    employer_telegram_id: int = Query(..., ge=1),
    handler: GetCandidateForEmployerHandler = Depends(get_candidate_for_employer_handler),
) -> CandidateEmployerViewResponse:
    result = await handler(
        GetCandidateForEmployerQuery(
            candidate_id=candidate_id,
            employer_telegram_id=employer_telegram_id,
        )
    )
    return CandidateEmployerViewResponse.from_view(result)
