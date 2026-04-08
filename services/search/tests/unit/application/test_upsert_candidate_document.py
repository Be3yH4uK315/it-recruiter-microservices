from __future__ import annotations

from uuid import uuid4

from app.application.common.contracts import CandidateDocumentPayload
from app.application.search.commands.upsert_candidate_document import (
    UpsertCandidateDocumentCommand,
    UpsertCandidateDocumentHandler,
)
from app.domain.search.entities import IndexedCandidateDocument


class FakeCandidateGateway:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get_candidate_profile(self, *, candidate_id):
        self.calls.append(candidate_id)
        return self.payload


class FakeIndexingService:
    def __init__(self, indexed_document: IndexedCandidateDocument):
        self.indexed_document = indexed_document
        self.calls = []

    async def build_indexed_document(self, *, payload):
        self.calls.append(payload)
        return self.indexed_document


class FakeLexicalRepository:
    def __init__(self) -> None:
        self.calls = []

    async def upsert_document(self, *, candidate_id, document):
        self.calls.append((candidate_id, document))

    async def delete_document(self, *, candidate_id):
        self.calls.append(("delete", candidate_id))


class FakeVectorRepository:
    def __init__(self) -> None:
        self.calls = []

    async def upsert_vector(self, *, candidate_id, embedding):
        self.calls.append((candidate_id, embedding))

    async def delete_vector(self, *, candidate_id):
        self.calls.append(("delete", candidate_id))


async def test_upsert_candidate_document_handler_indexes_candidate() -> None:
    candidate_id = uuid4()

    payload = CandidateDocumentPayload(
        id=candidate_id,
        display_name="Ivan",
        headline_role="Python Developer",
        location="Paris",
        work_modes=["remote"],
        experience_years=4.0,
        skills=[{"skill": "python"}],
        salary_min=100000,
        salary_max=150000,
        currency="RUB",
        english_level="B2",
        about_me="Async backend",
        experiences=[],
        projects=[],
        education=[],
        status="active",
    )

    indexed_document = IndexedCandidateDocument(
        candidate_id=candidate_id,
        document={"id": str(candidate_id), "display_name": "Ivan"},
        searchable_text="Python Developer Ivan python",
        embedding=[0.1, 0.2, 0.3],
    )

    gateway = FakeCandidateGateway(payload)
    indexing = FakeIndexingService(indexed_document)
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()

    handler = UpsertCandidateDocumentHandler(
        candidate_gateway=gateway,
        indexing_service=indexing,
        lexical_repository=lexical,
        vector_repository=vector,
    )

    result = await handler(UpsertCandidateDocumentCommand(candidate_id=candidate_id))

    assert gateway.calls == [candidate_id]
    assert indexing.calls == [payload]
    assert lexical.calls == [(candidate_id, {"id": str(candidate_id), "display_name": "Ivan"})]
    assert vector.calls == [(candidate_id, [0.1, 0.2, 0.3])]
    assert result.candidate_id == candidate_id
