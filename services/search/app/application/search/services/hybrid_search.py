from __future__ import annotations

import asyncio
import copy
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from app.application.common.contracts import (
    EmbeddingProvider,
    HybridSearchResult,
    HybridSearchService,
    Ranker,
)
from app.application.search.services.currency import normalize_to_rub
from app.application.search.services.rrf import reciprocal_rank_fusion
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class DefaultHybridSearchService(HybridSearchService):
    lexical_repository: LexicalSearchRepository
    vector_repository: VectorSearchRepository
    embedding_provider: EmbeddingProvider
    ranker: Ranker
    retrieval_size: int
    rerank_top_k: int
    rrf_k: int
    query_embedding_cache_size: int = 128
    result_cache_ttl_seconds: float = 0.0
    result_cache_size: int = 128
    timing_logging_enabled: bool = False
    timing_logging_threshold_ms: float = 1000.0
    _query_embedding_cache: OrderedDict[str, list[float]] = field(
        init=False,
        repr=False,
        default_factory=OrderedDict,
    )
    _result_cache: OrderedDict[str, tuple[float, HybridSearchResult]] = field(
        init=False,
        repr=False,
        default_factory=OrderedDict,
    )

    def __post_init__(self) -> None:
        self._query_embedding_cache = OrderedDict()
        self._result_cache = OrderedDict()

    async def search(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
    ) -> HybridSearchResult:
        cache_key = self._build_result_cache_key(filters=filters, limit=limit)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

        started_at = time.perf_counter()
        effective_limit = max(limit, self.retrieval_size, self.rerank_top_k)
        query_text = self._build_query_text(filters)
        timings: dict[str, float] = {}

        lexical_total, lexical_ids, vector_ids = await asyncio.gather(
            self._timed_count_candidates(filters=filters, timings=timings),
            self._timed_search_candidate_ids(
                filters=filters,
                limit=effective_limit,
                timings=timings,
            ),
            self._search_vector_ids(
                filters=filters,
                query_text=query_text,
                limit=effective_limit,
                timings=timings,
            ),
        )

        fused = reciprocal_rank_fusion(
            ranked_lists=[lexical_ids, vector_ids],
            k=self.rrf_k,
        )
        timings["fusion_ms"] = self._elapsed_ms(started_at)
        if not fused:
            self._log_timings(
                timings=timings,
                total_ms=self._elapsed_ms(started_at),
                limit=limit,
                lexical_total=lexical_total,
                lexical_ids=lexical_ids,
                vector_ids=vector_ids,
                fused_count=0,
                rerank_input_count=0,
                result_count=0,
                used_ranker=False,
            )
            return self._cache_result(
                cache_key,
                HybridSearchResult(total=lexical_total, items=[]),
            )

        rerank_window = self._resolve_rerank_window(
            requested_limit=limit,
            effective_limit=effective_limit,
        )
        top_ids = [candidate_id for candidate_id, _ in fused[:rerank_window]]
        documents_started_at = time.perf_counter()
        documents = await self.lexical_repository.get_documents(top_ids)
        timings["documents_ms"] = self._elapsed_ms(documents_started_at)
        if not documents:
            self._log_timings(
                timings=timings,
                total_ms=self._elapsed_ms(started_at),
                limit=limit,
                lexical_total=lexical_total,
                lexical_ids=lexical_ids,
                vector_ids=vector_ids,
                fused_count=len(fused),
                rerank_input_count=0,
                result_count=0,
                used_ranker=False,
            )
            return self._cache_result(
                cache_key,
                HybridSearchResult(total=lexical_total, items=[]),
            )

        ordered_documents = self._order_documents_by_ids(
            documents=documents,
            ordered_ids=top_ids,
        )
        if not ordered_documents:
            self._log_timings(
                timings=timings,
                total_ms=self._elapsed_ms(started_at),
                limit=limit,
                lexical_total=lexical_total,
                lexical_ids=lexical_ids,
                vector_ids=vector_ids,
                fused_count=len(fused),
                rerank_input_count=0,
                result_count=0,
                used_ranker=False,
            )
            return self._cache_result(
                cache_key,
                HybridSearchResult(total=lexical_total, items=[]),
            )

        hard_filters_started_at = time.perf_counter()
        filtered_documents = self._apply_hard_filters(
            documents=ordered_documents,
            filters=filters,
        )
        timings["hard_filters_ms"] = self._elapsed_ms(hard_filters_started_at)
        if not filtered_documents:
            self._log_timings(
                timings=timings,
                total_ms=self._elapsed_ms(started_at),
                limit=limit,
                lexical_total=lexical_total,
                lexical_ids=lexical_ids,
                vector_ids=vector_ids,
                fused_count=len(fused),
                rerank_input_count=0,
                result_count=0,
                used_ranker=False,
            )
            return self._cache_result(
                cache_key,
                HybridSearchResult(total=lexical_total, items=[]),
            )

        rerank_started_at = time.perf_counter()
        ranked_documents = await self.ranker.rerank(
            query_text=query_text,
            candidates=filtered_documents,
            filters=filters,
        )
        timings["rerank_ms"] = self._elapsed_ms(rerank_started_at)
        if ranked_documents:
            total_ms = self._elapsed_ms(started_at)
            self._log_timings(
                timings=timings,
                total_ms=total_ms,
                limit=limit,
                lexical_total=lexical_total,
                lexical_ids=lexical_ids,
                vector_ids=vector_ids,
                fused_count=len(fused),
                rerank_input_count=len(filtered_documents),
                result_count=min(len(ranked_documents), limit),
                used_ranker=True,
            )
            return self._cache_result(
                cache_key,
                HybridSearchResult(
                    total=lexical_total,
                    items=ranked_documents[:limit],
                ),
            )

        total_ms = self._elapsed_ms(started_at)
        self._log_timings(
            timings=timings,
            total_ms=total_ms,
            limit=limit,
            lexical_total=lexical_total,
            lexical_ids=lexical_ids,
            vector_ids=vector_ids,
            fused_count=len(fused),
            rerank_input_count=len(filtered_documents),
            result_count=min(len(filtered_documents), limit),
            used_ranker=False,
        )
        return self._cache_result(
            cache_key,
            HybridSearchResult(
                total=lexical_total,
                items=filtered_documents[:limit],
            ),
        )

    async def _search_vector_ids(
        self,
        *,
        filters: dict[str, Any],
        query_text: str,
        limit: int,
        timings: dict[str, float],
    ) -> list[str]:
        if not query_text:
            return []

        embedding_started_at = time.perf_counter()
        query_vector = await self._get_query_embedding(query_text)
        timings["embedding_ms"] = self._elapsed_ms(embedding_started_at)
        if not query_vector:
            return []

        vector_search_started_at = time.perf_counter()
        result = await self.vector_repository.search_candidate_ids(
            query_vector=query_vector,
            exclude_ids=self._extract_exclude_ids(filters),
            limit=limit,
        )
        timings["vector_search_ms"] = self._elapsed_ms(vector_search_started_at)
        return result

    async def _timed_count_candidates(
        self,
        *,
        filters: dict[str, Any],
        timings: dict[str, float],
    ) -> int:
        started_at = time.perf_counter()
        result = await self.lexical_repository.count_candidates(filters=filters)
        timings["count_ms"] = self._elapsed_ms(started_at)
        return result

    async def _timed_search_candidate_ids(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
        timings: dict[str, float],
    ) -> list[str]:
        started_at = time.perf_counter()
        result = await self.lexical_repository.search_candidate_ids(
            filters=filters,
            limit=limit,
        )
        timings["lexical_search_ms"] = self._elapsed_ms(started_at)
        return result

    async def _get_query_embedding(self, query_text: str) -> list[float]:
        cached = self._query_embedding_cache.get(query_text)
        if cached is not None:
            self._query_embedding_cache.move_to_end(query_text)
            return list(cached)

        embedding = await self.embedding_provider.encode_text(query_text)
        self._query_embedding_cache[query_text] = list(embedding)
        self._query_embedding_cache.move_to_end(query_text)

        while len(self._query_embedding_cache) > self.query_embedding_cache_size:
            self._query_embedding_cache.popitem(last=False)

        return list(embedding)

    def _build_result_cache_key(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
    ) -> str:
        payload = {
            "limit": limit,
            "filters": self._normalize_for_cache(filters),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _normalize_for_cache(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._normalize_for_cache(item) for key, item in sorted(value.items())
            }
        if isinstance(value, list | tuple):
            return [self._normalize_for_cache(item) for item in value]
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        return value

    def _get_cached_result(self, cache_key: str) -> HybridSearchResult | None:
        if self.result_cache_ttl_seconds <= 0:
            return None

        cached = self._result_cache.get(cache_key)
        if cached is None:
            return None

        expires_at, result = cached
        if expires_at <= time.monotonic():
            self._result_cache.pop(cache_key, None)
            return None

        self._result_cache.move_to_end(cache_key)
        return self._clone_result(result)

    def _cache_result(
        self,
        cache_key: str,
        result: HybridSearchResult,
    ) -> HybridSearchResult:
        if self.result_cache_ttl_seconds > 0:
            self._result_cache[cache_key] = (
                time.monotonic() + self.result_cache_ttl_seconds,
                self._clone_result(result),
            )
            self._result_cache.move_to_end(cache_key)
            self._prune_result_cache()

        return self._clone_result(result)

    def _clone_result(self, result: HybridSearchResult) -> HybridSearchResult:
        return HybridSearchResult(
            total=result.total,
            items=copy.deepcopy(result.items),
        )

    def _prune_result_cache(self) -> None:
        now = time.monotonic()
        expired_keys = [
            key for key, (expires_at, _) in self._result_cache.items() if expires_at <= now
        ]
        for key in expired_keys:
            self._result_cache.pop(key, None)

        while len(self._result_cache) > self.result_cache_size:
            self._result_cache.popitem(last=False)

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 2)

    def _log_timings(
        self,
        *,
        timings: dict[str, float],
        total_ms: float,
        limit: int,
        lexical_total: int,
        lexical_ids: list[str],
        vector_ids: list[str],
        fused_count: int,
        rerank_input_count: int,
        result_count: int,
        used_ranker: bool,
    ) -> None:
        if not self.timing_logging_enabled:
            return
        if total_ms < self.timing_logging_threshold_ms:
            return

        logger.info(
            "hybrid search timings",
            extra={
                "total_ms": total_ms,
                "count_ms": timings.get("count_ms", 0.0),
                "lexical_search_ms": timings.get("lexical_search_ms", 0.0),
                "embedding_ms": timings.get("embedding_ms", 0.0),
                "vector_search_ms": timings.get("vector_search_ms", 0.0),
                "fusion_ms": timings.get("fusion_ms", 0.0),
                "documents_ms": timings.get("documents_ms", 0.0),
                "hard_filters_ms": timings.get("hard_filters_ms", 0.0),
                "rerank_ms": timings.get("rerank_ms", 0.0),
                "limit": limit,
                "lexical_total": lexical_total,
                "lexical_hits": len(lexical_ids),
                "vector_hits": len(vector_ids),
                "fused_hits": fused_count,
                "rerank_input_count": rerank_input_count,
                "result_count": result_count,
                "used_ranker": used_ranker,
            },
        )

    def _resolve_rerank_window(
        self,
        *,
        requested_limit: int,
        effective_limit: int,
    ) -> int:
        buffered_limit = requested_limit + max(2, requested_limit // 4)
        return max(requested_limit, min(self.rerank_top_k, effective_limit, buffered_limit))

    @staticmethod
    def _build_query_text(filters: dict[str, Any]) -> str:
        parts: list[str] = []

        role = str(filters.get("role") or "").strip()
        if role:
            parts.append(role)

        must_skills = filters.get("must_skills") or []
        nice_skills = filters.get("nice_skills") or []

        skill_names: list[str] = []
        for item in [*must_skills, *nice_skills]:
            if not isinstance(item, dict):
                continue

            skill = str(item.get("skill") or "").strip()
            if skill:
                skill_names.append(skill)

        if skill_names:
            unique_skill_names: list[str] = []
            seen: set[str] = set()
            for skill in skill_names:
                key = skill.lower()
                if key in seen:
                    continue
                seen.add(key)
                unique_skill_names.append(skill)

            parts.append(f"skills: {', '.join(unique_skill_names)}")

        location = str(filters.get("location") or "").strip()
        if location:
            parts.append(f"location: {location}")

        work_modes = [
            str(item).strip() for item in (filters.get("work_modes") or []) if str(item).strip()
        ]
        if work_modes:
            parts.append(f"work mode: {', '.join(work_modes)}")

        english_level = str(filters.get("english_level") or "").strip()
        if english_level:
            parts.append(f"english: {english_level}")

        about_me = str(filters.get("about_me") or "").strip()
        if about_me:
            parts.append(about_me)

        return " ".join(parts).strip()

    @staticmethod
    def _extract_exclude_ids(filters: dict[str, Any]) -> list[UUID]:
        result: list[UUID] = []
        seen: set[UUID] = set()

        for item in filters.get("exclude_ids") or []:
            try:
                value = UUID(str(item))
            except ValueError:
                continue

            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    @staticmethod
    def _order_documents_by_ids(
        *,
        documents: list[dict[str, Any]],
        ordered_ids: list[str],
    ) -> list[dict[str, Any]]:
        documents_by_id: dict[str, dict[str, Any]] = {}

        for item in documents:
            raw_id = item.get("id")
            if raw_id is None:
                continue
            documents_by_id[str(raw_id)] = item

        return [documents_by_id[item_id] for item_id in ordered_ids if item_id in documents_by_id]

    @classmethod
    def _apply_hard_filters(
        cls,
        *,
        documents: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        must_skills = cls._extract_required_skills(filters)
        if not must_skills:
            return documents

        result: list[dict[str, Any]] = []
        for document in documents:
            if not cls._candidate_matches_status(document):
                continue

            candidate_skills = cls._extract_candidate_skills(document)
            if not cls._candidate_matches_required_skills(
                candidate_skills=candidate_skills,
                required_skills=must_skills,
            ):
                continue

            if not cls._candidate_matches_work_modes(document=document, filters=filters):
                continue

            if not cls._candidate_matches_experience(document=document, filters=filters):
                continue

            if not cls._candidate_matches_salary(document=document, filters=filters):
                continue

            result.append(document)

        return result

    @staticmethod
    def _candidate_matches_status(document: dict[str, Any]) -> bool:
        status = str(document.get("status") or "").strip().lower()
        return status in {"", "active"}

    @staticmethod
    def _extract_required_skills(filters: dict[str, Any]) -> dict[str, int | None]:
        result: dict[str, int | None] = {}

        for item in filters.get("must_skills") or []:
            if not isinstance(item, dict):
                continue

            raw_skill = item.get("skill")
            if raw_skill is None:
                continue

            normalized = str(raw_skill).strip().lower()
            if not normalized:
                continue

            level: int | None = None
            raw_level = item.get("level")
            if raw_level is not None and not isinstance(raw_level, bool):
                try:
                    level = int(raw_level)
                except (TypeError, ValueError):
                    level = None

            existing_level = result.get(normalized)
            if existing_level is None:
                result[normalized] = level
                continue

            if level is not None and (existing_level is None or level > existing_level):
                result[normalized] = level

        return result

    @staticmethod
    def _extract_candidate_skills(document: dict[str, Any]) -> dict[str, int | None]:
        result: dict[str, int | None] = {}

        for item in document.get("skills") or []:
            if isinstance(item, dict):
                raw_skill = item.get("skill") or item.get("name") or item.get("title")
                raw_level = item.get("level")
            else:
                raw_skill = item
                raw_level = None

            if raw_skill is None:
                continue

            normalized = str(raw_skill).strip().lower()
            if not normalized:
                continue

            level: int | None = None
            if raw_level is not None and not isinstance(raw_level, bool):
                try:
                    level = int(raw_level)
                except (TypeError, ValueError):
                    level = None

            existing_level = result.get(normalized)
            if existing_level is None:
                result[normalized] = level
                continue

            if level is not None and (existing_level is None or level > existing_level):
                result[normalized] = level

        return result

    @staticmethod
    def _candidate_matches_required_skills(
        *,
        candidate_skills: dict[str, int | None],
        required_skills: dict[str, int | None],
    ) -> bool:
        for skill, required_level in required_skills.items():
            if skill not in candidate_skills:
                return False

            candidate_level = candidate_skills[skill]
            if required_level is None or candidate_level is None:
                continue

            if candidate_level < required_level:
                return False

        return True

    @staticmethod
    def _candidate_matches_work_modes(
        *,
        document: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        requested_modes = {
            str(item).strip().lower()
            for item in (filters.get("work_modes") or [])
            if str(item).strip()
        }
        requested_modes = {"onsite" if item == "office" else item for item in requested_modes}
        if not requested_modes:
            return True

        candidate_modes = {
            str(item).strip().lower()
            for item in (document.get("work_modes") or [])
            if str(item).strip()
        }
        candidate_modes = {"onsite" if item == "office" else item for item in candidate_modes}
        if not candidate_modes:
            return False

        compatible: set[str] = set()
        if "remote" in requested_modes:
            compatible.update({"remote", "hybrid"})
        if "onsite" in requested_modes:
            compatible.update({"onsite", "hybrid"})
        if "hybrid" in requested_modes:
            compatible.update({"hybrid", "onsite", "remote"})

        return bool(candidate_modes & compatible)

    @staticmethod
    def _candidate_matches_experience(
        *,
        document: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        experience = document.get("experience_years")
        try:
            candidate_experience = float(experience) if experience is not None else 0.0
        except (TypeError, ValueError):
            candidate_experience = 0.0

        experience_min = filters.get("experience_min")
        if experience_min is not None and candidate_experience < float(experience_min):
            return False

        experience_max = filters.get("experience_max")
        if experience_max is not None and candidate_experience > float(experience_max) + 2.0:
            return False

        return True

    @staticmethod
    def _candidate_matches_salary(
        *,
        document: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        salary_min = filters.get("salary_min")
        salary_max = filters.get("salary_max")
        currency = filters.get("currency")

        if salary_min is not None:
            requested_min_rub = normalize_to_rub(salary_min, currency)
            if requested_min_rub is not None:
                candidate_salary_min_rub = document.get("salary_min_rub")
                candidate_salary_max_rub = document.get("salary_max_rub")
                if candidate_salary_min_rub is not None or candidate_salary_max_rub is not None:
                    try:
                        min_matches = (
                            candidate_salary_min_rub is not None
                            and float(candidate_salary_min_rub) >= requested_min_rub
                        )
                        max_matches = (
                            candidate_salary_max_rub is not None
                            and float(candidate_salary_max_rub) >= requested_min_rub
                        )
                    except (TypeError, ValueError):
                        min_matches = False
                        max_matches = False
                    if not min_matches and not max_matches:
                        return False

        if salary_max is not None:
            requested_max_rub = normalize_to_rub(salary_max, currency)
            if requested_max_rub is not None:
                candidate_salary_min_rub = document.get("salary_min_rub")
                if candidate_salary_min_rub is not None:
                    try:
                        if float(candidate_salary_min_rub) > requested_max_rub:
                            return False
                    except (TypeError, ValueError):
                        return False

        return True
