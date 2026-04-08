from __future__ import annotations

from types import SimpleNamespace

from app.api.http.v1.dependencies import (
    build_delete_candidate_document_handler,
    build_get_candidate_document_handler,
    build_rebuild_indices_handler,
    build_search_candidates_handler,
    build_upsert_candidate_document_handler,
)
from app.application.search.commands.delete_candidate_document import (
    DeleteCandidateDocumentHandler,
)
from app.application.search.commands.rebuild_indices import RebuildIndicesHandler
from app.application.search.commands.upsert_candidate_document import (
    UpsertCandidateDocumentHandler,
)
from app.application.search.queries.get_candidate_document import (
    GetCandidateDocumentHandler,
)
from app.application.search.queries.search_candidates import SearchCandidatesHandler


class FakeRegistry:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            retrieval_size=100,
            rerank_top_k=30,
            rrf_k=60,
        )
        self.lexical_repository = object()
        self.vector_repository = object()
        self.embedding_provider = object()
        self.ranker = object()
        self.candidate_gateway = object()
        self.indexing_service = object()
        self.hybrid_search_service = object()

    def require_lexical_repository(self):
        return self.lexical_repository

    def require_vector_repository(self):
        return self.vector_repository

    def require_embedding_provider(self):
        return self.embedding_provider

    def require_ranker(self):
        return self.ranker

    def require_candidate_gateway(self):
        return self.candidate_gateway

    def require_indexing_service(self):
        return self.indexing_service

    def require_hybrid_search_service(self):
        return self.hybrid_search_service


def test_build_search_candidates_handler() -> None:
    registry = FakeRegistry()
    handler = build_search_candidates_handler(registry)
    assert isinstance(handler, SearchCandidatesHandler)


def test_build_get_candidate_document_handler() -> None:
    registry = FakeRegistry()
    handler = build_get_candidate_document_handler(registry)
    assert isinstance(handler, GetCandidateDocumentHandler)


def test_build_upsert_candidate_document_handler() -> None:
    registry = FakeRegistry()
    handler = build_upsert_candidate_document_handler(registry)
    assert isinstance(handler, UpsertCandidateDocumentHandler)


def test_build_delete_candidate_document_handler() -> None:
    registry = FakeRegistry()
    handler = build_delete_candidate_document_handler(registry)
    assert isinstance(handler, DeleteCandidateDocumentHandler)


def test_build_rebuild_indices_handler() -> None:
    registry = FakeRegistry()
    handler = build_rebuild_indices_handler(registry)
    assert isinstance(handler, RebuildIndicesHandler)
