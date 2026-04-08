from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.http.v1.dependencies import (
    get_get_candidate_statistics_handler,
    get_get_contact_request_status_handler,
    get_has_contact_access_handler,
)
from app.application.employers.queries.get_candidate_statistics import (
    GetCandidateStatisticsHandler,
)
from app.application.employers.queries.get_contact_request_status import (
    GetContactRequestStatusHandler,
)
from app.application.employers.queries.has_contact_access import (
    HasContactAccessHandler,
)
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.employer import ContactRequestStatusResponse

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_service)],
)


@router.get("/contact-access", response_model=dict[str, bool])
async def has_contact_access(
    candidate_id: UUID = Query(...),
    employer_telegram_id: int = Query(..., gt=0),
    handler: HasContactAccessHandler = Depends(get_has_contact_access_handler),
) -> dict[str, bool]:
    result = await handler(
        candidate_id=candidate_id,
        employer_telegram_id=employer_telegram_id,
    )
    return {"has_access": result}


@router.get("/candidates/{candidate_id}/statistics", response_model=dict[str, int])
async def get_candidate_statistics(
    candidate_id: UUID,
    handler: GetCandidateStatisticsHandler = Depends(get_get_candidate_statistics_handler),
) -> dict[str, int]:
    result = await handler(candidate_id)
    return {
        "total_views": int(result.get("total_views", 0)),
        "total_likes": int(result.get("total_likes", 0)),
        "total_contact_requests": int(result.get("total_contact_requests", 0)),
    }


@router.get("/contact-requests/status", response_model=ContactRequestStatusResponse)
async def get_contact_request_status(
    employer_id: UUID = Query(...),
    candidate_id: UUID = Query(...),
    handler: GetContactRequestStatusHandler = Depends(get_get_contact_request_status_handler),
) -> ContactRequestStatusResponse:
    result = await handler(
        employer_id=employer_id,
        candidate_id=candidate_id,
    )
    return ContactRequestStatusResponse.from_result(result)
