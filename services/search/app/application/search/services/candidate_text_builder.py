from __future__ import annotations

from typing import Any

from app.application.common.contracts import CandidateDocumentPayload


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def _normalize_work_mode(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None

    lowered = normalized.lower()
    if lowered == "office":
        return "onsite"
    return lowered


def _extract_skill_name(item: dict[str, Any] | str) -> str | None:
    if isinstance(item, str):
        return _normalize_text(item)

    if isinstance(item, dict):
        return _normalize_text(item.get("skill") or item.get("name") or item.get("title"))

    return None


def _extract_skill_line(item: dict[str, Any] | str) -> str | None:
    if isinstance(item, str):
        return _normalize_text(item)

    if not isinstance(item, dict):
        return None

    skill = _extract_skill_name(item)
    if skill is None:
        return None

    kind = _normalize_text(item.get("kind"))
    level = item.get("level")

    suffix_parts: list[str] = []
    if kind:
        suffix_parts.append(kind)
    if level is not None:
        suffix_parts.append(f"level {level}")

    if suffix_parts:
        return f"{skill} ({', '.join(suffix_parts)})"
    return skill


def _join_non_empty(parts: list[str]) -> str:
    return ". ".join(part for part in parts if part).strip()


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def build_candidate_search_text(payload: CandidateDocumentPayload) -> str:
    parts: list[str] = []

    headline_role = _normalize_text(payload.headline_role)
    if headline_role:
        parts.append(f"Позиция: {headline_role}")

    location = _normalize_text(payload.location)
    if location:
        parts.append(f"Локация: {location}")

    if payload.work_modes:
        work_modes = _unique_preserve_order(
            [
                value
                for item in payload.work_modes
                if (value := _normalize_work_mode(item)) is not None
            ]
        )
        if work_modes:
            parts.append(f"Формат работы: {', '.join(work_modes)}")

    if payload.experience_years is not None:
        parts.append(f"Опыт: {payload.experience_years} лет")

    if payload.salary_min is not None or payload.salary_max is not None:
        currency = _normalize_text(payload.currency) or "RUB"
        if payload.salary_min is not None and payload.salary_max is not None:
            parts.append(
                f"Зарплатные ожидания: {payload.salary_min}-{payload.salary_max} {currency}"
            )
        elif payload.salary_min is not None:
            parts.append(f"Зарплатные ожидания: от {payload.salary_min} {currency}")
        elif payload.salary_max is not None:
            parts.append(f"Зарплатные ожидания: до {payload.salary_max} {currency}")

    skill_lines = _unique_preserve_order(
        [value for item in payload.skills if (value := _extract_skill_line(item)) is not None]
    )
    if skill_lines:
        parts.append(f"Навыки: {', '.join(skill_lines)}")

    english_level = _normalize_text(payload.english_level)
    if english_level:
        parts.append(f"Английский: {english_level}")

    about_me = _normalize_text(payload.about_me)
    if about_me:
        parts.append(f"О себе: {about_me}")

    if payload.experiences:
        experience_lines: list[str] = []
        for item in payload.experiences:
            if not isinstance(item, dict):
                continue

            position = _normalize_text(item.get("position") or item.get("role"))
            company = _normalize_text(item.get("company"))
            description = _normalize_text(
                item.get("responsibilities") or item.get("description") or item.get("summary")
            )

            line = " — ".join(part for part in (position, company) if part)
            if description:
                line = f"{line}: {description}" if line else description
            if line:
                experience_lines.append(line)

        experience_lines = _unique_preserve_order(experience_lines)
        if experience_lines:
            parts.append("Опыт работы: " + " | ".join(experience_lines))

    if payload.projects:
        project_lines: list[str] = []
        for item in payload.projects:
            if not isinstance(item, dict):
                continue

            title = _normalize_text(item.get("name") or item.get("title"))
            description = _normalize_text(item.get("description") or item.get("summary"))
            raw_links = item.get("links") or []

            link_values: list[str] = []
            if isinstance(raw_links, list):
                link_values = _unique_preserve_order(
                    [value for raw in raw_links if (value := _normalize_text(raw)) is not None]
                )

            line = title or ""
            if description:
                line = f"{line}: {description}" if line else description
            if link_values:
                line = (
                    f"{line}. Ссылки: {', '.join(link_values)}" if line else ", ".join(link_values)
                )

            if line:
                project_lines.append(line)

        project_lines = _unique_preserve_order(project_lines)
        if project_lines:
            parts.append("Проекты: " + " | ".join(project_lines))

    if payload.education:
        education_lines: list[str] = []
        for item in payload.education:
            if not isinstance(item, dict):
                continue

            institution = _normalize_text(
                item.get("institution") or item.get("school") or item.get("university")
            )
            degree = _normalize_text(
                item.get("degree")
                or item.get("specialization")
                or item.get("faculty")
                or item.get("level")
            )
            year = _normalize_text(item.get("year"))

            line = " — ".join(part for part in (institution, degree, year) if part)
            if line:
                education_lines.append(line)

        education_lines = _unique_preserve_order(education_lines)
        if education_lines:
            parts.append("Образование: " + " | ".join(education_lines))

    return _join_non_empty(parts)
