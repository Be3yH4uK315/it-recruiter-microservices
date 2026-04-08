from __future__ import annotations

from uuid import UUID

from app.application.search.dto.views import IndexedCandidateDocumentView
from app.domain.search.entities import IndexedCandidateDocument
from app.domain.search.errors import CandidateDocumentNotFoundError
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)


class GetCandidateDocumentHandler:
    def __init__(
        self,
        lexical_repository: LexicalSearchRepository,
        vector_repository: VectorSearchRepository,
    ) -> None:
        self._lexical_repository = lexical_repository
        self._vector_repository = vector_repository

    async def __call__(self, candidate_id: UUID) -> IndexedCandidateDocumentView:
        raw_document = await self._lexical_repository.get_document(candidate_id)
        if raw_document is None:
            raise CandidateDocumentNotFoundError(
                f"candidate document {candidate_id} not found",
            )

        vector_present = await self._vector_repository.has_vector(candidate_id=candidate_id)

        entity = IndexedCandidateDocument(
            candidate_id=candidate_id,
            document=raw_document,
            searchable_text=str(raw_document.get("searchable_text") or ""),
            vector_present=vector_present,
            vector_store="milvus",
        )
        return IndexedCandidateDocumentView.from_entity(entity)
