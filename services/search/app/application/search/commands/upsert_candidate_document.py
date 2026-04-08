from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import (
    CandidateGateway,
    CandidateIndexingService,
)
from app.application.search.dto.views import IndexedCandidateDocumentView
from app.domain.search.entities import IndexedCandidateDocument
from app.domain.search.errors import CandidateDocumentNotFoundError
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)

_INACTIVE_STATUSES = {"hidden", "blocked", "deleted", "inactive"}


@dataclass(slots=True, frozen=True)
class UpsertCandidateDocumentCommand:
    candidate_id: UUID


class UpsertCandidateDocumentHandler:
    def __init__(
        self,
        candidate_gateway: CandidateGateway,
        indexing_service: CandidateIndexingService,
        lexical_repository: LexicalSearchRepository,
        vector_repository: VectorSearchRepository,
    ) -> None:
        self._candidate_gateway = candidate_gateway
        self._indexing_service = indexing_service
        self._lexical_repository = lexical_repository
        self._vector_repository = vector_repository

    async def __call__(
        self,
        command: UpsertCandidateDocumentCommand,
    ) -> IndexedCandidateDocumentView:
        payload = await self._candidate_gateway.get_candidate_profile(
            candidate_id=command.candidate_id,
        )
        if payload is None:
            raise CandidateDocumentNotFoundError(
                f"candidate {command.candidate_id} not found",
            )

        normalized_status = (payload.status or "").strip().lower()
        if normalized_status in _INACTIVE_STATUSES:
            await self._lexical_repository.delete_document(candidate_id=command.candidate_id)
            await self._vector_repository.delete_vector(candidate_id=command.candidate_id)

            return IndexedCandidateDocumentView.from_entity(
                IndexedCandidateDocument(
                    candidate_id=command.candidate_id,
                    document={},
                    searchable_text="",
                    embedding=[],
                    vector_present=False,
                    vector_store="milvus",
                )
            )

        indexed_document = await self._indexing_service.build_indexed_document(
            payload=payload,
        )

        await self._lexical_repository.upsert_document(
            candidate_id=indexed_document.candidate_id,
            document=indexed_document.document,
        )
        await self._vector_repository.upsert_vector(
            candidate_id=indexed_document.candidate_id,
            embedding=indexed_document.embedding,
        )

        return IndexedCandidateDocumentView.from_entity(indexed_document)
