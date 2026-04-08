from __future__ import annotations

import math
from typing import Any

from app.application.search.services.currency import normalize_to_rub
from app.config import Settings
from app.domain.search.value_objects import SearchFilters

_ENGLISH_LEVEL_RANK: dict[str, int] = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
    "NATIVE": 7,
}

_REMOTE = "remote"
_ONSITE = "onsite"
_HYBRID = "hybrid"


def sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)

    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def _normalize_mode(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None

    lowered = normalized.lower()
    if lowered == "office":
        return _ONSITE
    return lowered


def _normalize_mode_set(items: list[Any] | tuple[Any, ...]) -> set[str]:
    result: set[str] = set()

    for item in items:
        value = _normalize_mode(item)
        if value is None:
            continue
        result.add(value)

    return result


def _candidate_skill_map(candidate: dict[str, Any]) -> dict[str, int | None]:
    skills_raw = candidate.get("skills") or []
    result: dict[str, int | None] = {}

    for item in skills_raw:
        if isinstance(item, dict):
            raw_name = item.get("skill") or item.get("name") or item.get("title")
            skill_name = _normalize_text(raw_name)
            if skill_name is None:
                continue

            skill_key = skill_name.lower()
            level_raw = item.get("level")
            level: int | None = None

            if isinstance(level_raw, int):
                level = level_raw
            elif isinstance(level_raw, float):
                level = int(level_raw)

            existing_level = result.get(skill_key)
            if existing_level is None:
                result[skill_key] = level
            elif level is not None and level > existing_level:
                result[skill_key] = level

            continue

        if isinstance(item, str):
            skill_name = _normalize_text(item)
            if skill_name is None:
                continue

            skill_key = skill_name.lower()
            result.setdefault(skill_key, None)

    return result


def _safe_blend(*, baseline: float, coverage: float) -> float:
    bounded_baseline = min(max(baseline, 0.0), 1.0)
    bounded_coverage = min(max(coverage, 0.0), 1.0)
    return bounded_baseline + (1.0 - bounded_baseline) * bounded_coverage


def _coverage_for_skills(
    candidate_skills: dict[str, int | None],
    requested_skills: list[Any],
) -> float:
    if not requested_skills:
        return 1.0

    matched_score = 0.0

    for item in requested_skills:
        candidate_level = candidate_skills.get(item.skill)
        has_skill = item.skill in candidate_skills

        if not has_skill:
            continue

        if item.level is None or candidate_level is None:
            matched_score += 1.0
            continue

        if candidate_level >= item.level:
            matched_score += 1.0
            continue

        matched_score += max(candidate_level / item.level, 0.0)

    return matched_score / len(requested_skills)


def _skill_match_score(
    candidate: dict[str, Any],
    filters: SearchFilters,
    settings: Settings,
) -> tuple[float, dict[str, float]]:
    candidate_skills = _candidate_skill_map(candidate)

    must_skills = list(filters.must_skills)
    nice_skills = list(filters.nice_skills)

    if not must_skills and not nice_skills:
        return 1.0, {
            "must_skill_coverage": 1.0,
            "nice_skill_coverage": 1.0,
            "skill_factor": 1.0,
        }

    must_coverage = _coverage_for_skills(candidate_skills, must_skills)
    nice_coverage = _coverage_for_skills(candidate_skills, nice_skills)

    if must_skills and nice_skills:
        combined_coverage = 0.8 * must_coverage + 0.2 * nice_coverage
    elif must_skills:
        combined_coverage = must_coverage
    else:
        combined_coverage = nice_coverage

    skill_factor = _safe_blend(
        baseline=settings.factor_no_skills,
        coverage=combined_coverage,
    )

    return skill_factor, {
        "must_skill_coverage": round(must_coverage, 6),
        "nice_skill_coverage": round(nice_coverage, 6),
        "skill_factor": round(skill_factor, 6),
    }


def _experience_factor(
    candidate: dict[str, Any],
    filters: SearchFilters,
    settings: Settings,
) -> tuple[float, float]:
    candidate_experience = float(candidate.get("experience_years") or 0.0)
    factor = 1.0

    if filters.experience_min is not None and candidate_experience < filters.experience_min:
        gap = filters.experience_min - candidate_experience
        severity = min(gap / max(filters.experience_min, 1.0), 1.0)
        factor *= 1.0 - (1.0 - settings.factor_exp_mismatch) * severity

    if filters.experience_max is not None and candidate_experience > filters.experience_max + 1.0:
        gap = candidate_experience - filters.experience_max
        severity = min(gap / max(filters.experience_max, 1.0), 1.0)
        factor *= 1.0 - (1.0 - settings.factor_exp_mismatch) * severity

    return factor, round(factor, 6)


def _work_mode_factor(
    candidate: dict[str, Any],
    filters: SearchFilters,
) -> tuple[float, float]:
    requested_modes = {_normalize_mode(item.value) for item in filters.work_modes}
    requested_modes.discard(None)
    candidate_modes = _normalize_mode_set(candidate.get("work_modes") or [])

    if not requested_modes:
        return 1.0, 1.0

    def factor_for_requested_mode(requested_mode: str) -> float:
        if requested_mode == _REMOTE:
            if _REMOTE in candidate_modes:
                return 1.1
            if _HYBRID in candidate_modes:
                return 1.0
            return 0.0

        if requested_mode == _ONSITE:
            if _ONSITE in candidate_modes:
                return 1.1
            if _HYBRID in candidate_modes:
                return 1.0
            return 0.0

        if requested_mode == _HYBRID:
            if _HYBRID in candidate_modes:
                return 1.05
            if _ONSITE in candidate_modes:
                return 1.0
            if _REMOTE in candidate_modes:
                return 1.0
            return 0.0

        return 1.0

    factor = max((factor_for_requested_mode(mode) for mode in requested_modes), default=1.0)
    return factor, round(factor, 6)


def _location_factor(
    candidate: dict[str, Any],
    filters: SearchFilters,
    settings: Settings,
) -> tuple[float, float]:
    requested_location = _normalize_text(filters.location)
    candidate_location = _normalize_text(candidate.get("location"))

    if requested_location is None:
        return 1.0, 1.0

    requested_location_normalized = requested_location.lower()
    candidate_location_normalized = (
        candidate_location.lower() if candidate_location is not None else None
    )

    has_location_match = bool(
        candidate_location_normalized
        and (
            requested_location_normalized in candidate_location_normalized
            or candidate_location_normalized in requested_location_normalized
        )
    )

    requested_modes = {_normalize_mode(item.value) for item in filters.work_modes}
    requested_modes.discard(None)
    candidate_modes = _normalize_mode_set(candidate.get("work_modes") or [])

    if not requested_modes:
        if has_location_match:
            return settings.factor_location_match, round(settings.factor_location_match, 6)
        return 1.0, 1.0

    if requested_modes == {_REMOTE}:
        return 1.0, 1.0

    if requested_modes == {_ONSITE}:
        if _ONSITE in candidate_modes:
            if has_location_match:
                return settings.factor_location_match, round(settings.factor_location_match, 6)
            return 0.7, 0.7

        if _HYBRID in candidate_modes:
            if has_location_match:
                return 0.95, 0.95
            return 0.8, 0.8

        return 0.75, 0.75

    if requested_modes == {_HYBRID}:
        if _HYBRID in candidate_modes:
            if has_location_match:
                return 1.05, 1.05
            return 0.95, 0.95

        if _ONSITE in candidate_modes:
            if has_location_match:
                return 0.95, 0.95
            return 0.85, 0.85

        if _REMOTE in candidate_modes:
            return 1.0, 1.0

        return 1.0, 1.0

    if has_location_match:
        return 1.05, 1.05

    return 1.0, 1.0


def _salary_factor(candidate: dict[str, Any], filters: SearchFilters) -> tuple[float, float]:
    if filters.salary_range is None:
        return 1.0, 1.0

    candidate_salary_min_rub = candidate.get("salary_min_rub")
    if candidate_salary_min_rub is None:
        return 1.0, 1.0

    requested_salary_max_rub = normalize_to_rub(
        filters.salary_range.max_amount,
        filters.salary_range.currency,
    )
    if requested_salary_max_rub is None:
        return 1.0, 1.0

    if float(candidate_salary_min_rub) > requested_salary_max_rub:
        return 0.9, 0.9

    return 1.0, 1.0


def _english_factor(candidate: dict[str, Any], filters: SearchFilters) -> tuple[float, float]:
    if not filters.english_level:
        return 1.0, 1.0

    candidate_english = _normalize_text(candidate.get("english_level"))
    requested_english = _normalize_text(filters.english_level)

    if requested_english is None:
        return 1.0, 1.0

    requested_english = requested_english.upper()
    if candidate_english is None:
        return 0.95, 0.95

    candidate_english = candidate_english.upper()

    candidate_rank = _ENGLISH_LEVEL_RANK.get(candidate_english)
    requested_rank = _ENGLISH_LEVEL_RANK.get(requested_english)

    if candidate_rank is None or requested_rank is None:
        return (1.0, 1.0) if candidate_english == requested_english else (0.97, 0.97)

    if candidate_rank >= requested_rank:
        return 1.0, 1.0

    gap = requested_rank - candidate_rank
    factor = max(0.85, 1.0 - 0.05 * gap)
    return factor, round(factor, 6)


def calculate_multiplicative_score(
    *,
    candidate: dict[str, Any],
    filters: SearchFilters,
    raw_ranker_score: float,
    settings: Settings,
) -> tuple[float, dict[str, float]]:
    ml_score = sigmoid(raw_ranker_score)
    final_score = ml_score

    factors: dict[str, float] = {
        "ml_score": round(ml_score, 6),
    }

    skill_factor, skill_details = _skill_match_score(candidate, filters, settings)
    final_score *= skill_factor
    factors.update(skill_details)

    experience_factor, experience_factor_rounded = _experience_factor(candidate, filters, settings)
    final_score *= experience_factor
    factors["experience_factor"] = experience_factor_rounded

    work_mode_factor, work_mode_factor_rounded = _work_mode_factor(candidate, filters)
    final_score *= work_mode_factor
    factors["work_mode_factor"] = work_mode_factor_rounded

    location_factor, location_factor_rounded = _location_factor(candidate, filters, settings)
    final_score *= location_factor
    factors["location_factor"] = location_factor_rounded

    salary_factor, salary_factor_rounded = _salary_factor(candidate, filters)
    final_score *= salary_factor
    factors["salary_factor"] = salary_factor_rounded

    english_factor, english_factor_rounded = _english_factor(candidate, filters)
    final_score *= english_factor
    factors["english_factor"] = english_factor_rounded

    factors["final_score"] = round(final_score, 6)
    return final_score, factors
