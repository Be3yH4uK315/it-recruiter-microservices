from __future__ import annotations

from typing import Any

import httpx

from app.application.common.contracts import (
    CandidateGateway,
    CandidateIndexingService,
    EmbeddingProvider,
    HybridSearchService,
    Ranker,
)
from app.application.search.services.hybrid_search import DefaultHybridSearchService
from app.application.search.services.indexing import DefaultCandidateIndexingService
from app.config import Settings
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)
from app.infrastructure.integrations.candidate_gateway import HttpCandidateGateway
from app.infrastructure.integrations.elasticsearch_client import build_elasticsearch_client
from app.infrastructure.integrations.elasticsearch_repository import (
    ElasticsearchCandidateRepository,
)
from app.infrastructure.integrations.embedding_provider import (
    SentenceTransformerEmbeddingProvider,
)
from app.infrastructure.integrations.milvus_client import MilvusClientWrapper
from app.infrastructure.integrations.milvus_repository import MilvusCandidateRepository
from app.infrastructure.integrations.ranker import CrossEncoderRanker


class ResourceRegistry:
    def __init__(
        self,
        *,
        settings: Settings,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.settings = settings
        self.http_client = http_client

        self._es_client = None
        self._milvus_client: MilvusClientWrapper | None = None

        self.candidate_gateway: CandidateGateway | None = None
        self.lexical_repository: LexicalSearchRepository | None = None
        self.vector_repository: VectorSearchRepository | None = None
        self.embedding_provider: EmbeddingProvider | None = None
        self.ranker: Ranker | None = None
        self.indexing_service: CandidateIndexingService | None = None
        self.hybrid_search_service: HybridSearchService | None = None

    async def startup(self) -> None:
        try:
            self.candidate_gateway = HttpCandidateGateway(
                client=self.http_client,
                base_url=self.settings.candidate_service_url,
                internal_token=self.settings.internal_service_token,
            )

            self._es_client = build_elasticsearch_client(self.settings)
            lexical_repository = ElasticsearchCandidateRepository(
                client=self._es_client,
                index_alias=self.settings.candidate_index_alias,
            )
            await lexical_repository.startup()
            self.lexical_repository = lexical_repository

            self._milvus_client = MilvusClientWrapper(
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
                collection_name=self.settings.milvus_collection_name,
                dimension=self.settings.milvus_embedding_dim,
            )
            await self._milvus_client.startup()
            self.vector_repository = MilvusCandidateRepository(client=self._milvus_client)

            embedding_provider = SentenceTransformerEmbeddingProvider(
                model_name=self.settings.sentence_model_name,
                concurrency_limit=self.settings.ml_concurrency_limit,
            )
            await embedding_provider.startup()
            self.embedding_provider = embedding_provider

            ranker = CrossEncoderRanker(
                model_name=self.settings.ranker_model_name,
                settings=self.settings,
                concurrency_limit=self.settings.ml_concurrency_limit,
            )
            await ranker.startup()
            self.ranker = ranker

            self.indexing_service = DefaultCandidateIndexingService(
                embedding_provider=self.require_embedding_provider(),
                embedding_cache_size=self.settings.index_embedding_cache_size,
            )

            self.hybrid_search_service = DefaultHybridSearchService(
                lexical_repository=self.require_lexical_repository(),
                vector_repository=self.require_vector_repository(),
                embedding_provider=self.require_embedding_provider(),
                ranker=self.require_ranker(),
                retrieval_size=self.settings.retrieval_size,
                rerank_top_k=self.settings.rerank_top_k,
                rrf_k=self.settings.rrf_k,
                result_cache_ttl_seconds=self.settings.search_result_cache_ttl_seconds,
                result_cache_size=self.settings.search_result_cache_size,
                timing_logging_enabled=self.settings.search_timing_logging_enabled,
                timing_logging_threshold_ms=self.settings.search_timing_logging_threshold_ms,
            )
        except Exception:
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        if self.ranker is not None and hasattr(self.ranker, "shutdown"):
            try:
                await self.ranker.shutdown()
            finally:
                self.ranker = None

        if self.embedding_provider is not None and hasattr(self.embedding_provider, "shutdown"):
            try:
                await self.embedding_provider.shutdown()
            finally:
                self.embedding_provider = None

        if self.lexical_repository is not None and hasattr(self.lexical_repository, "shutdown"):
            try:
                await self.lexical_repository.shutdown()
            finally:
                self.lexical_repository = None
                self._es_client = None

        if self._milvus_client is not None:
            try:
                await self._milvus_client.shutdown()
            finally:
                self._milvus_client = None
                self.vector_repository = None

        self.candidate_gateway = None
        self.indexing_service = None
        self.hybrid_search_service = None

    def require_candidate_gateway(self) -> CandidateGateway:
        if self.candidate_gateway is None:
            raise RuntimeError("Candidate gateway is not initialized")
        return self.candidate_gateway

    def require_lexical_repository(self) -> LexicalSearchRepository:
        if self.lexical_repository is None:
            raise RuntimeError("Lexical repository is not initialized")
        return self.lexical_repository

    def require_vector_repository(self) -> VectorSearchRepository:
        if self.vector_repository is None:
            raise RuntimeError("Vector repository is not initialized")
        return self.vector_repository

    def require_embedding_provider(self) -> EmbeddingProvider:
        if self.embedding_provider is None:
            raise RuntimeError("Embedding provider is not initialized")
        return self.embedding_provider

    def require_ranker(self) -> Ranker:
        if self.ranker is None:
            raise RuntimeError("Ranker is not initialized")
        return self.ranker

    def require_indexing_service(self) -> CandidateIndexingService:
        if self.indexing_service is None:
            raise RuntimeError("Candidate indexing service is not initialized")
        return self.indexing_service

    def require_hybrid_search_service(self) -> HybridSearchService:
        if self.hybrid_search_service is None:
            raise RuntimeError("Hybrid search service is not initialized")
        return self.hybrid_search_service

    async def get_health_snapshot(self) -> dict[str, Any]:
        components: dict[str, dict[str, str]] = {
            "candidate_gateway": {
                "status": "configured" if self.candidate_gateway is not None else "not_initialized"
            },
            "elasticsearch": await self._check_elasticsearch(),
            "milvus": await self._check_milvus(),
            "embedding_provider": {
                "status": "ok" if self.embedding_provider is not None else "not_initialized"
            },
            "ranker": {"status": "ok" if self.ranker is not None else "not_initialized"},
            "indexing_service": {
                "status": "ok" if self.indexing_service is not None else "not_initialized"
            },
            "hybrid_search_service": {
                "status": "ok" if self.hybrid_search_service is not None else "not_initialized"
            },
        }
        required_components = (
            "elasticsearch",
            "milvus",
            "embedding_provider",
            "ranker",
            "indexing_service",
            "hybrid_search_service",
        )
        ready = all(components[name]["status"] == "ok" for name in required_components)
        return {
            "ready": ready,
            "components": components,
        }

    async def _check_elasticsearch(self) -> dict[str, str]:
        if self._es_client is None:
            return {"status": "not_initialized"}

        try:
            is_ready = await self._es_client.ping()
        except Exception:
            return {"status": "unavailable"}

        return {"status": "ok" if is_ready else "unavailable"}

    async def _check_milvus(self) -> dict[str, str]:
        if self._milvus_client is None:
            return {"status": "not_initialized"}

        try:
            await self._milvus_client.healthcheck()
        except Exception:
            return {"status": "unavailable"}

        return {"status": "ok"}
