from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.http.v1.dependencies import (
    get_get_contact_request_details_handler,
    get_get_employer_by_telegram_handler,
    get_get_favorites_handler,
    get_get_unlocked_contacts_handler,
    get_list_candidate_pending_contact_requests_handler,
    get_request_contact_access_handler,
    get_respond_contact_request_handler,
)
from app.application.employers.commands.request_contact_access import (
    RequestContactAccessHandler,
)
from app.application.employers.commands.respond_contact_request import (
    RespondContactRequestHandler,
)
from app.application.employers.queries.get_contact_request_details import (
    GetContactRequestDetailsHandler,
)
from app.application.employers.queries.get_employer import GetEmployerByTelegramHandler
from app.application.employers.queries.get_favorites import GetFavoritesHandler
from app.application.employers.queries.get_unlocked_contacts import (
    GetUnlockedContactsHandler,
)
from app.application.employers.queries.list_candidate_pending_contact_requests import (
    ListCandidatePendingContactRequestsHandler,
)
from app.infrastructure.auth.internal import (
    CandidateSubject,
    require_candidate_subject,
    require_employer_subject,
)
from app.schemas.employer import (
    CandidatePendingContactRequestResponse,
    CandidatePreviewResponse,
    ContactAccessRequest,
    ContactAccessResponse,
    ContactRequestDecisionRequest,
    ContactRequestDecisionResponse,
    ContactRequestDetailsResponse,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])


async def _ensure_subject_matches_employer(
    *,
    employer_id: UUID,
    subject_telegram_id: int,
    get_employer_by_telegram_handler: GetEmployerByTelegramHandler,
) -> None:
    subject_employer = await get_employer_by_telegram_handler(subject_telegram_id)
    if subject_employer.id != employer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )


@router.post("/requests/{employer_id}", response_model=ContactAccessResponse)
async def request_contact_access(
    employer_id: UUID,
    payload: ContactAccessRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    subject_handler: GetEmployerByTelegramHandler = Depends(get_get_employer_by_telegram_handler),
    handler: RequestContactAccessHandler = Depends(get_request_contact_access_handler),
) -> ContactAccessResponse:
    await _ensure_subject_matches_employer(
        employer_id=employer_id,
        subject_telegram_id=subject_telegram_id,
        get_employer_by_telegram_handler=subject_handler,
    )

    result = await handler(payload.to_command(employer_id=employer_id))
    return ContactAccessResponse.from_result(result)


@router.patch(
    "/requests/{request_id}/candidate-response",
    response_model=ContactRequestDecisionResponse,
)
async def respond_contact_request(
    request_id: UUID,
    payload: ContactRequestDecisionRequest,
    candidate_subject: CandidateSubject = Depends(require_candidate_subject),
    handler: RespondContactRequestHandler = Depends(get_respond_contact_request_handler),
) -> ContactRequestDecisionResponse:
    result = await handler(
        payload.to_command(
            request_id=request_id,
            candidate_id=candidate_subject.candidate_id,
        )
    )
    return ContactRequestDecisionResponse.from_domain(result)


@router.get(
    "/requests/candidate/pending",
    response_model=list[CandidatePendingContactRequestResponse],
)
async def list_candidate_pending_contact_requests(
    limit: int = 10,
    candidate_subject: CandidateSubject = Depends(require_candidate_subject),
    handler: ListCandidatePendingContactRequestsHandler = Depends(
        get_list_candidate_pending_contact_requests_handler
    ),
) -> list[CandidatePendingContactRequestResponse]:
    normalized_limit = max(1, min(limit, 20))
    result = await handler(
        candidate_id=candidate_subject.candidate_id,
        limit=normalized_limit,
    )
    return [CandidatePendingContactRequestResponse.from_result(item) for item in result]


@router.get("/requests/{request_id}", response_model=ContactRequestDetailsResponse)
async def get_contact_request_details(
    request_id: UUID,
    candidate_subject: CandidateSubject = Depends(require_candidate_subject),
    handler: GetContactRequestDetailsHandler = Depends(get_get_contact_request_details_handler),
) -> ContactRequestDetailsResponse:
    result = await handler(request_id)

    if result.candidate_id != candidate_subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    return ContactRequestDetailsResponse.from_result(result)


@router.get("/favorites/{employer_id}", response_model=list[CandidatePreviewResponse])
async def get_favorites(
    employer_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    subject_handler: GetEmployerByTelegramHandler = Depends(get_get_employer_by_telegram_handler),
    handler: GetFavoritesHandler = Depends(get_get_favorites_handler),
) -> list[CandidatePreviewResponse]:
    await _ensure_subject_matches_employer(
        employer_id=employer_id,
        subject_telegram_id=subject_telegram_id,
        get_employer_by_telegram_handler=subject_handler,
    )

    result = await handler(employer_id)
    return [CandidatePreviewResponse.from_contract(item) for item in result]


@router.get("/unlocked/{employer_id}", response_model=list[CandidatePreviewResponse])
async def get_unlocked_contacts(
    employer_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    subject_handler: GetEmployerByTelegramHandler = Depends(get_get_employer_by_telegram_handler),
    handler: GetUnlockedContactsHandler = Depends(get_get_unlocked_contacts_handler),
) -> list[CandidatePreviewResponse]:
    await _ensure_subject_matches_employer(
        employer_id=employer_id,
        subject_telegram_id=subject_telegram_id,
        get_employer_by_telegram_handler=subject_handler,
    )

    result = await handler(employer_id)
    return [CandidatePreviewResponse.from_contract(item) for item in result]
