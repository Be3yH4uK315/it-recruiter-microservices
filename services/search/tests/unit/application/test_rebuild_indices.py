from __future__ import annotations

from uuid import uuid4

from app.application.common.contracts import CandidateDocumentPayload
from app.application.search.commands.rebuild_indices import RebuildIndicesHandler
from app.domain.search.entities import IndexedCandidateDocument


class FakeCandidateGateway:
    def __init__(self):
        self.calls = []
        self.batch = [
            CandidateDocumentPayload(
                id=uuid4(),
                display_name="Ivan",
                headline_role="Python",
                location="Paris",
                work_modes=["remote"],
                experience_years=4.0,
                skills=[{"skill": "python"}],
                salary_min=100000,
                salary_max=150000,
                currency="RUB",
                english_level="B2",
                about_me=None,
                experiences=[],
                projects=[],
                education=[],
                status="active",
            ),
            CandidateDocumentPayload(
                id=uuid4(),
                display_name="Petr",
                headline_role="Go",
                location="Paris",
                work_modes=["remote"],
                experience_years=4.0,
                skills=[{"skill": "go"}],
                salary_min=100000,
                salary_max=150000,
                currency="RUB",
                english_level="B2",
                about_me=None,
                experiences=[],
                projects=[],
                education=[],
                status="active",
            ),
        ]

    async def list_candidates(self, *, limit, offset):
        self.calls.append((limit, offset))
        if offset > 0:
            return []
        return self.batch


class FakeIndexingService:
    def __init__(self):
        self.calls = []

    async def build_indexed_document(self, *, payload):
        self.calls.append(payload)
        candidate_id = uuid4()
        return IndexedCandidateDocument(
            candidate_id=candidate_id,
            document={"id": str(candidate_id), "headline_role": payload.headline_role},
            searchable_text=payload.headline_role,
            embedding=[0.1, 0.2],
        )


class FakeLexicalRepository:
    def __init__(self):
        self.calls = []
        self.indexed_ids = []

    async def upsert_document(self, *, candidate_id, document):
        self.calls.append((candidate_id, document))

    async def delete_document(self, *, candidate_id):
        self.calls.append(("delete", candidate_id))

    async def clear_all(self):
        self.calls.append(("clear_all", None))

    async def list_candidate_ids(self):
        return list(self.indexed_ids)


class FakeVectorRepository:
    def __init__(self):
        self.calls = []
        self.indexed_ids = []

    async def upsert_vector(self, *, candidate_id, embedding):
        self.calls.append((candidate_id, embedding))

    async def delete_vector(self, *, candidate_id):
        self.calls.append(("delete", candidate_id))

    async def clear_all(self):
        self.calls.append(("clear_all", None))

    async def list_candidate_ids(self):
        return list(self.indexed_ids)


async def test_rebuild_indices_handler_reindexes_candidates() -> None:
    gateway = FakeCandidateGateway()
    indexing = FakeIndexingService()
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()

    handler = RebuildIndicesHandler(
        candidate_gateway=gateway,
        indexing_service=indexing,
        lexical_repository=lexical,
        vector_repository=vector,
    )

    result = await handler(command=type("Cmd", (), {"batch_size": 2})())

    assert result.processed == 2
    assert result.indexed == 2
    assert result.failed == 0
    assert gateway.calls
    assert indexing.calls
    assert lexical.calls
    assert vector.calls
    assert ("clear_all", None) not in lexical.calls
    assert ("clear_all", None) not in vector.calls


async def test_rebuild_indices_handler_deletes_orphaned_documents_after_full_scan() -> None:
    gateway = FakeCandidateGateway()
    indexing = FakeIndexingService()
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()

    orphan_id = uuid4()
    lexical.indexed_ids = [str(orphan_id)]
    vector.indexed_ids = [str(orphan_id)]

    handler = RebuildIndicesHandler(
        candidate_gateway=gateway,
        indexing_service=indexing,
        lexical_repository=lexical,
        vector_repository=vector,
    )

    await handler(command=type("Cmd", (), {"batch_size": 2})())

    assert ("delete", orphan_id) in lexical.calls
    assert ("delete", orphan_id) in vector.calls
