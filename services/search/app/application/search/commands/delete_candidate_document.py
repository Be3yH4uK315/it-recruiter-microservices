from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)


@dataclass(slots=True, frozen=True)
class DeleteCandidateDocumentCommand:
    candidate_id: UUID


class DeleteCandidateDocumentHandler:
    def __init__(
        self,
        lexical_repository: LexicalSearchRepository,
        vector_repository: VectorSearchRepository,
    ) -> None:
        self._lexical_repository = lexical_repository
        self._vector_repository = vector_repository

    async def __call__(self, command: DeleteCandidateDocumentCommand) -> bool:
        await self._lexical_repository.delete_document(candidate_id=command.candidate_id)
        await self._vector_repository.delete_vector(candidate_id=command.candidate_id)
        return True
