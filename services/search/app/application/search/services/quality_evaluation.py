from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.application.common.contracts import (
    EmbeddingProvider,
    HybridSearchService,
)
from app.application.search.services.hybrid_search import DefaultHybridSearchService
from app.domain.search.errors import (
    EmbeddingGenerationError,
    RankingUnavailableError,
    SearchBackendUnavailableError,
)
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)

try:
    from elastic_transport import ConnectionTimeout as ElasticConnectionTimeout
except ModuleNotFoundError:  # pragma: no cover - env-dependent import
    ElasticConnectionTimeout = ()  # type: ignore[assignment]


class SearchEvaluationMode(str, Enum):
    LEXICAL = "lexical"
    VECTOR = "vector"
    HYBRID = "hybrid"


@dataclass(slots=True, frozen=True)
class SearchQualityCase:
    case_id: str
    filters: dict[str, Any]
    relevance: dict[str, float]

    def __post_init__(self) -> None:
        normalized_case_id = self.case_id.strip()
        if not normalized_case_id:
            raise ValueError("case_id must not be empty")
        object.__setattr__(self, "case_id", normalized_case_id)

        normalized_relevance: dict[str, float] = {}
        for candidate_id, grade in self.relevance.items():
            normalized_id = str(candidate_id).strip()
            if not normalized_id:
                continue

            numeric_grade = float(grade)
            if numeric_grade <= 0:
                continue

            normalized_relevance[normalized_id] = numeric_grade

        object.__setattr__(self, "relevance", normalized_relevance)


@dataclass(slots=True, frozen=True)
class QueryEvaluationResult:
    case_id: str
    mode: SearchEvaluationMode
    latency_ms: float
    ranked_candidate_ids: list[str]
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float]
    mrr: float
    ndcg_at_k: dict[int, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "mode": self.mode.value,
            "latency_ms": self.latency_ms,
            "ranked_candidate_ids": list(self.ranked_candidate_ids),
            "precision_at_k": {str(key): value for key, value in self.precision_at_k.items()},
            "recall_at_k": {str(key): value for key, value in self.recall_at_k.items()},
            "mrr": self.mrr,
            "ndcg_at_k": {str(key): value for key, value in self.ndcg_at_k.items()},
        }


@dataclass(slots=True, frozen=True)
class ModeEvaluationSummary:
    mode: SearchEvaluationMode
    query_count: int
    average_latency_ms: float
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float]
    mrr: float
    ndcg_at_k: dict[int, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "query_count": self.query_count,
            "average_latency_ms": self.average_latency_ms,
            "precision_at_k": {str(key): value for key, value in self.precision_at_k.items()},
            "recall_at_k": {str(key): value for key, value in self.recall_at_k.items()},
            "mrr": self.mrr,
            "ndcg_at_k": {str(key): value for key, value in self.ndcg_at_k.items()},
        }


@dataclass(slots=True, frozen=True)
class SearchQualityEvaluationReport:
    k_values: list[int]
    per_query: list[QueryEvaluationResult]
    summaries: list[ModeEvaluationSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "k_values": list(self.k_values),
            "per_query": [item.to_dict() for item in self.per_query],
            "summaries": [item.to_dict() for item in self.summaries],
        }


def precision_at_k(
    ranked_candidate_ids: list[str],
    relevance: dict[str, float],
    *,
    k: int,
) -> float:
    if k <= 0:
        return 0.0

    top_k = ranked_candidate_ids[:k]
    relevant_in_top_k = sum(1 for candidate_id in top_k if relevance.get(candidate_id, 0.0) > 0.0)
    return relevant_in_top_k / k


def recall_at_k(
    ranked_candidate_ids: list[str],
    relevance: dict[str, float],
    *,
    k: int,
) -> float:
    relevant_total = sum(1 for grade in relevance.values() if grade > 0.0)
    if relevant_total == 0:
        return 0.0

    top_k = ranked_candidate_ids[:k]
    relevant_in_top_k = sum(1 for candidate_id in top_k if relevance.get(candidate_id, 0.0) > 0.0)
    return relevant_in_top_k / relevant_total


def reciprocal_rank(
    ranked_candidate_ids: list[str],
    relevance: dict[str, float],
) -> float:
    for rank, candidate_id in enumerate(ranked_candidate_ids, start=1):
        if relevance.get(candidate_id, 0.0) > 0.0:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    ranked_candidate_ids: list[str],
    relevance: dict[str, float],
    *,
    k: int,
) -> float:
    if k <= 0:
        return 0.0

    def dcg(grades: list[float]) -> float:
        score = 0.0
        for rank, grade in enumerate(grades, start=1):
            score += (2**grade - 1.0) / math.log2(rank + 1.0)
        return score

    actual_grades = [relevance.get(candidate_id, 0.0) for candidate_id in ranked_candidate_ids[:k]]
    ideal_grades = sorted((grade for grade in relevance.values() if grade > 0.0), reverse=True)[:k]

    actual_dcg = dcg(actual_grades)
    ideal_dcg = dcg(ideal_grades)
    if ideal_dcg <= 0.0:
        return 0.0

    return actual_dcg / ideal_dcg


