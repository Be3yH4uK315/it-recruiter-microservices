from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.search.queries.get_candidate_document import GetCandidateDocumentHandler
from app.domain.search.errors import CandidateDocumentNotFoundError


class FakeLexicalRepository:
    def __init__(self, document: dict | None) -> None:
        self.document = document
        self.calls = []

    async def get_document(self, candidate_id):
        self.calls.append(candidate_id)
        return self.document


class FakeVectorRepository:
    def __init__(self, *, vector_exists: bool = True) -> None:
        self.vector_exists = vector_exists
        self.calls = []

    async def has_vector(self, *, candidate_id):
        self.calls.append(candidate_id)
        return self.vector_exists


async def test_get_candidate_document_handler_returns_view() -> None:
    candidate_id = uuid4()
    repo = FakeLexicalRepository(
        {
            "id": str(candidate_id),
            "display_name": "Иван",
            "searchable_text": "python fastapi postgres",
        }
    )
    vector_repo = FakeVectorRepository(vector_exists=True)
    handler = GetCandidateDocumentHandler(
        lexical_repository=repo,
        vector_repository=vector_repo,
    )

    result = await handler(candidate_id)

    assert result.candidate_id == candidate_id
    assert result.searchable_text == "python fastapi postgres"
    assert result.document["display_name"] == "Иван"
    assert result.vector_present is True
    assert result.vector_store == "milvus"
    assert repo.calls == [candidate_id]
    assert vector_repo.calls == [candidate_id]


async def test_get_candidate_document_handler_raises_when_missing() -> None:
    candidate_id = uuid4()
    repo = FakeLexicalRepository(None)
    handler = GetCandidateDocumentHandler(
        lexical_repository=repo,
        vector_repository=FakeVectorRepository(vector_exists=False),
    )

    with pytest.raises(
        CandidateDocumentNotFoundError,
        match=f"candidate document {candidate_id} not found",
    ):
        await handler(candidate_id)
