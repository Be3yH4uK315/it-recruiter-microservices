from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.http.v1.dependencies import (
    get_candidate_by_telegram_handler,
    get_get_candidate_search_document_handler,
    get_list_candidate_search_documents_handler,
)
from app.application.candidates.queries.get_candidate_by_telegram import (
    GetCandidateByTelegramHandler,
)
from app.application.candidates.queries.get_candidate_search_document import (
    GetCandidateSearchDocumentHandler,
)
from app.application.candidates.queries.list_candidate_search_documents import (
    ListCandidateSearchDocumentsHandler,
)
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.candidate import (
    CandidateInternalResolveResponse,
    CandidateSearchDocumentListResponse,
    CandidateSearchDocumentResponse,
)

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_service)],
)


@router.get(
    "/candidates/by-telegram/{telegram_id}",
    response_model=CandidateInternalResolveResponse,
)
async def get_candidate_internal_by_telegram(
    telegram_id: int,
    handler: GetCandidateByTelegramHandler = Depends(get_candidate_by_telegram_handler),
) -> CandidateInternalResolveResponse:
    result = await handler(telegram_id)
    return CandidateInternalResolveResponse.from_domain(result)


@router.get(
    "/candidates/search-documents",
    response_model=CandidateSearchDocumentListResponse,
)
async def list_candidate_search_documents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    handler: ListCandidateSearchDocumentsHandler = Depends(
        get_list_candidate_search_documents_handler
    ),
) -> CandidateSearchDocumentListResponse:
    result = await handler(limit=limit, offset=offset)
    return CandidateSearchDocumentListResponse.from_views(result)


@router.get(
    "/candidates/{candidate_id}/search-document",
    response_model=CandidateSearchDocumentResponse,
)
async def get_candidate_search_document(
    candidate_id: UUID,
    handler: GetCandidateSearchDocumentHandler = Depends(get_get_candidate_search_document_handler),
) -> CandidateSearchDocumentResponse:
    result = await handler(candidate_id)
    return CandidateSearchDocumentResponse.from_view(result)
