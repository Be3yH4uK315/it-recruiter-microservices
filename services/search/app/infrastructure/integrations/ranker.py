from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.application.common.contracts import Ranker
from app.application.search.services.scoring import calculate_multiplicative_score
from app.config import Settings
from app.domain.search.enums import WorkMode
from app.domain.search.errors import RankingUnavailableError
from app.domain.search.value_objects import SalaryRange, SearchFilters, SearchSkill

try:
    from sentence_transformers import CrossEncoder
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    CrossEncoder = None  # type: ignore[assignment]
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = exc
else:
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = None


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


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


def _normalize_work_mode(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None

    lowered = normalized.lower()
    if lowered == "office":
        return "onsite"
    return lowered


@dataclass(slots=True)
class CrossEncoderRanker(Ranker):
    model_name: str
    settings: Settings
    concurrency_limit: int = 1
    _model: CrossEncoder | None = field(default=None, init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.concurrency_limit)

    async def startup(self) -> None:
        if self._model is not None:
            return
        if CrossEncoder is None:
            raise RankingUnavailableError(
                "sentence-transformers dependency is not installed"
            ) from _SENTENCE_TRANSFORMERS_IMPORT_ERROR

        try:
            self._model = await asyncio.to_thread(CrossEncoder, self.model_name)
        except Exception as exc:
            raise RankingUnavailableError("ranker model initialization failed") from exc

    async def shutdown(self) -> None:
        self._model = None

    async def rerank(
        self,
        *,
        query_text: str,
        candidates: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        if self._model is None:
            raise RankingUnavailableError("ranker model is not initialized")

        effective_query_text = query_text.strip() or str(filters.get("role") or "").strip()
        if not effective_query_text:
            effective_query_text = "candidate search"

        pairs = [
            (effective_query_text, self._candidate_to_text(item) or "candidate")
            for item in candidates
        ]

        async with self._semaphore:
            try:
                raw_scores = await asyncio.to_thread(self._model.predict, pairs)
            except Exception as exc:
                raise RankingUnavailableError("ranker prediction failed") from exc

        filters_vo = self._build_filters(filters)

        ranked: list[dict[str, Any]] = []
        for item, raw_score in zip(candidates, raw_scores, strict=False):
            final_score, factors = calculate_multiplicative_score(
                candidate=item,
                filters=filters_vo,
                raw_ranker_score=float(raw_score),
                settings=self.settings,
            )

            result = dict(item)
            result["match_score"] = final_score
            result["score_explanation"] = factors
            ranked.append(result)

        ranked.sort(key=lambda item: float(item.get("match_score") or 0.0), reverse=True)
        return ranked

    @staticmethod
    def _build_filters(filters: dict[str, Any]) -> SearchFilters:
        must_skills = tuple(
            SearchSkill(
                skill=str(item["skill"]),
                level=_normalize_skill_level(item.get("level")),
            )
            for item in (filters.get("must_skills") or [])
            if isinstance(item, dict) and item.get("skill")
        )
        nice_skills = tuple(
            SearchSkill(
                skill=str(item["skill"]),
                level=_normalize_skill_level(item.get("level")),
            )
            for item in (filters.get("nice_skills") or [])
            if isinstance(item, dict) and item.get("skill")
        )

        work_modes: list[WorkMode] = []
        for item in filters.get("work_modes") or []:
            raw = _normalize_work_mode(item)
            if raw is None:
                continue

            try:
                work_modes.append(WorkMode(raw))
            except ValueError:
                continue

        role = str(filters.get("role") or "").strip()
        if len(role) < 2:
            role = "candidate"

        return SearchFilters(
            role=role,
            must_skills=must_skills,
            nice_skills=nice_skills,
            experience_min=filters.get("experience_min"),
            experience_max=filters.get("experience_max"),
            location=filters.get("location"),
            work_modes=tuple(work_modes),
            salary_range=SalaryRange.from_scalars(
                salary_min=filters.get("salary_min"),
                salary_max=filters.get("salary_max"),
                currency=filters.get("currency"),
            ),
            english_level=filters.get("english_level"),
            exclude_ids=tuple(),
            about_me=filters.get("about_me"),
        )

    @staticmethod
    def _candidate_to_text(candidate: dict[str, Any]) -> str:
        parts: list[str] = []

        headline_role = _normalize_text(candidate.get("headline_role"))
        if headline_role:
            parts.append(f"Позиция: {headline_role}")

        location = _normalize_text(candidate.get("location"))
        if location:
            parts.append(f"Локация: {location}")

        work_modes = [
            value
            for item in (candidate.get("work_modes") or [])
            if (value := _normalize_text(item)) is not None
        ]
        if work_modes:
            parts.append(f"Формат работы: {', '.join(work_modes)}")

        experience_years = candidate.get("experience_years")
        if experience_years is not None:
            parts.append(f"Опыт: {experience_years} лет")

        skills = candidate.get("skills") or []
        skill_names: list[str] = []
        if isinstance(skills, list):
            for item in skills:
                if isinstance(item, str):
                    value = _normalize_text(item)
                    if value:
                        skill_names.append(value)
                elif isinstance(item, dict):
                    value = _normalize_text(
                        item.get("skill") or item.get("name") or item.get("title")
                    )
                    if value:
                        skill_names.append(value)

        if skill_names:
            unique_skill_names: list[str] = []
            seen: set[str] = set()
            for skill_name in skill_names:
                key = skill_name.lower()
                if key in seen:
                    continue
                seen.add(key)
                unique_skill_names.append(skill_name)

            parts.append(f"Навыки: {', '.join(unique_skill_names)}")

        english_level = _normalize_text(candidate.get("english_level"))
        if english_level:
            parts.append(f"Английский: {english_level}")

        about_me = _normalize_text(candidate.get("about_me"))
        if about_me:
            parts.append(f"О себе: {about_me}")

        experiences = candidate.get("experiences") or []
        if isinstance(experiences, list) and experiences:
            lines: list[str] = []
            for item in experiences[:5]:
                if not isinstance(item, dict):
                    continue

                position = _normalize_text(item.get("position") or item.get("role"))
                company = _normalize_text(item.get("company"))
                description = _normalize_text(
                    item.get("description") or item.get("responsibilities") or item.get("summary")
                )

                line = " — ".join(part for part in (position, company) if part)
                if description:
                    line = f"{line}: {description}" if line else description
                if line:
                    lines.append(line)

            if lines:
                parts.append("Опыт работы: " + " | ".join(lines))

        projects = candidate.get("projects") or []
        if isinstance(projects, list) and projects:
            lines: list[str] = []
            for item in projects[:5]:
                if not isinstance(item, dict):
                    continue

                title = _normalize_text(item.get("title") or item.get("name"))
                description = _normalize_text(item.get("description") or item.get("summary"))

                if title and description:
                    lines.append(f"{title}: {description}")
                elif title:
                    lines.append(title)
                elif description:
                    lines.append(description)

            if lines:
                parts.append("Проекты: " + " | ".join(lines))

        return ". ".join(part for part in parts if part).strip()
