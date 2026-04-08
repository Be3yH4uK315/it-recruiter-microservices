from __future__ import annotations

import httpx
from fastapi import Depends, Request

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
from app.application.search.queries.search_candidates import (
    SearchCandidatesHandler,
)
from app.infrastructure.integrations.resource_registry import ResourceRegistry


def get_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("HTTP client is not initialized")
    return client


def get_resource_registry(request: Request) -> ResourceRegistry:
    registry = getattr(request.app.state, "resource_registry", None)
    if registry is None:
        raise RuntimeError("Resource registry is not initialized")
    return registry


def build_search_candidates_handler(registry: ResourceRegistry) -> SearchCandidatesHandler:
    return SearchCandidatesHandler(
        hybrid_search_service=registry.require_hybrid_search_service(),
    )


def get_search_candidates_handler(
    registry: ResourceRegistry = Depends(get_resource_registry),
) -> SearchCandidatesHandler:
    return build_search_candidates_handler(registry)


def build_get_candidate_document_handler(
    registry: ResourceRegistry,
) -> GetCandidateDocumentHandler:
    return GetCandidateDocumentHandler(
        lexical_repository=registry.require_lexical_repository(),
        vector_repository=registry.require_vector_repository(),
    )


def get_get_candidate_document_handler(
    registry: ResourceRegistry = Depends(get_resource_registry),
) -> GetCandidateDocumentHandler:
    return build_get_candidate_document_handler(registry)


def build_upsert_candidate_document_handler(
    registry: ResourceRegistry,
) -> UpsertCandidateDocumentHandler:
    return UpsertCandidateDocumentHandler(
        candidate_gateway=registry.require_candidate_gateway(),
        indexing_service=registry.require_indexing_service(),
        lexical_repository=registry.require_lexical_repository(),
        vector_repository=registry.require_vector_repository(),
    )


def get_upsert_candidate_document_handler(
    registry: ResourceRegistry = Depends(get_resource_registry),
) -> UpsertCandidateDocumentHandler:
    return build_upsert_candidate_document_handler(registry)


def build_delete_candidate_document_handler(
    registry: ResourceRegistry,
) -> DeleteCandidateDocumentHandler:
    return DeleteCandidateDocumentHandler(
        lexical_repository=registry.require_lexical_repository(),
        vector_repository=registry.require_vector_repository(),
    )


def get_delete_candidate_document_handler(
    registry: ResourceRegistry = Depends(get_resource_registry),
) -> DeleteCandidateDocumentHandler:
    return build_delete_candidate_document_handler(registry)


def build_rebuild_indices_handler(
    registry: ResourceRegistry,
) -> RebuildIndicesHandler:
    return RebuildIndicesHandler(
        candidate_gateway=registry.require_candidate_gateway(),
        indexing_service=registry.require_indexing_service(),
        lexical_repository=registry.require_lexical_repository(),
        vector_repository=registry.require_vector_repository(),
    )


def get_rebuild_indices_handler(
    registry: ResourceRegistry = Depends(get_resource_registry),
) -> RebuildIndicesHandler:
    return build_rebuild_indices_handler(registry)
