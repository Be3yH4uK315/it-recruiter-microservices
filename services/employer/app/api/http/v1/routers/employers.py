from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.http.v1.dependencies import (
    get_create_employer_handler,
    get_create_search_session_handler,
    get_get_candidate_statistics_handler,
    get_get_employer_by_telegram_handler,
    get_get_employer_contact_request_details_handler,
    get_get_employer_handler,
    get_get_employer_statistics_handler,
    get_list_employer_searches_handler,
    get_uow_factory,
    get_update_employer_handler,
)
from app.application.common.uow import UnitOfWork
from app.application.employers.commands.create_employer import CreateEmployerHandler
from app.application.employers.commands.create_search_session import CreateSearchSessionHandler
from app.application.employers.commands.update_employer import UpdateEmployerHandler
from app.application.employers.queries.get_candidate_statistics import (
    GetCandidateStatisticsHandler,
)
from app.application.employers.queries.get_employer import (
    GetEmployerByTelegramHandler,
    GetEmployerHandler,
)
from app.application.employers.queries.get_employer_contact_request_details import (
    GetEmployerContactRequestDetailsHandler,
)
from app.application.employers.queries.get_employer_statistics import (
    GetEmployerStatisticsHandler,
)
from app.application.employers.queries.list_employer_searches import (
    ListEmployerSearchesHandler,
)
from app.infrastructure.auth.internal import require_employer_subject
from app.schemas.employer import (
    CandidateStatisticsResponse,
    EmployerContactRequestDetailsResponse,
    EmployerCreateRequest,
    EmployerResponse,
    EmployerStatisticsResponse,
    EmployerUpdateRequest,
    SearchSessionCreateRequest,
    SearchSessionResponse,
)

router = APIRouter(prefix="/employers", tags=["employers"])


async def _ensure_employer_owner(
    *,
    employer_id: UUID,
    subject_telegram_id: int,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        employer = await uow.employers.get_by_id(employer_id)
        if employer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="employer not found",
            )

        if employer.telegram_id != subject_telegram_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="employer access denied",
            )


@router.post("", response_model=EmployerResponse, status_code=status.HTTP_201_CREATED)
async def create_employer(
    payload: EmployerCreateRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    handler: CreateEmployerHandler = Depends(get_create_employer_handler),
) -> EmployerResponse:
    if payload.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="telegram id mismatch",
        )

    result = await handler(payload.to_command())
    return EmployerResponse.from_entity(result)


@router.get("/by-telegram/{telegram_id}", response_model=EmployerResponse)
async def get_employer_by_telegram(
    telegram_id: int,
    subject_telegram_id: int = Depends(require_employer_subject),
    handler: GetEmployerByTelegramHandler = Depends(get_get_employer_by_telegram_handler),
) -> EmployerResponse:
    if telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    result = await handler(telegram_id)
    return EmployerResponse.from_view(result)


@router.get("/{employer_id}", response_model=EmployerResponse)
async def get_employer(
    employer_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    handler: GetEmployerHandler = Depends(get_get_employer_handler),
) -> EmployerResponse:
    result = await handler(employer_id)

    if result.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    return EmployerResponse.from_view(result)


@router.patch("/{employer_id}", response_model=EmployerResponse)
async def update_employer(
    employer_id: UUID,
    payload: EmployerUpdateRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    employer_handler: GetEmployerHandler = Depends(get_get_employer_handler),
    handler: UpdateEmployerHandler = Depends(get_update_employer_handler),
) -> EmployerResponse:
    employer = await employer_handler(employer_id)
    if employer.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    updated = await handler(payload.to_command(employer_id=employer_id))
    return EmployerResponse.from_entity(updated)


@router.post(
    "/{employer_id}/searches",
    response_model=SearchSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_search_session(
    employer_id: UUID,
    payload: SearchSessionCreateRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: CreateSearchSessionHandler = Depends(get_create_search_session_handler),
) -> SearchSessionResponse:
    await _ensure_employer_owner(
        employer_id=employer_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(payload.to_command(employer_id=employer_id))
    return SearchSessionResponse.from_domain(result)


@router.get("/{employer_id}/searches", response_model=list[SearchSessionResponse])
async def list_employer_searches(
    employer_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: ListEmployerSearchesHandler = Depends(get_list_employer_searches_handler),
) -> list[SearchSessionResponse]:
    await _ensure_employer_owner(
        employer_id=employer_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(employer_id, limit=limit)
    return [SearchSessionResponse.from_domain(item) for item in result]


@router.get("/{employer_id}/statistics", response_model=EmployerStatisticsResponse)
async def get_employer_statistics(
    employer_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    employer_handler: GetEmployerHandler = Depends(get_get_employer_handler),
    handler: GetEmployerStatisticsHandler = Depends(get_get_employer_statistics_handler),
) -> EmployerStatisticsResponse:
    employer = await employer_handler(employer_id)
    if employer.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    result = await handler(employer_id)
    return EmployerStatisticsResponse(**result)


@router.get(
    "/{employer_id}/contact-requests/{request_id}",
    response_model=EmployerContactRequestDetailsResponse,
)
async def get_employer_contact_request_details(
    employer_id: UUID,
    request_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    handler: GetEmployerContactRequestDetailsHandler = Depends(
        get_get_employer_contact_request_details_handler
    ),
) -> EmployerContactRequestDetailsResponse:
    result = await handler(
        employer_id=employer_id,
        employer_telegram_id=subject_telegram_id,
        request_id=request_id,
    )
    return EmployerContactRequestDetailsResponse.from_result(result)


@router.get(
    "/candidates/{candidate_id}/statistics",
    response_model=CandidateStatisticsResponse,
)
async def get_candidate_statistics(
    candidate_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    handler: GetCandidateStatisticsHandler = Depends(get_get_candidate_statistics_handler),
) -> CandidateStatisticsResponse:
    _ = subject_telegram_id
    result = await handler(candidate_id)
    return CandidateStatisticsResponse(**result)
