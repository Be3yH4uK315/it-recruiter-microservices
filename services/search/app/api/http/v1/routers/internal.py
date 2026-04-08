from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.http.v1.dependencies import (
    get_delete_candidate_document_handler,
    get_get_candidate_document_handler,
    get_rebuild_indices_handler,
    get_upsert_candidate_document_handler,
)
from app.application.search.commands.delete_candidate_document import (
    DeleteCandidateDocumentCommand,
    DeleteCandidateDocumentHandler,
)
from app.application.search.commands.rebuild_indices import RebuildIndicesHandler
from app.application.search.commands.upsert_candidate_document import (
    UpsertCandidateDocumentCommand,
    UpsertCandidateDocumentHandler,
)
from app.application.search.queries.get_candidate_document import GetCandidateDocumentHandler
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.search import (
    DeleteCandidateDocumentResponse,
    IndexedCandidateDocumentResponse,
    RebuildIndicesRequest,
    RebuildIndicesResponse,
    UpsertCandidateDocumentResponse,
)

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_service)],
)


@router.post(
    "/index/rebuild",
    response_model=RebuildIndicesResponse,
    status_code=status.HTTP_200_OK,
)
async def rebuild_indices(
    payload: RebuildIndicesRequest,
    handler: RebuildIndicesHandler = Depends(get_rebuild_indices_handler),
) -> RebuildIndicesResponse:
    result = await handler(payload.to_command())
    return RebuildIndicesResponse.from_view(result)


@router.post(
    "/index/candidates/{candidate_id}",
    response_model=UpsertCandidateDocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_candidate_document(
    candidate_id: UUID,
    handler: UpsertCandidateDocumentHandler = Depends(get_upsert_candidate_document_handler),
) -> UpsertCandidateDocumentResponse:
    result = await handler(UpsertCandidateDocumentCommand(candidate_id=candidate_id))
    return UpsertCandidateDocumentResponse.from_view(result)


@router.delete(
    "/index/candidates/{candidate_id}",
    response_model=DeleteCandidateDocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_candidate_document(
    candidate_id: UUID,
    handler: DeleteCandidateDocumentHandler = Depends(get_delete_candidate_document_handler),
) -> DeleteCandidateDocumentResponse:
    deleted = await handler(DeleteCandidateDocumentCommand(candidate_id=candidate_id))
    return DeleteCandidateDocumentResponse(deleted=deleted)


@router.get(
    "/index/candidates/{candidate_id}",
    response_model=IndexedCandidateDocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_candidate_document(
    candidate_id: UUID,
    handler: GetCandidateDocumentHandler = Depends(get_get_candidate_document_handler),
) -> IndexedCandidateDocumentResponse:
    result = await handler(candidate_id)
    return IndexedCandidateDocumentResponse.from_view(result)
