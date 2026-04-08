from __future__ import annotations

from uuid import uuid4

from app.application.search.commands.delete_candidate_document import (
    DeleteCandidateDocumentCommand,
    DeleteCandidateDocumentHandler,
)


class FakeLexicalRepository:
    def __init__(self) -> None:
        self.calls = []

    async def delete_document(self, *, candidate_id):
        self.calls.append(candidate_id)


class FakeVectorRepository:
    def __init__(self) -> None:
        self.calls = []

    async def delete_vector(self, *, candidate_id):
        self.calls.append(candidate_id)


async def test_delete_candidate_document_handler_removes_document() -> None:
    candidate_id = uuid4()

    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()

    handler = DeleteCandidateDocumentHandler(
        lexical_repository=lexical,
        vector_repository=vector,
    )

    result = await handler(DeleteCandidateDocumentCommand(candidate_id=candidate_id))

    assert result is True
    assert lexical.calls == [candidate_id]
    assert vector.calls == [candidate_id]
