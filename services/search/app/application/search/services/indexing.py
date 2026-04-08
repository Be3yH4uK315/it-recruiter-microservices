from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.application.common.contracts import (
    CandidateDocumentPayload,
    CandidateIndexingService,
    EmbeddingProvider,
)
from app.application.search.services.candidate_text_builder import build_candidate_search_text
from app.application.search.services.currency import normalize_currency_code, normalize_to_rub
from app.domain.search.entities import IndexedCandidateDocument


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def _normalize_lower_text(value: Any) -> str | None:
    normalized = _normalize_text(value)
    return normalized.lower() if normalized is not None else None


def _normalize_upper_text(value: Any) -> str | None:
    normalized = _normalize_text(value)
    return normalized.upper() if normalized is not None else None


def _normalize_skill_level(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class DefaultCandidateIndexingService(CandidateIndexingService):
    embedding_provider: EmbeddingProvider
    embedding_cache_size: int = 256
    _embedding_cache: OrderedDict[str, list[float]] = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
    )

    async def build_indexed_document(
        self,
        *,
        payload: CandidateDocumentPayload,
    ) -> IndexedCandidateDocument:
        searchable_text = build_candidate_search_text(payload)
        embedding = await self._get_embedding(searchable_text)

        document = self._build_document(
            payload=payload,
            searchable_text=searchable_text,
        )
        return IndexedCandidateDocument(
            candidate_id=payload.id,
            document=document,
            searchable_text=searchable_text,
            embedding=embedding,
            vector_present=bool(embedding),
            vector_store="milvus",
        )

    def _build_document(
        self,
        *,
        payload: CandidateDocumentPayload,
        searchable_text: str,
    ) -> dict[str, Any]:
        normalized_currency = normalize_currency_code(payload.currency)

        salary_min_rub = normalize_to_rub(payload.salary_min, normalized_currency)
        salary_max_rub = normalize_to_rub(payload.salary_max, normalized_currency)

        skills = self._normalize_skills(payload.skills)
        experiences = payload.experiences if isinstance(payload.experiences, list) else []
        projects = payload.projects if isinstance(payload.projects, list) else []
        education = payload.education if isinstance(payload.education, list) else []
        work_modes = self._normalize_string_list(payload.work_modes)

        return {
            "id": str(payload.id),
            "display_name": _normalize_text(payload.display_name) or "",
            "headline_role": _normalize_text(payload.headline_role) or "",
            "location": _normalize_text(payload.location),
            "work_modes": work_modes,
            "experience_years": float(payload.experience_years or 0.0),
            "skills": skills,
            "salary_min": payload.salary_min,
            "salary_max": payload.salary_max,
            "currency": normalized_currency,
            "salary_min_rub": salary_min_rub,
            "salary_max_rub": salary_max_rub,
            "english_level": _normalize_upper_text(payload.english_level),
            "about_me": _normalize_text(payload.about_me),
            "experiences": experiences,
            "projects": projects,
            "education": education,
            "status": _normalize_lower_text(payload.status),
            "searchable_text": searchable_text,
        }

    async def _get_embedding(self, searchable_text: str) -> list[float]:
        cached = self._embedding_cache.get(searchable_text)
        if cached is not None:
            self._embedding_cache.move_to_end(searchable_text)
            return list(cached)

        embedding = await self.embedding_provider.encode_text(searchable_text)
        if self.embedding_cache_size > 0 and searchable_text:
            self._embedding_cache[searchable_text] = list(embedding)
            self._embedding_cache.move_to_end(searchable_text)
            while len(self._embedding_cache) > self.embedding_cache_size:
                self._embedding_cache.popitem(last=False)

        return embedding

    @staticmethod
    def _normalize_string_list(items: list[Any] | None) -> list[str]:
        if not items:
            return []

        result: list[str] = []
        seen: set[str] = set()

        for item in items:
            value = _normalize_lower_text(item)
            if value is None:
                continue

            if value == "office":
                value = "onsite"

            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    @staticmethod
    def _normalize_skills(items: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in items:
            if isinstance(item, str):
                value = _normalize_lower_text(item)
                if value is None:
                    continue

                if value in seen:
                    continue

                seen.add(value)
                result.append({"skill": value})
                continue

            if not isinstance(item, dict):
                continue

            raw = item.get("skill") or item.get("name") or item.get("title")
            value = _normalize_lower_text(raw)
            if value is None:
                continue

            if value in seen:
                continue

            seen.add(value)
            normalized_item: dict[str, Any] = {"skill": value}

            level = _normalize_skill_level(item.get("level"))
            if level is not None:
                normalized_item["level"] = level

            kind = _normalize_lower_text(item.get("kind"))
            if kind is not None:
                normalized_item["kind"] = kind

            result.append(normalized_item)

        return result