@dataclass(slots=True)
class SearchQualityEvaluator:
    lexical_repository: LexicalSearchRepository
    vector_repository: VectorSearchRepository
    embedding_provider: EmbeddingProvider
    hybrid_search_service: HybridSearchService
    retry_attempts: int = 2
    retry_delay_seconds: float = 1.0

    async def evaluate(
        self,
        *,
        cases: list[SearchQualityCase],
        k_values: list[int],
        modes: list[SearchEvaluationMode] | tuple[SearchEvaluationMode, ...] = (
            SearchEvaluationMode.LEXICAL,
            SearchEvaluationMode.VECTOR,
            SearchEvaluationMode.HYBRID,
        ),
    ) -> SearchQualityEvaluationReport:
        normalized_k_values = sorted({int(item) for item in k_values if int(item) > 0})
        if not normalized_k_values:
            raise ValueError("k_values must contain at least one positive integer")

        await self.warmup(
            cases=cases,
            modes=modes,
            limit=max(normalized_k_values),
        )
        self._clear_runtime_caches()

        per_query: list[QueryEvaluationResult] = []
        search_limit = max(normalized_k_values)

        for case in cases:
            for mode in modes:
                started_at = time.perf_counter()
                documents = await self._run_mode_with_retry(
                    mode=mode,
                    filters=case.filters,
                    limit=search_limit,
                )
                latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
                ranked_candidate_ids = self._extract_candidate_ids(documents)

                per_query.append(
                    QueryEvaluationResult(
                        case_id=case.case_id,
                        mode=mode,
                        latency_ms=latency_ms,
                        ranked_candidate_ids=ranked_candidate_ids,
                        precision_at_k={
                            k: round(
                                precision_at_k(
                                    ranked_candidate_ids,
                                    case.relevance,
                                    k=k,
                                ),
                                6,
                            )
                            for k in normalized_k_values
                        },
                        recall_at_k={
                            k: round(
                                recall_at_k(
                                    ranked_candidate_ids,
                                    case.relevance,
                                    k=k,
                                ),
                                6,
                            )
                            for k in normalized_k_values
                        },
                        mrr=round(reciprocal_rank(ranked_candidate_ids, case.relevance), 6),
                        ndcg_at_k={
                            k: round(
                                ndcg_at_k(
                                    ranked_candidate_ids,
                                    case.relevance,
                                    k=k,
                                ),
                                6,
                            )
                            for k in normalized_k_values
                        },
                    )
                )

        summaries: list[ModeEvaluationSummary] = []
        for mode in modes:
            mode_results = [item for item in per_query if item.mode == mode]
            if not mode_results:
                continue

            summaries.append(
                ModeEvaluationSummary(
                    mode=mode,
                    query_count=len(mode_results),
                    average_latency_ms=round(
                        sum(item.latency_ms for item in mode_results) / len(mode_results),
                        3,
                    ),
                    precision_at_k={
                        k: round(
                            sum(item.precision_at_k[k] for item in mode_results) / len(mode_results),
                            6,
                        )
                        for k in normalized_k_values
                    },
                    recall_at_k={
                        k: round(
                            sum(item.recall_at_k[k] for item in mode_results) / len(mode_results),
                            6,
                        )
                        for k in normalized_k_values
                    },
                    mrr=round(
                        sum(item.mrr for item in mode_results) / len(mode_results),
                        6,
                    ),
                    ndcg_at_k={
                        k: round(
                            sum(item.ndcg_at_k[k] for item in mode_results) / len(mode_results),
                            6,
                        )
                        for k in normalized_k_values
                    },
                )
            )

        return SearchQualityEvaluationReport(
            k_values=normalized_k_values,
            per_query=per_query,
            summaries=summaries,
        )

    async def warmup(
        self,
        *,
        cases: list[SearchQualityCase],
        modes: list[SearchEvaluationMode] | tuple[SearchEvaluationMode, ...],
        limit: int,
    ) -> None:
        if limit <= 0 or not cases:
            return

        for mode in modes:
            target_case = self._select_warmup_case(cases=cases, mode=mode)
            if target_case is None:
                continue

            try:
                await self._run_mode_with_retry(
                    mode=mode,
                    filters=target_case.filters,
                    limit=limit,
                )
            except Exception:
                # Warmup is best-effort: the measured run below still surfaces real failures.
                continue

    async def search_documents(
        self,
        *,
        mode: SearchEvaluationMode,
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        return await self._run_mode_with_retry(
            mode=mode,
            filters=filters,
            limit=limit,
        )

    async def _run_mode_with_retry(
        self,
        *,
        mode: SearchEvaluationMode,
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        attempts = max(int(self.retry_attempts), 1)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await self._run_mode(
                    mode=mode,
                    filters=filters,
                    limit=limit,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= attempts or not self._is_retryable_error(exc):
                    raise
                await asyncio.sleep(self.retry_delay_seconds)

        if last_error is not None:
            raise last_error

        return []

    async def _run_mode(
        self,
        *,
        mode: SearchEvaluationMode,
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        if mode == SearchEvaluationMode.LEXICAL:
            return await self._search_lexical(filters=filters, limit=limit)

        if mode == SearchEvaluationMode.VECTOR:
            return await self._search_vector(filters=filters, limit=limit)

        if mode == SearchEvaluationMode.HYBRID:
            result = await self.hybrid_search_service.search(
                filters=filters,
                limit=limit,
                include_total=False,
            )
            return result.items

        raise ValueError(f"unsupported search mode: {mode}")

    async def _search_lexical(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        candidate_ids = await self.lexical_repository.search_candidate_ids(
            filters=filters,
            limit=limit,
        )
        return await self._load_documents_by_ids(
            candidate_ids=candidate_ids,
            filters=filters,
            limit=limit,
        )

    async def _search_vector(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        query_text = DefaultHybridSearchService._build_query_text(filters)
        if not query_text:
            return []

        query_vector = await self.embedding_provider.encode_text(query_text)
        if not query_vector:
            return []

        candidate_ids = await self.vector_repository.search_candidate_ids(
            query_vector=query_vector,
            exclude_ids=DefaultHybridSearchService._extract_exclude_ids(filters),
            limit=limit,
        )
        return await self._load_documents_by_ids(
            candidate_ids=candidate_ids,
            filters=filters,
            limit=limit,
        )

    async def _load_documents_by_ids(
        self,
        *,
        candidate_ids: list[str],
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not candidate_ids:
            return []

        documents = await self.lexical_repository.get_documents(candidate_ids)
        ordered_documents = DefaultHybridSearchService._order_documents_by_ids(
            documents=documents,
            ordered_ids=candidate_ids,
        )
        filtered_documents = DefaultHybridSearchService._apply_hard_filters(
            documents=ordered_documents,
            filters=filters,
        )
        return filtered_documents[:limit]

    @staticmethod
    def _extract_candidate_ids(documents: list[dict[str, Any]]) -> list[str]:
        ranked_candidate_ids: list[str] = []
        for item in documents:
            raw_id = item.get("id")
            if raw_id is None:
                continue

            normalized_id = str(raw_id).strip()
            if not normalized_id:
                continue

            ranked_candidate_ids.append(normalized_id)

        return ranked_candidate_ids

    @staticmethod
    def _select_warmup_case(
        *,
        cases: list[SearchQualityCase],
        mode: SearchEvaluationMode,
    ) -> SearchQualityCase | None:
        if mode == SearchEvaluationMode.LEXICAL:
            return cases[0] if cases else None

        for case in cases:
            if DefaultHybridSearchService._build_query_text(case.filters):
                return case

        return cases[0] if cases else None

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        retryable_error_types: tuple[type[Exception], ...] = (
            SearchBackendUnavailableError,
            EmbeddingGenerationError,
            RankingUnavailableError,
            TimeoutError,
        )

        if ElasticConnectionTimeout:
            retryable_error_types = retryable_error_types + (ElasticConnectionTimeout,)  # type: ignore[operator]

        return isinstance(exc, retryable_error_types)

    def _clear_runtime_caches(self) -> None:
        clear_method = getattr(self.hybrid_search_service, "clear_runtime_caches", None)
        if callable(clear_method):
            clear_method()


def load_quality_cases(payload: dict[str, Any]) -> tuple[list[int], list[SearchQualityCase]]:
    raw_k_values = payload.get("k_values") or [5, 10]
    k_values = [int(item) for item in raw_k_values if int(item) > 0]

    cases: list[SearchQualityCase] = []
    for index, item in enumerate(payload.get("cases") or [], start=1):
        if not isinstance(item, dict):
            continue

        case_id = str(item.get("id") or f"case_{index}").strip()
        filters = item.get("filters")
        if not isinstance(filters, dict):
            raise ValueError(f"case '{case_id}' must contain object field 'filters'")

        relevance_payload = item.get("relevance")
        if isinstance(relevance_payload, dict):
            relevance = {str(key): float(value) for key, value in relevance_payload.items()}
        elif isinstance(relevance_payload, list):
            relevance = {str(value): 1.0 for value in relevance_payload}
        else:
            relevant_ids = item.get("relevant_ids") or []
            relevance = {str(value): 1.0 for value in relevant_ids}

        cases.append(
            SearchQualityCase(
                case_id=case_id,
                filters=filters,
                relevance=relevance,
            )
        )

    return k_values, cases
