from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.http.v1.dependencies import get_search_candidates_handler
from app.application.search.queries.search_candidates import SearchCandidatesHandler
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.search import (
    SearchCandidatesRequest,
    SearchCandidatesResponse,
)

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(require_internal_service)],
)


@router.post("/candidates", response_model=SearchCandidatesResponse)
async def search_candidates(
    payload: SearchCandidatesRequest,
    handler: SearchCandidatesHandler = Depends(get_search_candidates_handler),
) -> SearchCandidatesResponse:
    result = await handler(payload.to_query())
    return SearchCandidatesResponse.from_view(result)
