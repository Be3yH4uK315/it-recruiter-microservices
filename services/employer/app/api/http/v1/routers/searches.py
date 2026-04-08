from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.http.v1.dependencies import (
    get_close_search_session_handler,
    get_get_next_candidate_handler,
    get_pause_search_session_handler,
    get_resume_search_session_handler,
    get_submit_decision_handler,
    get_uow_factory,
)
from app.application.common.uow import UnitOfWork
from app.application.employers.commands.close_search_session import (
    CloseSearchSessionCommand,
    CloseSearchSessionHandler,
)
from app.application.employers.commands.get_next_candidate import GetNextCandidateHandler
from app.application.employers.commands.pause_search_session import (
    PauseSearchSessionCommand,
    PauseSearchSessionHandler,
)
from app.application.employers.commands.resume_search_session import (
    ResumeSearchSessionCommand,
    ResumeSearchSessionHandler,
)
from app.application.employers.commands.submit_decision import SubmitDecisionHandler
from app.infrastructure.auth.internal import require_employer_subject
from app.schemas.employer import (
    DecisionCreateRequest,
    DecisionResponse,
    NextCandidateResponse,
    SearchSessionResponse,
)

router = APIRouter(prefix="/searches", tags=["searches"])


async def _ensure_session_owner(
    *,
    session_id: UUID,
    subject_telegram_id: int,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        subject_employer = await uow.employers.get_by_telegram_id(subject_telegram_id)
        if subject_employer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="employer not found",
            )

        session = await uow.searches.get_by_id(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="search session not found",
            )

        if session.employer_id != subject_employer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="search session access denied",
            )


@router.get("/{session_id}/next", response_model=NextCandidateResponse)
async def get_next_candidate(
    session_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: GetNextCandidateHandler = Depends(get_get_next_candidate_handler),
) -> NextCandidateResponse:
    await _ensure_session_owner(
        session_id=session_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(session_id)
    return NextCandidateResponse.from_result(result)


@router.post(
    "/{session_id}/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_decision(
    session_id: UUID,
    payload: DecisionCreateRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: SubmitDecisionHandler = Depends(get_submit_decision_handler),
) -> DecisionResponse:
    await _ensure_session_owner(
        session_id=session_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(payload.to_command(session_id=session_id))
    return DecisionResponse.from_domain(result)


@router.post("/{session_id}/pause", response_model=SearchSessionResponse)
async def pause_search_session(
    session_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: PauseSearchSessionHandler = Depends(get_pause_search_session_handler),
) -> SearchSessionResponse:
    await _ensure_session_owner(
        session_id=session_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(PauseSearchSessionCommand(session_id=session_id))
    return SearchSessionResponse.from_domain(result)


@router.post("/{session_id}/resume", response_model=SearchSessionResponse)
async def resume_search_session(
    session_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: ResumeSearchSessionHandler = Depends(get_resume_search_session_handler),
) -> SearchSessionResponse:
    await _ensure_session_owner(
        session_id=session_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(ResumeSearchSessionCommand(session_id=session_id))
    return SearchSessionResponse.from_domain(result)


@router.post("/{session_id}/close", response_model=SearchSessionResponse)
async def close_search_session(
    session_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    handler: CloseSearchSessionHandler = Depends(get_close_search_session_handler),
) -> SearchSessionResponse:
    await _ensure_session_owner(
        session_id=session_id,
        subject_telegram_id=subject_telegram_id,
        uow_factory=uow_factory,
    )

    result = await handler(CloseSearchSessionCommand(session_id=session_id))
    return SearchSessionResponse.from_domain(result)
